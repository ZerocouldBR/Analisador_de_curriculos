import io
import re
from pathlib import Path
from typing import Optional, BinaryIO

# PDF
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# DOCX
try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# OCR (Tesseract)
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# HTML
from bs4 import BeautifulSoup


class TextExtractionService:
    """
    Serviço para extração de texto de diferentes formatos de documento

    Suporta:
    - PDF (via pdfplumber)
    - DOCX (via python-docx)
    - TXT, RTF (leitura direta)
    - Imagens (via Tesseract OCR)
    - HTML (via BeautifulSoup)
    """

    @staticmethod
    def extract_text(file_path: str, mime_type: str) -> str:
        """
        Extrai texto de um arquivo baseado no tipo MIME

        Args:
            file_path: Caminho para o arquivo
            mime_type: Tipo MIME do arquivo

        Returns:
            Texto extraído

        Raises:
            ValueError: Se formato não suportado ou biblioteca não disponível
        """
        path = Path(file_path)

        if mime_type == "application/pdf":
            return TextExtractionService._extract_from_pdf(path)

        elif mime_type in [
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]:
            return TextExtractionService._extract_from_docx(path)

        elif mime_type == "text/plain":
            return TextExtractionService._extract_from_txt(path)

        elif mime_type in ["text/html", "application/xhtml+xml"]:
            return TextExtractionService._extract_from_html(path)

        elif mime_type.startswith("image/"):
            return TextExtractionService._extract_from_image(path)

        else:
            raise ValueError(f"Formato não suportado: {mime_type}")

    @staticmethod
    def _extract_from_pdf(file_path: Path) -> str:
        """Extrai texto de PDF"""
        if not PDF_AVAILABLE:
            raise ValueError("pdfplumber não está instalado. Execute: pip install pdfplumber")

        text = ""

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"

            # Se não conseguiu extrair texto (pode ser PDF de imagem)
            if not text.strip() and OCR_AVAILABLE:
                print(f"PDF sem texto extraível, tentando OCR...")
                return TextExtractionService._extract_from_pdf_with_ocr(file_path)

            return text.strip()

        except Exception as e:
            raise ValueError(f"Erro ao extrair texto do PDF: {str(e)}")

    @staticmethod
    def _extract_from_pdf_with_ocr(file_path: Path) -> str:
        """Extrai texto de PDF usando OCR (para PDFs escaneados)"""
        if not PDF_AVAILABLE or not OCR_AVAILABLE:
            raise ValueError("Bibliotecas de OCR não disponíveis")

        text = ""

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    # Converter página para imagem
                    image = page.to_image(resolution=300).original

                    # Aplicar OCR
                    page_text = pytesseract.image_to_string(image, lang='por')
                    text += page_text + "\n\n"

            return text.strip()

        except Exception as e:
            raise ValueError(f"Erro ao extrair texto com OCR: {str(e)}")

    @staticmethod
    def _extract_from_docx(file_path: Path) -> str:
        """Extrai texto de DOCX"""
        if not DOCX_AVAILABLE:
            raise ValueError("python-docx não está instalado. Execute: pip install python-docx")

        try:
            doc = DocxDocument(file_path)

            text = []

            # Extrair parágrafos
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text.append(paragraph.text)

            # Extrair tabelas
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        text.append(" | ".join(row_text))

            return "\n".join(text)

        except Exception as e:
            raise ValueError(f"Erro ao extrair texto do DOCX: {str(e)}")

    @staticmethod
    def _extract_from_txt(file_path: Path) -> str:
        """Extrai texto de TXT"""
        try:
            # Tentar diferentes encodings
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue

            # Se nenhum encoding funcionou
            raise ValueError("Não foi possível detectar encoding do arquivo")

        except Exception as e:
            raise ValueError(f"Erro ao ler arquivo TXT: {str(e)}")

    @staticmethod
    def _extract_from_html(file_path: Path) -> str:
        """Extrai texto de HTML"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')

            # Remover scripts e estilos
            for script in soup(["script", "style"]):
                script.decompose()

            # Extrair texto
            text = soup.get_text()

            # Limpar espaços extras
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            raise ValueError(f"Erro ao extrair texto do HTML: {str(e)}")

    @staticmethod
    def _extract_from_image(file_path: Path) -> str:
        """Extrai texto de imagem usando OCR"""
        if not OCR_AVAILABLE:
            raise ValueError(
                "Bibliotecas de OCR não disponíveis. "
                "Execute: pip install pytesseract pillow\n"
                "E instale o Tesseract: https://github.com/tesseract-ocr/tesseract"
            )

        try:
            image = Image.open(file_path)

            # Aplicar OCR (português)
            text = pytesseract.image_to_string(image, lang='por')

            return text.strip()

        except Exception as e:
            raise ValueError(f"Erro ao extrair texto da imagem: {str(e)}")

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normaliza texto extraído

        - Remove espaços extras
        - Normaliza quebras de linha
        - Remove caracteres especiais problemáticos
        """
        # Remover caracteres de controle (exceto \n e \t)
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)

        # Normalizar quebras de linha
        text = re.sub(r'\r\n|\r', '\n', text)

        # Remover múltiplas quebras de linha
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remover espaços no início/fim de linhas
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Remover múltiplos espaços
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detecta idioma do texto (simplificado)

        Args:
            text: Texto para análise

        Returns:
            Código do idioma ('pt', 'en', etc.)
        """
        # Palavras comuns em português
        pt_words = ['de', 'e', 'o', 'a', 'para', 'com', 'em', 'é', 'são', 'como']

        # Palavras comuns em inglês
        en_words = ['the', 'and', 'of', 'to', 'for', 'with', 'in', 'is', 'are', 'as']

        text_lower = text.lower()

        pt_score = sum(1 for word in pt_words if f' {word} ' in text_lower)
        en_score = sum(1 for word in en_words if f' {word} ' in text_lower)

        if pt_score > en_score:
            return 'pt'
        elif en_score > pt_score:
            return 'en'
        else:
            return 'unknown'
