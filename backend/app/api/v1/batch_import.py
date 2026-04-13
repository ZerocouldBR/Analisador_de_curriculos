"""
API de Importacao em Lote de Curriculos

Permite importar curriculos de:
- Pasta local no servidor
- Pasta de rede (SMB/CIFS montada)
- Drive compartilhado montado
"""
import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, Document, Candidate, AuditLog
from app.core.dependencies import require_permission
from app.core.config import settings
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch-import", tags=["batch-import"])

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf", ".jpg", ".jpeg", ".png", ".tiff", ".bmp"}


# ============================================
# Schemas
# ============================================

class FolderScanRequest(BaseModel):
    folder_path: str = Field(..., description="Caminho da pasta para escanear (local, rede, ou drive montado)")
    recursive: bool = Field(default=True, description="Incluir subpastas")


class FolderScanResult(BaseModel):
    folder_path: str
    exists: bool
    readable: bool
    files_found: int
    supported_files: int
    files: List[Dict[str, Any]] = []
    unsupported_files: List[str] = []
    errors: List[str] = []


class BatchImportRequest(BaseModel):
    folder_path: str = Field(..., description="Caminho da pasta com os curriculos")
    recursive: bool = Field(default=True, description="Incluir subpastas")
    skip_duplicates: bool = Field(default=True, description="Pular arquivos ja importados (hash SHA256)")
    candidate_id: Optional[int] = Field(None, description="Vincular todos a um candidato (None = criar novos)")
    max_files: int = Field(default=100, ge=1, le=500, description="Maximo de arquivos para importar")


class BatchImportFileResult(BaseModel):
    filename: str
    status: str  # imported, duplicate, error, skipped
    message: str
    document_id: Optional[int] = None
    candidate_id: Optional[int] = None


class BatchImportResponse(BaseModel):
    total_files: int
    imported: int
    duplicates: int
    errors: int
    skipped: int
    results: List[BatchImportFileResult]


# ============================================
# Helpers
# ============================================

def _validate_folder_path(folder_path: str) -> Path:
    """Valida e normaliza caminho da pasta"""
    path = Path(folder_path).resolve()

    # Bloquear caminhos perigosos
    blocked = ["/etc", "/bin", "/sbin", "/usr", "/boot", "/dev", "/proc", "/sys", "/root"]
    for b in blocked:
        if str(path).startswith(b):
            raise ValueError(f"Acesso ao diretorio '{b}' nao permitido por seguranca")

    return path


def _scan_files(folder: Path, recursive: bool) -> List[Path]:
    """Lista arquivos suportados em uma pasta"""
    files = []
    pattern = "**/*" if recursive else "*"

    for f in folder.glob(pattern):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(f)

    return sorted(files, key=lambda x: x.name)


# ============================================
# Endpoints
# ============================================

