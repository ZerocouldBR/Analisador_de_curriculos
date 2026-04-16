"""
Servico de extracao de foto do candidato a partir de PDFs e DOCX.

Estrategia:
- PDF: extrai todas imagens da primeira pagina, filtra por tamanho
  e proporcao tipica de foto de perfil, e salva a melhor candidata.
- DOCX: varre word/media, aplica mesmos filtros.
- Imagem direta (.jpg/.png): usa a propria imagem se tiver proporcao
  compativel com foto de perfil.

Quando OpenCV com Haar Cascades estiver disponivel, usa deteccao
facial para priorizar imagens que realmente contem o rosto do candidato.
"""
from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except (ImportError, AttributeError, Exception):
    CV2_AVAILABLE = False
    np = None  # type: ignore


# Filtros tipicos de foto de perfil
MIN_PHOTO_WIDTH = 80
MIN_PHOTO_HEIGHT = 80
MAX_PHOTO_WIDTH = 2000
MAX_PHOTO_HEIGHT = 2000
MIN_ASPECT_RATIO = 0.5   # retrato alongado
MAX_ASPECT_RATIO = 2.0   # paisagem moderada

# Pasta dentro do storage onde fotos serao salvas (relativa ao storage base)
PHOTOS_SUBDIR = "photos"


