import os
import hashlib
from pathlib import Path
from typing import BinaryIO, Optional
import shutil
from datetime import datetime


class StorageService:
    """
    Serviço para gerenciamento de storage de arquivos

    Suporta armazenamento local (pode ser extendido para MinIO/S3)
    """

    def __init__(self, base_path: str = "/app/storage"):
        """
        Inicializa o serviço de storage

        Args:
            base_path: Caminho base para armazenamento
        """
        self.base_path = Path(base_path)
        self._ensure_directories()

    def _ensure_directories(self):
        """Cria estrutura de diretórios se não existir"""
        directories = [
            self.base_path,
            self.base_path / "documents",
            self.base_path / "temp",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calculate_sha256(file: BinaryIO) -> str:
        """
        Calcula hash SHA256 de um arquivo

        Args:
            file: Arquivo em modo binário

        Returns:
            Hash SHA256 em hexadecimal
        """
        sha256_hash = hashlib.sha256()

        # Ler arquivo em chunks para não sobrecarregar memória
        for chunk in iter(lambda: file.read(4096), b""):
            sha256_hash.update(chunk)

        # Reset file pointer
        file.seek(0)

        return sha256_hash.hexdigest()

    def save_document(
        self,
        file: BinaryIO,
        original_filename: str,
        sha256_hash: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Salva um documento no storage

        Args:
            file: Arquivo em modo binário
            original_filename: Nome original do arquivo
            sha256_hash: Hash SHA256 (calculado se não fornecido)

        Returns:
            Tuple (caminho_relativo, sha256_hash)
        """
        # Calcular hash se não fornecido
        if sha256_hash is None:
            sha256_hash = self.calculate_sha256(file)

        # Criar estrutura de diretórios baseada no hash (primeiros 2 caracteres)
        # Exemplo: hash abc123... -> documents/ab/c1/abc123...
        hash_prefix = sha256_hash[:2]
        hash_middle = sha256_hash[2:4]

        storage_dir = self.base_path / "documents" / hash_prefix / hash_middle
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Nome do arquivo: hash + extensão original
        file_extension = Path(original_filename).suffix
        filename = f"{sha256_hash}{file_extension}"
        file_path = storage_dir / filename

        # Salvar arquivo se ainda não existir (deduplicação)
        if not file_path.exists():
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file, f)

        # Retornar caminho relativo
        relative_path = str(file_path.relative_to(self.base_path))

        return relative_path, sha256_hash

    def _validate_path(self, resolved: Path) -> None:
        """Ensures the resolved path is inside base_path (prevents path traversal)."""
        try:
            resolved.relative_to(self.base_path.resolve())
        except ValueError:
            raise ValueError("Caminho inválido: acesso fora do diretório de storage não permitido")

    def get_absolute_path(self, relative_path: str) -> Path:
        """
        Converte caminho relativo para absoluto

        Args:
            relative_path: Caminho relativo ao base_path

        Returns:
            Caminho absoluto

        Raises:
            ValueError: Se caminho aponta para fora do base_path
        """
        absolute = (self.base_path / relative_path).resolve()
        self._validate_path(absolute)
        return absolute

    def file_exists(self, relative_path: str) -> bool:
        """Verifica se arquivo existe"""
        return self.get_absolute_path(relative_path).exists()

    def delete_file(self, relative_path: str) -> bool:
        """
        Remove um arquivo do storage

        Args:
            relative_path: Caminho relativo do arquivo

        Returns:
            True se arquivo foi removido
        """
        file_path = self.get_absolute_path(relative_path)

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    def get_file_size(self, relative_path: str) -> int:
        """
        Obtém tamanho do arquivo em bytes

        Args:
            relative_path: Caminho relativo do arquivo

        Returns:
            Tamanho em bytes
        """
        file_path = self.get_absolute_path(relative_path)

        if file_path.exists():
            return file_path.stat().st_size

        return 0

    def read_file(self, relative_path: str) -> bytes:
        """
        Lê o conteúdo de um arquivo

        Args:
            relative_path: Caminho relativo do arquivo

        Returns:
            Conteúdo do arquivo em bytes
        """
        file_path = self.get_absolute_path(relative_path)

        with open(file_path, "rb") as f:
            return f.read()

    @staticmethod
    def get_mime_type(filename: str) -> str:
        """
        Detecta tipo MIME baseado na extensão

        Args:
            filename: Nome do arquivo

        Returns:
            Tipo MIME
        """
        extension = Path(filename).suffix.lower()

        mime_types = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".rtf": "application/rtf",
            ".odt": "application/vnd.oasis.opendocument.text",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".html": "text/html",
        }

        return mime_types.get(extension, "application/octet-stream")

    @staticmethod
    def is_supported_format(filename: str) -> bool:
        """
        Verifica se formato é suportado

        Args:
            filename: Nome do arquivo

        Returns:
            True se formato é suportado
        """
        supported_extensions = {
            ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff",
            ".html"
        }

        extension = Path(filename).suffix.lower()
        return extension in supported_extensions


# Instância global do serviço de storage
storage_service = StorageService()
