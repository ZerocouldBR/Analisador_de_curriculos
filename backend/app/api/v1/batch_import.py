"""
API de importacao em lote de curriculos a partir de pasta local/rede/drive

Permite importar curriculos de:
- Pasta local no servidor
- Pasta de rede montada (SMB/NFS/CIFS)
- Drive compartilhado (Google Drive, OneDrive montado)
- Qualquer diretorio acessivel pelo sistema operacional

Funcionalidades:
- Scan de pasta com filtro por extensao
- Importacao em lote com progresso
- Deduplicacao por hash SHA256
- Log detalhado de cada arquivo
- Suporte a subpastas (recursivo)
"""
import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, require_permission
from app.db.database import get_db
from app.db.models import User, Document, Candidate, AuditLog
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch-import", tags=["batch-import"])


# ============================================
# Schemas
# ============================================

SUPPORTED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff",
}


class FolderScanRequest(BaseModel):
    folder_path: str = Field(
        ...,
        description="Caminho da pasta para escanear (local, rede, ou drive montado)",
        examples=[
            "/mnt/rh/curriculos",
            "/home/user/curriculos",
            "//servidor/compartilhamento/curriculos",
            "/mnt/gdrive/Curriculos RH",
        ],
    )
    recursive: bool = Field(
        default=True,
        description="Escanear subpastas recursivamente",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="Filtrar por extensoes (ex: ['.pdf', '.docx']). Null = todas suportadas",
    )


class FolderScanResponse(BaseModel):
    folder_path: str
    exists: bool
    readable: bool
    total_files: int
    supported_files: int
    unsupported_files: int
    already_imported: int
    files: List[Dict[str, Any]]
    summary_by_extension: Dict[str, int]
    total_size_mb: float


class BatchImportRequest(BaseModel):
    folder_path: str = Field(
        ...,
        description="Caminho da pasta para importar",
    )
    recursive: bool = Field(default=True)
    extensions: Optional[List[str]] = Field(default=None)
    skip_duplicates: bool = Field(
        default=True,
        description="Pular arquivos ja importados (por hash SHA256)",
    )
    candidate_id: Optional[int] = Field(
        default=None,
        description="Vincular todos a um candidato (null = criar novo por arquivo)",
    )


class BatchImportFileResult(BaseModel):
    filename: str
    path: str
    status: str  # imported, skipped_duplicate, error
    message: str
    document_id: Optional[int] = None
    candidate_id: Optional[int] = None


class BatchImportResponse(BaseModel):
    folder_path: str
    total_files: int
    imported: int
    skipped_duplicates: int
    errors: int
    results: List[BatchImportFileResult]


class WatchFolderRequest(BaseModel):
    folder_path: str = Field(..., description="Caminho da pasta para monitorar")
    recursive: bool = Field(default=True)
    extensions: Optional[List[str]] = Field(default=None)


# ============================================
# Helpers
# ============================================

def _resolve_and_validate_path(folder_path: str) -> Path:
    """Resolve e valida o caminho da pasta"""
    path = Path(folder_path)

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pasta nao encontrada: {folder_path}. "
                   f"Verifique se o caminho existe e esta montado/acessivel.",
        )

    if not path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O caminho nao e uma pasta: {folder_path}",
        )

    if not os.access(path, os.R_OK):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem permissao de leitura na pasta: {folder_path}. "
                   f"Verifique permissoes do usuario do servidor.",
        )

    return path


def _scan_files(
    folder: Path,
    recursive: bool,
    extensions: Optional[List[str]] = None,
) -> List[Path]:
    """Escaneia pasta e retorna lista de arquivos suportados"""
    allowed_ext = set(extensions) if extensions else SUPPORTED_EXTENSIONS

    files = []
    if recursive:
        for f in folder.rglob("*"):
            if f.is_file() and f.suffix.lower() in allowed_ext:
                files.append(f)
    else:
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in allowed_ext:
                files.append(f)

    return sorted(files, key=lambda p: p.name)


def _get_existing_hashes(db: Session) -> set:
    """Retorna set de hashes de documentos ja importados"""
    hashes = db.query(Document.sha256_hash).all()
    return {h[0] for h in hashes if h[0]}


# ============================================
# Endpoints
# ============================================

