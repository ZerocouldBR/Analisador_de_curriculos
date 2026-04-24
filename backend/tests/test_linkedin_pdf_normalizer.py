"""
Testes de regressao para PDFs exportados do LinkedIn.

O layout em duas colunas do LinkedIn costuma colocar Contato/Skills/Idiomas
antes do nome no texto extraido. Estes testes garantem que o normalizador
reconstrua os campos principais antes do parser/IA.
"""

from app.services.linkedin_pdf_normalizer import normalize_linkedin_pdf_text


def test_normalizes_linkedin_pdf_export_with_broken_url_and_sidebar():
    raw = """
    Contato
    candidato@example.com
    www.linkedin.com/in/candidato-teste-
    perfil-12345 (LinkedIn)
    www.portfolioexemplo.com
    (Personal)
    Principais competências
    Gestão de data center
    Workspace one
    Active Directory
    Languages
    English
    Certifications
    Android Enterprise Certified Expert
    Android Enterprise Professional
    Lucas Muller Rodrigues
    Senior Project Manager | IA & Transformação Digital | Liderando equipes
    São Leopoldo, Rio Grande do Sul, Brasil
    Resumo
    Possuo mais de 15 anos de experiência em Gestão de Projetos.
    Page 1 of 9
    """

    result = normalize_linkedin_pdf_text(raw)
    meta = result["metadata"]

    assert result["is_linkedin_pdf"] is True
    assert meta["name"] == "Lucas Muller Rodrigues"
    assert meta["email"] == "candidato@example.com"
    assert meta["linkedin"] == "https://www.linkedin.com/in/candidato-teste-perfil-12345"
    assert meta["portfolio"] == "https://www.portfolioexemplo.com"
    assert meta["headline"].startswith("Senior Project Manager")
    assert meta["location"] == "São Leopoldo, Rio Grande do Sul, Brasil"
    assert "Gestão de data center" in meta["skills"]
    assert "Workspace one" in meta["skills"]
    assert "Active Directory" in meta["skills"]
    assert "English" in meta["languages"]
    assert "Android Enterprise Certified Expert" in meta["certifications"]

    normalized_text = result["text"]
    assert "DADOS ESTRUTURADOS DETECTADOS - LINKEDIN PDF" in normalized_text
    assert "Nome: Lucas Muller Rodrigues" in normalized_text
    assert "LinkedIn: https://www.linkedin.com/in/candidato-teste-perfil-12345" in normalized_text


def test_strips_contact_label_glued_to_name_and_uses_hyperlink_uri():
    """Cenario real: extracao em duas colunas grudou 'Contato' na linha do
    nome e a URL do LinkedIn quebrou em duas linhas misturando texto da
    coluna direita. O PDF traz a URL real como anotacao de hiperlink,
    que precisa ter prioridade sobre o texto visivel reconstruido."""
    raw = """
    [HYPERLINK] https://www.linkedin.com/in/lucas-muller-rodrigues-9905931b
    [HYPERLINK] https://www.mullerrodrigues.com
    Contato Lucas Muller Rodrigues
    lucas@mullerrodrigues.com Senior Project Manager | IA & Transformação Digital
    www.linkedin.com/in/lucas-muller- equipes e inovação para resultados escaláveis
    rodrigues-9905931b (LinkedIn) São Leopoldo, Rio Grande do Sul, Brasil
    www.mullerrodrigues.com Resumo
    (Personal) Possuo mais de 15 anos de experiência em Gestão de Projetos.
    Principais competências
    Gestão de data center
    Workspace one
    Active Directory
    Languages
    English
    Certifications
    Android Enterprise Certified Expert
    """

    result = normalize_linkedin_pdf_text(raw)
    meta = result["metadata"]

    assert result["is_linkedin_pdf"] is True
    assert meta["name"] == "Lucas Muller Rodrigues"
    assert meta["linkedin"] == "https://www.linkedin.com/in/lucas-muller-rodrigues-9905931b"
    assert meta["portfolio"] == "https://www.mullerrodrigues.com"
    assert meta["email"] == "lucas@mullerrodrigues.com"
    # Marcadores [HYPERLINK] nao devem vazar para o texto normalizado.
    assert "[HYPERLINK]" not in result["text"]


def test_does_not_mark_plain_resume_without_linkedin_url_as_linkedin_pdf():
    raw = """
    Maria Silva
    Desenvolvedora Python
    Email: maria@example.com
    Experiência
    Empresa X
    """

    result = normalize_linkedin_pdf_text(raw)

    assert result["is_linkedin_pdf"] is False
    assert "DADOS ESTRUTURADOS DETECTADOS" not in result["text"]
