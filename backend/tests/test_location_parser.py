"""
Testes do parser de localizacao brasileiro.

Garante que extraimos 'Cidade, UF' corretamente nos formatos tipicos de
curriculos (LinkedIn PDF export, rotulos 'Endereco:', 'Cidade-UF', etc.)
e rejeitamos listas de skills e enderecos puros sem ancora geografica.
"""
from app.services.brazilian_validators import parse_brazilian_location
from app.services.resume_parser_service import ResumeParserService


def test_parses_linkedin_three_segment_location():
    got = parse_brazilian_location("São Leopoldo, Rio Grande do Sul, Brasil")
    assert got is not None
    assert got["city"] == "São Leopoldo"
    assert got["state"] == "RS"
    assert got["state_full"] == "Rio Grande Do Sul"
    assert got["country"] == "Brasil"
    assert got["display"] == "São Leopoldo, RS"


def test_parses_city_uf_short_form():
    assert parse_brazilian_location("São Paulo, SP")["display"] == "São Paulo, SP"
    assert parse_brazilian_location("Belo Horizonte - MG")["display"] == "Belo Horizonte, MG"
    assert parse_brazilian_location("Campinas/SP")["display"] == "Campinas, SP"
    assert parse_brazilian_location("Curitiba - PR")["display"] == "Curitiba, PR"


def test_parses_full_state_name_accent_insensitive():
    assert parse_brazilian_location("Curitiba, Paraná, Brasil")["state"] == "PR"
    assert parse_brazilian_location("Curitiba, Parana, Brasil")["state"] == "PR"
    assert parse_brazilian_location("Fortaleza, Ceara")["state"] == "CE"


def test_rejects_skill_lists_without_geographical_anchor():
    assert parse_brazilian_location("Python, Docker, AWS") is None
    assert parse_brazilian_location("Gestão, Liderança, Agile") is None
    assert parse_brazilian_location("SCRUM, PMP, ITIL") is None


def test_rejects_country_only_and_single_unknown_city():
    assert parse_brazilian_location("Brasil") is None
    assert parse_brazilian_location("Porto") is None
    assert parse_brazilian_location("Remoto") is None
    assert parse_brazilian_location("") is None


def test_strips_street_number_from_full_address():
    got = parse_brazilian_location("Rua Foo 123, Curitiba, Paraná, Brasil")
    assert got is not None
    assert got["city"] == "Curitiba"
    assert got["state"] == "PR"


def test_resume_parser_picks_header_location_not_job_location():
    """Linha de localizacao do cabecalho tem prioridade sobre a localizacao
    de uma vaga antiga na secao Experiencia."""
    text = (
        "Lucas Muller Rodrigues\n"
        "Senior Project Manager | IA & Transformação Digital\n"
        "São Leopoldo, Rio Grande do Sul, Brasil\n"
        "Resumo\n"
        "Mais de 15 anos de experiência.\n"
        "\n"
        "Experiência\n"
        "Empresa ACME - São Paulo, SP\n"
        "2019 - Atual\n"
    )
    info = ResumeParserService.extract_personal_info(text)
    assert info["location"] == "São Leopoldo, RS"


def test_resume_parser_returns_none_when_no_location():
    info = ResumeParserService.extract_personal_info(
        "Carlos Lima\ncarlos@ex.com\nPython, Docker, AWS\n"
    )
    assert info["location"] is None


def test_resume_parser_respects_labeled_address():
    info = ResumeParserService.extract_personal_info(
        "Pedro Alves\npedro@ex.com\nEndereço: Rua Foo 123, Curitiba, Paraná, Brasil\n"
    )
    assert info["location"] == "Curitiba, PR"