class PhotoExtractionService:
    """
    Extrai a foto do candidato de um curriculo.
    """

    @staticmethod
    def extract_photo(file_path: Path, mime_type: str) -> Optional[bytes]:
        """
        Extrai a melhor foto candidata do documento. Retorna bytes PNG/JPEG
        ou None se nenhuma imagem adequada for encontrada.
        """
        if not PIL_AVAILABLE:
            return None

        try:
            if mime_type == "application/pdf":
                return PhotoExtractionService._extract_from_pdf(file_path)
            elif mime_type in (
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ):
                return PhotoExtractionService._extract_from_docx(file_path)
            elif mime_type.startswith("image/"):
                return PhotoExtractionService._extract_from_image(file_path)
        except Exception as e:
            logger.warning(f"Falha ao extrair foto de {file_path.name}: {e}")
        return None

    @staticmethod
    def save_photo(
        photo_bytes: bytes,
        candidate_id: int,
        storage_base: Path,
    ) -> Optional[str]:
        """
        Salva bytes da foto no storage e retorna o caminho relativo
        (ex: photos/42/profile.jpg).
        """
        if not photo_bytes:
            return None
        try:
            photos_dir = storage_base / PHOTOS_SUBDIR / str(candidate_id)
            photos_dir.mkdir(parents=True, exist_ok=True)

            img = Image.open(io.BytesIO(photo_bytes))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Redimensionar se muito grande (mantem aspecto)
            max_dim = 800
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.LANCZOS)

            out_path = photos_dir / "profile.jpg"
            img.save(out_path, format="JPEG", quality=85, optimize=True)

            return str(out_path.relative_to(storage_base))
        except Exception as e:
            logger.warning(f"Falha ao salvar foto do candidato {candidate_id}: {e}")
            return None

    # ================================================================
    # PDF
    # ================================================================

    @staticmethod
    def _extract_from_pdf(file_path: Path) -> Optional[bytes]:
        if not PDF_AVAILABLE:
            return None

        best: Optional[Tuple[int, bytes]] = None

        try:
            with pdfplumber.open(file_path) as pdf:
                # Priorizar primeiras 2 paginas (fotos em curriculos aparecem cedo)
                for page_idx, page in enumerate(pdf.pages[:2]):
                    try:
                        # Renderizar a pagina em alta resolucao e extrair imagens embutidas
                        images = page.images or []
                        for img in images:
                            x0 = img.get("x0", 0)
                            y0 = img.get("top", 0)
                            x1 = img.get("x1", page.width)
                            y1 = img.get("bottom", page.height)

                            width_pts = x1 - x0
                            height_pts = y1 - y0
                            if width_pts < 30 or height_pts < 30:
                                continue

                            # Renderizar apenas a regiao da imagem em alta resolucao
                            try:
                                cropped = page.crop((x0, y0, x1, y1))
                                rendered = cropped.to_image(resolution=200).original
                            except Exception:
                                continue

                            if rendered is None:
                                continue

                            buf = io.BytesIO()
                            rendered.save(buf, format="PNG")
                            data = buf.getvalue()

                            score = PhotoExtractionService._score_image(
                                rendered, bonus_first_page=(page_idx == 0)
                            )
                            if score > 0:
                                if best is None or score > best[0]:
                                    best = (score, data)
                    except Exception as e:
                        logger.debug(f"Erro ao processar imagens da pagina {page_idx + 1}: {e}")
                        continue

                # Fallback: se nao achou imagem embutida, renderizar a primeira pagina inteira
                # e tentar detectar face nela
                if best is None and CV2_AVAILABLE and pdf.pages:
                    try:
                        page_img = pdf.pages[0].to_image(resolution=200).original
                        face_crop = PhotoExtractionService._crop_face(page_img)
                        if face_crop is not None:
                            buf = io.BytesIO()
                            face_crop.save(buf, format="PNG")
                            best = (100, buf.getvalue())
                    except Exception as e:
                        logger.debug(f"Fallback face detection falhou: {e}")

        except Exception as e:
            logger.debug(f"Erro ao extrair fotos do PDF {file_path.name}: {e}")

        return best[1] if best else None

    # ================================================================
    # DOCX
    # ================================================================

    @staticmethod
    def _extract_from_docx(file_path: Path) -> Optional[bytes]:
        best: Optional[Tuple[int, bytes]] = None
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                image_files = [
                    f for f in zf.namelist()
                    if f.startswith("word/media/")
                    and any(f.lower().endswith(ext) for ext in
                            (".png", ".jpg", ".jpeg", ".bmp"))
                ]
                for img_file in image_files:
                    try:
                        data = zf.read(img_file)
                        img = Image.open(io.BytesIO(data))
                        score = PhotoExtractionService._score_image(img)
                        if score > 0 and (best is None or score > best[0]):
                            best = (score, data)
                    except Exception as e:
                        logger.debug(f"Erro ao analisar {img_file}: {e}")
                        continue
        except Exception as e:
            logger.debug(f"Erro ao abrir DOCX como zip: {e}")

        return best[1] if best else None

    # ================================================================
    # Imagem direta
    # ================================================================

    @staticmethod
    def _extract_from_image(file_path: Path) -> Optional[bytes]:
        try:
            img = Image.open(file_path)
            if PhotoExtractionService._score_image(img) > 0:
                buf = io.BytesIO()
                fmt = img.format or "JPEG"
                if fmt not in ("JPEG", "PNG"):
                    fmt = "JPEG"
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                img.save(buf, format=fmt)
                return buf.getvalue()
        except Exception as e:
            logger.debug(f"Erro ao processar imagem direta {file_path.name}: {e}")
        return None

    # ================================================================
    # Heuristicas
    # ================================================================

    @staticmethod
    def _score_image(img: Image.Image, bonus_first_page: bool = False) -> int:
        """
        Pontua uma imagem como candidata a foto de perfil.
        Retorna 0 se nao for candidata valida.
        """
        try:
            w, h = img.size
        except Exception:
            return 0

        if w < MIN_PHOTO_WIDTH or h < MIN_PHOTO_HEIGHT:
            return 0
        if w > MAX_PHOTO_WIDTH or h > MAX_PHOTO_HEIGHT:
            # Imagens muito grandes (ex: paginas inteiras) nao sao fotos
            return 0

        aspect = w / h if h else 0
        if aspect < MIN_ASPECT_RATIO or aspect > MAX_ASPECT_RATIO:
            return 0

        # Base: area da imagem (fotos de perfil costumam ser medianas)
        score = min(w * h, 1000 * 1000) // 1000

        # Bonus por proporcao proxima de 1 (foto quadrada ou retangular 3:4/4:3)
        if 0.7 <= aspect <= 1.5:
            score += 50

        if bonus_first_page:
            score += 30

        # Bonus forte se detectar face
        if CV2_AVAILABLE:
            try:
                if PhotoExtractionService._has_face(img):
                    score += 500
            except Exception:
                pass

        return int(score)

    @staticmethod
    def _has_face(img: Image.Image) -> bool:
        if not CV2_AVAILABLE:
            return False
        try:
            arr = np.array(img.convert("RGB"))
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                return False
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
            return len(faces) > 0
        except Exception:
            return False

    @staticmethod
    def _crop_face(img: Image.Image) -> Optional[Image.Image]:
        """Detecta uma face na imagem e retorna apenas a regiao cortada."""
        if not CV2_AVAILABLE:
            return None
        try:
            arr = np.array(img.convert("RGB"))
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                return None
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50))
            if len(faces) == 0:
                return None
            # Pegar a maior face
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            # Expandir bounding box para incluir um pouco de contexto
            pad_w = int(w * 0.3)
            pad_h = int(h * 0.4)
            x0 = max(0, x - pad_w)
            y0 = max(0, y - pad_h)
            x1 = min(arr.shape[1], x + w + pad_w)
            y1 = min(arr.shape[0], y + h + pad_h)
            crop = img.crop((x0, y0, x1, y1))
            return crop
        except Exception:
            return None