@router.post("/scan", response_model=FolderScanResponse)
def scan_folder(
    data: FolderScanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.create")),
):
    """
    Escaneia uma pasta e lista os arquivos disponiveis para importacao

    Use este endpoint antes de importar para verificar:
    - Quantos arquivos existem
    - Quais ja foram importados
    - Quais formatos estao presentes
    - Tamanho total

    Suporta pastas locais, de rede (montadas) e drives compartilhados.

    **Exemplos de caminhos:**
    - Linux local: `/home/rh/curriculos`
    - Rede montada: `/mnt/servidor/rh/curriculos`
    - NFS: `/mnt/nfs/curriculos`
    - Google Drive (montado): `/mnt/gdrive/Curriculos`

    **Requer permissao:** documents.create
    """
    folder = _resolve_and_validate_path(data.folder_path)
    files = _scan_files(folder, data.recursive, data.extensions)

    # Verificar quais ja foram importados
    existing_hashes = _get_existing_hashes(db)

    file_info = []
    summary_by_ext: Dict[str, int] = {}
    total_size = 0
    already_imported = 0

    for f in files:
        ext = f.suffix.lower()
        size = f.stat().st_size
        total_size += size

        summary_by_ext[ext] = summary_by_ext.get(ext, 0) + 1

        # Verificar se ja foi importado (por hash)
        file_hash = None
        is_duplicate = False
        try:
            with open(f, "rb") as fh:
                file_hash = storage_service.calculate_sha256(fh)
            is_duplicate = file_hash in existing_hashes
            if is_duplicate:
                already_imported += 1
        except Exception:
            pass

        file_info.append({
            "name": f.name,
            "path": str(f),
            "extension": ext,
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "modified_at": datetime.fromtimestamp(
                f.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
            "already_imported": is_duplicate,
            "sha256": file_hash,
        })

    # Contar unsupported
    all_files_count = 0
    if data.recursive:
        all_files_count = sum(1 for _ in folder.rglob("*") if _.is_file())
    else:
        all_files_count = sum(1 for _ in folder.iterdir() if _.is_file())

    unsupported = all_files_count - len(files)

    logger.info(
        f"Folder scan: {data.folder_path} -> "
        f"{len(files)} supported files, {already_imported} already imported, "
        f"{unsupported} unsupported"
    )

    return FolderScanResponse(
        folder_path=str(folder),
        exists=True,
        readable=True,
        total_files=all_files_count,
        supported_files=len(files),
        unsupported_files=unsupported,
        already_imported=already_imported,
        files=file_info,
        summary_by_extension=summary_by_ext,
        total_size_mb=round(total_size / (1024 * 1024), 2),
    )


@router.post("/import", response_model=BatchImportResponse)
def batch_import_from_folder(
    data: BatchImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.create")),
):
    """
    Importa curriculos de uma pasta local/rede/drive em lote

    **Como funciona:**
    1. Escaneia a pasta por arquivos suportados (PDF, DOCX, TXT, imagens)
    2. Para cada arquivo:
       - Calcula hash SHA256 para deduplicacao
       - Pula se ja importado (quando skip_duplicates=true)
       - Copia para o storage interno
       - Cria registro no banco de dados
       - Enfileira processamento async (OCR, parsing, embedding)
    3. Retorna resultado detalhado de cada arquivo

    **Tipos de pasta suportados:**
    - Pasta local: `/home/user/curriculos`
    - Pasta de rede montada (SMB/CIFS): `/mnt/rede/rh/curriculos`
    - NFS share: `/mnt/nfs/curriculos`
    - Google Drive (via rclone): `/mnt/gdrive/Curriculos`
    - OneDrive (via rclone): `/mnt/onedrive/Curriculos`
    - Qualquer filesystem montado no servidor

    **Dica para montar drives compartilhados:**
    ```
    # Google Drive (usando rclone):
    rclone mount gdrive: /mnt/gdrive --daemon

    # Pasta de rede Windows (SMB):
    mount -t cifs //servidor/compartilhamento /mnt/rede -o user=usuario

    # NFS:
    mount -t nfs servidor:/export/curriculos /mnt/nfs
    ```

    **Requer permissao:** documents.create
    """
    folder = _resolve_and_validate_path(data.folder_path)
    files = _scan_files(folder, data.recursive, data.extensions)

    existing_hashes = _get_existing_hashes(db) if data.skip_duplicates else set()

    results: List[BatchImportFileResult] = []
    imported_count = 0
    skipped_count = 0
    error_count = 0

    for file_path in files:
        try:
            # Ler arquivo
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            file_io = io.BytesIO(file_bytes)

            # Calcular hash
            sha256_hash = storage_service.calculate_sha256(file_io)

            # Verificar duplicata
            if data.skip_duplicates and sha256_hash in existing_hashes:
                results.append(BatchImportFileResult(
                    filename=file_path.name,
                    path=str(file_path),
                    status="skipped_duplicate",
                    message="Arquivo ja importado (mesmo hash SHA256)",
                ))
                skipped_count += 1
                continue

            # Salvar no storage
            file_io.seek(0)
            relative_path, _ = storage_service.save_document(
                file_io, file_path.name, sha256_hash
            )

            # Detectar MIME
            mime_type = storage_service.get_mime_type(file_path.name)

            # Criar candidato se necessario
            candidate_id = data.candidate_id
            if not candidate_id:
                candidate = Candidate(
                    full_name="Aguardando processamento",
                    email=None,
                    company_id=current_user.company_id,
                )
                db.add(candidate)
                db.flush()
                candidate_id = candidate.id

            # Criar documento
            document = Document(
                candidate_id=candidate_id,
                original_filename=file_path.name,
                mime_type=mime_type,
                source_path=relative_path,
                sha256_hash=sha256_hash,
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            # Audit log
            audit = AuditLog(
                user_id=current_user.id,
                action="batch_import",
                entity="document",
                entity_id=document.id,
                metadata_json={
                    "filename": file_path.name,
                    "source_folder": str(folder),
                    "source_path": str(file_path),
                    "candidate_id": candidate_id,
                    "size": len(file_bytes),
                },
            )
            db.add(audit)
            db.commit()

            # Enfileirar processamento async
            try:
                from app.tasks.document_tasks import process_document_task
                process_document_task.delay(document.id, current_user.id)
            except Exception as task_err:
                logger.warning(f"Erro ao enfileirar processamento de {file_path.name}: {task_err}")

            existing_hashes.add(sha256_hash)
            imported_count += 1

            results.append(BatchImportFileResult(
                filename=file_path.name,
                path=str(file_path),
                status="imported",
                message="Importado com sucesso, processamento enfileirado",
                document_id=document.id,
                candidate_id=candidate_id,
            ))

            logger.info(f"Batch import: {file_path.name} -> document_id={document.id}")

        except Exception as e:
            error_count += 1
            results.append(BatchImportFileResult(
                filename=file_path.name,
                path=str(file_path),
                status="error",
                message=f"Erro: {str(e)}",
            ))
            logger.error(f"Batch import error for {file_path.name}: {e}")

    # Audit log do lote
    audit = AuditLog(
        user_id=current_user.id,
        action="batch_import_completed",
        entity="batch_import",
        entity_id=0,
        metadata_json={
            "folder": str(folder),
            "total": len(files),
            "imported": imported_count,
            "skipped": skipped_count,
            "errors": error_count,
        },
    )
    db.add(audit)
    db.commit()

    logger.info(
        f"Batch import complete: {data.folder_path} -> "
        f"{imported_count} imported, {skipped_count} skipped, {error_count} errors"
    )

    return BatchImportResponse(
        folder_path=str(folder),
        total_files=len(files),
        imported=imported_count,
        skipped_duplicates=skipped_count,
        errors=error_count,
        results=results,
    )


@router.post("/validate-path")
def validate_folder_path(
    data: FolderScanRequest,
    current_user: User = Depends(require_permission("documents.create")),
):
    """
    Valida se um caminho de pasta e acessivel

    Use para verificar rapidamente se o servidor consegue acessar
    a pasta antes de tentar escanear ou importar.

    Retorna informacoes sobre:
    - Se o caminho existe
    - Se e uma pasta
    - Se tem permissao de leitura
    - Espaco em disco disponivel
    - Tipo de filesystem montado

    **Requer permissao:** documents.create
    """
    path = Path(data.folder_path)

    result: Dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_directory": path.is_dir() if path.exists() else False,
        "is_readable": os.access(path, os.R_OK) if path.exists() else False,
        "is_writable": os.access(path, os.W_OK) if path.exists() else False,
    }

    if path.exists() and path.is_dir():
        # Info do filesystem
        try:
            statvfs = os.statvfs(path)
            result["disk_total_gb"] = round(
                statvfs.f_frsize * statvfs.f_blocks / (1024**3), 2
            )
            result["disk_free_gb"] = round(
                statvfs.f_frsize * statvfs.f_bavail / (1024**3), 2
            )
            result["disk_used_percent"] = round(
                100 * (1 - statvfs.f_bavail / statvfs.f_blocks), 1
            )
        except Exception:
            pass

        # Contar arquivos
        try:
            file_count = sum(1 for f in path.iterdir() if f.is_file())
            dir_count = sum(1 for f in path.iterdir() if f.is_dir())
            result["file_count"] = file_count
            result["directory_count"] = dir_count
        except Exception:
            pass

    # Sugestoes se nao existe
    if not path.exists():
        result["suggestions"] = [
            "Verifique se o caminho esta correto",
            "Se e pasta de rede, verifique se esta montada: mount | grep <ponto_montagem>",
            "Para montar pasta de rede SMB: mount -t cifs //servidor/share /mnt/destino -o user=usuario",
            "Para montar NFS: mount -t nfs servidor:/export /mnt/destino",
            "Para Google Drive: rclone mount gdrive: /mnt/gdrive --daemon",
            "Verifique permissoes: ls -la " + str(path.parent),
        ]

    return result


@router.get("/history")
def get_import_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.create")),
):
    """
    Retorna historico de importacoes em lote

    **Requer permissao:** documents.create
    """
    audits = db.query(AuditLog).filter(
        AuditLog.action.in_(["batch_import", "batch_import_completed"]),
        AuditLog.user_id == current_user.id,
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()

    return [
        {
            "id": a.id,
            "action": a.action,
            "metadata": a.metadata_json,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in audits
    ]