@router.post("/scan", response_model=FolderScanResult)
async def scan_folder(
    request: FolderScanRequest,
    current_user: User = Depends(require_permission("documents.create")),
):
    """
    Escaneia uma pasta e lista os curriculos encontrados

    Verifica:
    - Se a pasta existe e e acessivel
    - Quais arquivos sao curriculos suportados
    - Tamanho e tipo de cada arquivo

    **Requer permissao:** documents.create
    """
    logger.info(
        f"Escaneando pasta: {request.folder_path}",
        extra={"operation": "batch_scan", "user_id": current_user.id},
    )

    errors = []

    try:
        folder = _validate_folder_path(request.folder_path)
    except ValueError as e:
        return FolderScanResult(
            folder_path=request.folder_path,
            exists=False, readable=False,
            files_found=0, supported_files=0,
            errors=[str(e)],
        )

    if not folder.exists():
        return FolderScanResult(
            folder_path=str(folder),
            exists=False, readable=False,
            files_found=0, supported_files=0,
            errors=[f"Pasta nao encontrada: {folder}"],
        )

    if not os.access(str(folder), os.R_OK):
        return FolderScanResult(
            folder_path=str(folder),
            exists=True, readable=False,
            files_found=0, supported_files=0,
            errors=[f"Sem permissao de leitura: {folder}"],
        )

    # Contar todos os arquivos
    all_files = []
    pattern = "**/*" if request.recursive else "*"
    for f in folder.glob(pattern):
        if f.is_file():
            all_files.append(f)

    # Filtrar suportados
    supported = [f for f in all_files if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    unsupported = [f.name for f in all_files if f.suffix.lower() not in SUPPORTED_EXTENSIONS]

    file_info = []
    for f in supported[:200]:  # Limitar preview
        try:
            stat = f.stat()
            file_info.append({
                "name": f.name,
                "path": str(f),
                "size_kb": round(stat.st_size / 1024, 1),
                "extension": f.suffix.lower(),
                "modified": str(stat.st_mtime),
            })
        except Exception as e:
            errors.append(f"Erro ao ler {f.name}: {e}")

    return FolderScanResult(
        folder_path=str(folder),
        exists=True,
        readable=True,
        files_found=len(all_files),
        supported_files=len(supported),
        files=file_info,
        unsupported_files=unsupported[:50],
        errors=errors,
    )


@router.post("/import", response_model=BatchImportResponse)
async def batch_import_resumes(
    request: BatchImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents.create")),
):
    """
    Importa curriculos de uma pasta local/rede/drive

    Pipeline para cada arquivo:
    1. Valida formato e tamanho
    2. Calcula hash SHA256 (deduplicacao)
    3. Copia para storage interno
    4. Cria registro de Document
    5. Enfileira processamento (Celery)

    **Requer permissao:** documents.create
    """
    logger.info(
        f"Iniciando importacao em lote: {request.folder_path} (max={request.max_files})",
        extra={"operation": "batch_import", "user_id": current_user.id},
    )

    try:
        folder = _validate_folder_path(request.folder_path)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not folder.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pasta nao encontrada: {folder}")

    if not os.access(str(folder), os.R_OK):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Sem permissao de leitura: {folder}")

    files = _scan_files(folder, request.recursive)[:request.max_files]

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum arquivo suportado encontrado na pasta",
        )

    max_size = settings.max_upload_size_mb * 1024 * 1024
    results: List[BatchImportFileResult] = []
    imported = 0
    duplicates = 0
    errors = 0
    skipped = 0

    for file_path in files:
        try:
            # Validar tamanho
            file_size = file_path.stat().st_size
            if file_size > max_size:
                results.append(BatchImportFileResult(
                    filename=file_path.name,
                    status="skipped",
                    message=f"Arquivo excede {settings.max_upload_size_mb}MB ({round(file_size/1024/1024, 1)}MB)",
                ))
                skipped += 1
                continue

            if file_size == 0:
                results.append(BatchImportFileResult(
                    filename=file_path.name,
                    status="skipped",
                    message="Arquivo vazio",
                ))
                skipped += 1
                continue

            # Calcular hash
            with open(file_path, "rb") as f:
                sha256_hash = storage_service.calculate_sha256(f)

            # Verificar duplicata
            if request.skip_duplicates:
                existing = db.query(Document).filter(Document.sha256_hash == sha256_hash).first()
                if existing:
                    results.append(BatchImportFileResult(
                        filename=file_path.name,
                        status="duplicate",
                        message=f"Ja importado (doc_id={existing.id}, candidato_id={existing.candidate_id})",
                        document_id=existing.id,
                        candidate_id=existing.candidate_id,
                    ))
                    duplicates += 1
                    continue

            # Copiar para storage
            with open(file_path, "rb") as f:
                relative_path, _ = storage_service.save_document(f, file_path.name, sha256_hash)

            mime_type = storage_service.get_mime_type(file_path.name)

            # Criar candidato ou usar existente
            cand_id = request.candidate_id
            if not cand_id:
                candidate = Candidate(full_name="Aguardando processamento", email=None)
                db.add(candidate)
                db.flush()
                cand_id = candidate.id

            # Criar documento
            document = Document(
                candidate_id=cand_id,
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
                action="batch_import_document",
                entity="document",
                entity_id=document.id,
                metadata_json={
                    "filename": file_path.name,
                    "source_folder": str(folder),
                    "candidate_id": cand_id,
                    "size": file_size,
                },
            )
            db.add(audit)
            db.commit()

            # Enfileirar processamento
            try:
                from app.tasks.document_tasks import process_document_task
                process_document_task.delay(document.id, current_user.id)
            except Exception as e:
                logger.warning(f"Celery nao disponivel para {file_path.name}: {e}")

            results.append(BatchImportFileResult(
                filename=file_path.name,
                status="imported",
                message=f"Importado com sucesso (doc_id={document.id})",
                document_id=document.id,
                candidate_id=cand_id,
            ))
            imported += 1

            logger.info(
                f"Arquivo importado: {file_path.name} -> doc_id={document.id}",
                extra={"operation": "batch_import", "document_id": document.id},
            )

        except Exception as e:
            logger.error(f"Erro ao importar {file_path.name}: {e}", exc_info=True)
            results.append(BatchImportFileResult(
                filename=file_path.name,
                status="error",
                message=str(e),
            ))
            errors += 1

    # Audit log do lote
    audit = AuditLog(
        user_id=current_user.id,
        action="batch_import_completed",
        entity="batch_import",
        entity_id=0,
        metadata_json={
            "folder": str(folder),
            "total": len(files),
            "imported": imported,
            "duplicates": duplicates,
            "errors": errors,
            "skipped": skipped,
        },
    )
    db.add(audit)
    db.commit()

    logger.info(
        f"Importacao em lote concluida: {imported} importados, {duplicates} duplicados, {errors} erros",
        extra={"operation": "batch_import"},
    )

    return BatchImportResponse(
        total_files=len(files),
        imported=imported,
        duplicates=duplicates,
        errors=errors,
        skipped=skipped,
        results=results,
    )


@router.get("/supported-formats")
async def list_supported_formats(
    current_user: User = Depends(require_permission("documents.create")),
):
    """Lista formatos de arquivo suportados para importacao"""
    return {
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "max_file_size_mb": settings.max_upload_size_mb,
        "max_batch_size": 500,
        "tips": [
            "Formatos recomendados: PDF e DOCX (melhor extracao de texto)",
            "Imagens (JPG, PNG) usam OCR - confianca pode variar",
            "Pastas de rede devem estar montadas no sistema de arquivos",
            "Exemplo Linux: /mnt/share/curriculos ou /media/drive/rh",
            "Exemplo Windows: //servidor/compartilhamento (montado via CIFS/SMB)",
            "Google Drive: use rclone para montar em /mnt/gdrive",
        ],
    }
