"""
Servico de criptografia para protecao de dados pessoais (PII)

Implementa:
- Criptografia AES-256-GCM para dados em repouso
- Derivacao de chave com PBKDF2
- Rotacao de chaves
- Campo-a-campo encryption para dados sensiveis (CPF, RG, telefone, endereco)
- Conformidade LGPD

Uso:
    from app.services.encryption_service import encryption_service

    # Criptografar
    encrypted = encryption_service.encrypt("123.456.789-00")

    # Descriptografar
    original = encryption_service.decrypt(encrypted)
"""
import os
import base64
import json
import hashlib
import logging
from typing import Optional, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Tentar usar cryptography (recomendado)
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography nao disponivel. Instale: pip install cryptography. "
        "Criptografia de PII desabilitada."
    )


class EncryptionService:
    """
    Servico de criptografia para dados pessoais sensiveis

    Usa AES-256-GCM para:
    - Confidencialidade (criptografia)
    - Integridade (authentication tag)
    - Protecao contra replay (nonce unico)
    """

    NONCE_SIZE = 12  # 96 bits para AES-GCM
    KEY_SIZE = 32  # 256 bits
    SALT_SIZE = 16
    ITERATIONS = 100_000

    def __init__(self, master_key: Optional[str] = None):
        self._master_key = master_key or getattr(settings, 'secret_key', None)
        self._derived_key: Optional[bytes] = None
        self._salt: Optional[bytes] = None

    def _get_encryption_key(self) -> bytes:
        """Deriva chave de criptografia a partir da master key"""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography nao disponivel")

        if self._derived_key is None:
            if not self._master_key:
                raise ValueError("Master key nao configurada")

            # Usar hash da master key como salt deterministico
            # para que a mesma key sempre gere os mesmos resultados
            self._salt = hashlib.sha256(
                self._master_key.encode()
            ).digest()[:self.SALT_SIZE]

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=self.KEY_SIZE,
                salt=self._salt,
                iterations=self.ITERATIONS,
            )
            self._derived_key = kdf.derive(self._master_key.encode())

        return self._derived_key

    def encrypt(self, plaintext: str) -> str:
        """
        Criptografa texto usando AES-256-GCM

        Args:
            plaintext: Texto a criptografar

        Returns:
            String base64 com nonce + ciphertext + tag
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Criptografia indisponivel - retornando texto obfuscado")
            return self._obfuscate(plaintext)

        if not plaintext:
            return ""

        try:
            key = self._get_encryption_key()
            nonce = os.urandom(self.NONCE_SIZE)
            aesgcm = AESGCM(key)

            ciphertext = aesgcm.encrypt(
                nonce, plaintext.encode('utf-8'), None
            )

            # Concatenar nonce + ciphertext e encodar em base64
            encrypted = base64.b64encode(nonce + ciphertext).decode('utf-8')
            return f"enc:v1:{encrypted}"

        except Exception as e:
            logger.error(f"Erro na criptografia: {e}")
            raise ValueError("Falha ao criptografar dados")

    def decrypt(self, encrypted_text: str) -> str:
        """
        Descriptografa texto

        Args:
            encrypted_text: Texto criptografado (formato enc:v1:base64)

        Returns:
            Texto original
        """
        if not encrypted_text:
            return ""

        # Verificar se eh texto criptografado
        if not encrypted_text.startswith("enc:v1:"):
            # Texto nao criptografado ou obfuscado
            if encrypted_text.startswith("obf:"):
                return self._deobfuscate(encrypted_text)
            return encrypted_text

        if not CRYPTO_AVAILABLE:
            logger.warning("Criptografia indisponivel - impossivel descriptografar")
            raise RuntimeError("cryptography nao disponivel para descriptografia")

        try:
            key = self._get_encryption_key()
            data = base64.b64decode(encrypted_text[7:])  # Remove "enc:v1:"

            nonce = data[:self.NONCE_SIZE]
            ciphertext = data[self.NONCE_SIZE:]

            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)

            return plaintext.decode('utf-8')

        except Exception as e:
            logger.error(f"Erro na descriptografia: {e}")
            raise ValueError("Falha ao descriptografar dados")

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Criptografa um dicionario como JSON"""
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        return self.encrypt(json_str)

    def decrypt_dict(self, encrypted: str) -> Dict[str, Any]:
        """Descriptografa um dicionario"""
        json_str = self.decrypt(encrypted)
        return json.loads(json_str) if json_str else {}

    def mask_pii(self, value: str, field_type: str = "generic") -> str:
        """
        Mascara dados PII para exibicao

        Args:
            value: Valor a mascarar
            field_type: Tipo do campo (cpf, phone, email, generic)

        Returns:
            Valor mascarado
        """
        if not value:
            return ""

        if field_type == "cpf":
            # 123.456.789-00 -> ***.***.789-**
            digits = value.replace(".", "").replace("-", "").replace(" ", "")
            if len(digits) >= 11:
                return f"***.***{digits[6:9]}-**"
            return "***.***.***-**"

        elif field_type == "phone":
            # (11) 99999-1234 -> (11) *****-1234
            if len(value) >= 4:
                return value[:-4].replace(
                    value[-8:-4] if len(value) >= 8 else "", "****"
                ) + value[-4:]
            return "****"

        elif field_type == "email":
            if "@" in value:
                local, domain = value.split("@", 1)
                masked_local = local[0] + "***" + (local[-1] if len(local) > 1 else "")
                return f"{masked_local}@{domain}"
            return "***@***.com"

        else:
            # Generico: mostrar primeiros 2 e ultimos 2 chars
            if len(value) > 4:
                return value[:2] + "*" * (len(value) - 4) + value[-2:]
            return "****"

    @staticmethod
    def _obfuscate(text: str) -> str:
        """Fallback: obfuscacao simples quando cryptography nao esta disponivel"""
        encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
        return f"obf:{encoded}"

    @staticmethod
    def _deobfuscate(text: str) -> str:
        """Reverte obfuscacao simples"""
        if text.startswith("obf:"):
            return base64.b64decode(text[4:]).decode('utf-8')
        return text


# Instancia global
encryption_service = EncryptionService()
