"""
Testes unitarios para a extracao de dados de curriculos.

Foca em detectar regressoes nas heuristicas de limpeza (filtros de prosa,
artefatos de PDF, canonicalizacao de idiomas, categorizacao de skills) e
na validacao do nome/LinkedIn.

Os testes nao dependem de banco, LLM ou filesystem - sao puros.
"""
import pytest

from app.services.resume_parser_service import (
    ResumeParserService,
    _canonical_language,
    _canonical_level,
    _is_clean_list_item,
    _is_pdf_artifact,
    _looks_like_narrative,
    _looks_like_certification_item,
    categorize_skills,
)
from app.services.resume_ai_extraction_service import ResumeAIExtractionService


# ---------------------------------------------------------------------------
# Helpers de normalizacao
# ---------------------------------------------------------------------------

class TestPdfArtifactDetection:
    @pytest.mark.parametrize("line,expected", [
        ("Page 1 of 9", True),
        ("Pagina 3 de 10", True),
        ("Página 5 de 20", True),
        ("Page 1 / 9", True),
        ("2/10", True),
        ("[TABELA]", True),
        ("[IMAGEM]", True),
        ("[figura]", True),
        ("---", True),
        ("———", True),
        ("AWS Certified", False),
        ("Lucas Muller", False),
        ("", True),
    ])
    def test_detects_artifacts(self, line, expected):
        assert _is_pdf_artifact(line) is expected


class TestNarrativeDetection:
    @pytest.mark.parametrize("line,expected", [
        # Narrativa
        ("experiencia consolidada em PMO Leadership, estruturando", True),
        ("metodologias ageis e hibridas (PMI, SCRUM, Kanban, SAFe) e", True),
        ("Gestao de stakeholders em nivel executivo e C-level;", True),  # prosa com "em" no meio
        ("Atuei na implementacao de solucoes em cloud computing (AWS,", True),
        ("adequando frameworks a realidade de cada organizacao.", True),
        # Nao narrativa
        ("Python", False),
        ("AWS Cloud Services", False),
        ("Android Enterprise Certified Expert", False),
        ("PMP", False),
        ("Scrum Master PSM-I", False),
        ("Mestrado em Engenharia", False),  # prep "em" mas curta
    ])
    def test_distinguishes_narrative_from_items(self, line, expected):
        assert _looks_like_narrative(line) is expected


class TestCleanListItem:
    @pytest.mark.parametrize("text,expected", [
        # Skills limpos
        ("Python", True),
        ("JavaScript", True),
        ("AWS Cloud Services", True),
        ("Machine Learning", True),
        ("PMP", True),
        ("Scrum Master PSM-I", True),
        # Prosa/fragmentos
        ("experiencia consolidada em PMO Leadership, estruturando", False),
        ("metodologias ageis e hibridas (PMI, SCRUM, Kanban, SAFe) e", False),
        ("a integracao de equipes tecnicas e de negocio para garantir", False),
        # Artefatos
        ("Page 1 of 9", False),
        ("[TABELA]", False),
        # Cabecalhos
        ("Contato", False),
        ("Resumo", False),
        # Edge cases
        ("", False),
        (" ", False),
        ("A" * 200, False),  # muito longo
    ])
    def test_filters_correctly(self, text, expected):
        assert _is_clean_list_item(text, max_len=50) is expected


class TestLanguageCanonical:
    @pytest.mark.parametrize("raw,expected", [
        ("Portugues", "Portugues"),
        ("portugues", "Portugues"),
        ("português", "Portugues"),
        ("Portuguese", "Portugues"),
        ("portuguese", "Portugues"),
        ("Ingles", "Ingles"),
        ("inglês", "Ingles"),
        ("English", "Ingles"),
        ("Espanhol", "Espanhol"),
        ("Spanish", "Espanhol"),
        ("Alemao", "Alemao"),
        ("German", "Alemao"),
        ("Mandarim", "Chines"),
        ("Mandarin", "Chines"),
        # Invalido
        ("xyz", None),
        ("", None),
        (None, None),
    ])
    def test_normalizes_language_names(self, raw, expected):
        assert _canonical_language(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("Nativo", "Nativo"),
        ("Native", "Nativo"),
        ("Fluente", "Fluente"),
        ("Fluent", "Fluente"),
        ("Avancado", "Avancado"),
        ("avançado", "Avancado"),
        ("Advanced", "Avancado"),
        ("Intermediario", "Intermediario"),
        ("Intermediate", "Intermediario"),
        ("Basico", "Basico"),
        ("Basic", "Basico"),
        ("Iniciante", "Basico"),
        ("", "Nao especificado"),
        (None, "Nao especificado"),
        ("xyz", "Nao especificado"),
    ])
    def test_normalizes_levels(self, raw, expected):
        assert _canonical_level(raw) == expected


# ---------------------------------------------------------------------------
# Extratores (regex)
# ---------------------------------------------------------------------------

class TestExtractLanguages:
    def test_deduplicates_across_languages(self):
        text = """
        Languages

        Portuguese (Native)
        Portugues: Nativo
        English - Advanced
        Ingles Avancado
        Espanhol Intermediario
        """
        out = ResumeParserService.extract_languages(text)
        langs = {l["language"] for l in out}
        assert langs == {"Portugues", "Ingles", "Espanhol"}
        # Nenhuma duplicata
        assert len(out) == 3

    def test_returns_empty_for_text_without_languages(self):
        assert ResumeParserService.extract_languages("Hello world") == []


class TestExtractSkills:
    def test_filters_narrative_and_artifacts(self):
        text = """
        Habilidades
        Python
        AWS Cloud Services
        experiencia consolidada em PMO Leadership, estruturando
        Page 1 of 9
        [TABELA]
        metodologias ageis e hibridas (PMI, SCRUM, Kanban, SAFe) e
        Docker

        Experiencia
        """
        out = ResumeParserService.extract_skills(text)
        assert "Python" in out
        assert "AWS Cloud Services" in out
        assert "Docker" in out
        # Filtrados
        assert not any("estruturando" in s for s in out)
        assert not any("Page" in s for s in out)
        assert "[TABELA]" not in out

    def test_deduplicates_case_insensitive(self):
        text = """
        Habilidades
        Python
        python
        PYTHON

        Experiencia
        """
        out = ResumeParserService.extract_skills(text)
        assert len(out) == 1


class TestExtractCertifications:
    def test_filters_page_numbers_and_sections(self):
        text = """
        Certificacoes
        AWS Certified Solutions Architect - Associate
        Scrum Master Certified Professional
        Page 1 of 9
        [TABELA]
        Contato

        Experiencia
        """
        out = ResumeParserService.extract_certifications(text)
        assert "Scrum Master Certified Professional" in out
        assert "AWS Certified Solutions Architect - Associate" in out
        for bad in ("Page 1 of 9", "[TABELA]", "Contato"):
            assert bad not in out

    def test_rejects_narrative_pollution_in_certifications(self):
        text = """
        Certificacoes
        experiencia consolidada em PMO Leadership, estruturando
        Android Enterprise Certified Expert
        metodologias ageis e hibridas (PMI, SCRUM, Kanban, SAFe) e
        Android Enterprise Professional
        Conduzi projetos de transformacao digital end-to-end, aplicando
        Page 1 of 9
        [TABELA]
        """
        out = ResumeParserService.extract_certifications(text)
        assert "Android Enterprise Certified Expert" in out
        assert "Android Enterprise Professional" in out
        assert not any("estruturando" in c.lower() for c in out)
        assert not any("conduzi" in c.lower() for c in out)


class TestCertificationValidator:
    def test_accepts_real_certification_items(self):
        assert _looks_like_certification_item("PMP")
        assert _looks_like_certification_item("AWS Certified Solutions Architect - Associate")

    def test_rejects_dirty_non_cert_items(self):
        assert not _looks_like_certification_item("Conduzi projetos de transformação digital end-to-end, aplicando")
        assert not _looks_like_certification_item("www.linkedin.com/in/lucas-muller")


# ---------------------------------------------------------------------------
# Categorizacao de skills
# ---------------------------------------------------------------------------

class TestCategorizeSkills:
    def test_classifies_basic_categories(self):
        skills = [
            "Python",  # technical
            "React",  # framework
            "Docker",  # tool
            "Lideranca",  # soft
            "AWS",  # technical (fallback)
            "Git",  # tool
            "Django",  # framework
            "Comunicacao",  # soft
        ]
        out = categorize_skills(skills)
        assert "React" in out["frameworks"]
        assert "Django" in out["frameworks"]
        assert "Docker" in out["tools"]
        assert "Git" in out["tools"]
        assert "Lideranca" in out["soft"]
        assert "Comunicacao" in out["soft"]
        assert "Python" in out["technical"]
        assert "AWS" in out["technical"]

    def test_deduplicates(self):
        out = categorize_skills(["Python", "python", "PYTHON"])
        assert sum(len(v) for v in out.values()) == 1

    def test_empty_input(self):
        out = categorize_skills([])
        assert out == {"technical": [], "soft": [], "tools": [], "frameworks": []}


# ---------------------------------------------------------------------------
# Validacao de nome / LinkedIn
# ---------------------------------------------------------------------------

class TestNameValidation:
    def test_accepts_valid_name(self):
        result = ResumeAIExtractionService._validate_name(
            "Lucas Muller Rodrigues",
            None,
            0.92,
            "Lucas Muller Rodrigues\nSenior Project Manager",
        )
        assert result["value"] == "Lucas Muller Rodrigues"
        assert result["source"] == "ai"
        assert result["confidence"] >= 0.9

    def test_rejects_narrative_phrase_and_falls_back(self):
        raw = """Lucas Muller Rodrigues
        Senior Project Manager

        Resumo: Projetos que geram impacto mensuravel para o negocio.
        """
        result = ResumeAIExtractionService._validate_name(
            "geram impacto mensuravel para o negocio.",  # IA errou
            None,
            0.9,
            raw,
        )
        # Deve cair no fallback heuristico e achar o nome real
        assert result["value"] == "Lucas Muller Rodrigues"
        assert result["source"] != "ai"

    def test_returns_none_when_no_valid_name_found(self):
        raw = "Texto completamente generico sem nenhum nome proprio identificavel aqui."
        result = ResumeAIExtractionService._validate_name(
            "texto completamente generico",  # nao eh nome
            None,
            0.5,
            raw,
        )
        # Sem nome valido retorna None em vez de propagar dado ruim
        assert result["value"] is None
        assert result["source"] == "none"


class TestLinkedinPicker:
    def test_picks_first_when_single_url(self):
        urls = ["https://www.linkedin.com/in/lucas-muller"]
        assert (
            ResumeAIExtractionService._pick_best_linkedin("Lucas Muller", urls)
            == urls[0]
        )

    def test_prefers_slug_matching_candidate_name(self):
        urls = [
            "https://www.linkedin.com/in/outra-pessoa",
            "https://www.linkedin.com/in/lucas-muller-rodrigues",
        ]
        best = ResumeAIExtractionService._pick_best_linkedin(
            "Lucas Muller Rodrigues", urls
        )
        assert best == "https://www.linkedin.com/in/lucas-muller-rodrigues"

    def test_falls_back_to_first_when_no_affinity(self):
        urls = [
            "https://www.linkedin.com/in/aaa",
            "https://www.linkedin.com/in/bbb",
        ]
        best = ResumeAIExtractionService._pick_best_linkedin(
            "Carlos Silva Pereira", urls
        )
        # Nenhum casa - retorna o primeiro
        assert best == urls[0]

    def test_returns_none_for_empty_list(self):
        assert ResumeAIExtractionService._pick_best_linkedin("X", []) is None
        assert ResumeAIExtractionService._pick_best_linkedin("X", [None, None]) is None

    def test_rebuilds_linkedin_url_broken_across_lines(self):
        raw = """
        Contato
        www.linkedin.com/in/lucas-muller-
        rodrigues-9905931b
        """
        urls = ResumeAIExtractionService._find_all_linkedin_urls(raw)
        assert "https://www.linkedin.com/in/lucas-muller-rodrigues-9905931b" in urls

    def test_rebuilds_linkedin_url_broken_after_in_prefix(self):
        raw = """
        Contato
        www.linkedin.com/in/
        lucas-muller-rodrigues-9905931b
        """
        url = ResumeAIExtractionService._find_linkedin_in_text(raw)
        assert url == "https://www.linkedin.com/in/lucas-muller-rodrigues-9905931b"


# ---------------------------------------------------------------------------
# Bugs corrigidos (regressao)
# ---------------------------------------------------------------------------

class TestBugRegressions:
    def test_email_regex_rejects_pipe_in_tld(self):
        """Regressao do bug [A-Z|a-z] que aceitava pipe literal no TLD."""
        info = ResumeParserService.extract_personal_info(
            "Contato: teste@example.c|m"
        )
        # TLD invalido (pipe) nao deve ser aceito; pattern corrigido exige so letras
        assert info.get("email") != "teste@example.c|m"

    def test_email_regex_accepts_normal_email(self):
        info = ResumeParserService.extract_personal_info(
            "Email: lucas@mullerrodrigues.com"
        )
        assert info.get("email") == "lucas@mullerrodrigues.com"

    def test_birth_date_parsing_no_double_break(self):
        """Regressao do double break em extract_personal_info."""
        # O bug era unreachable code; o teste so confirma que o fluxo funciona
        info = ResumeParserService.extract_personal_info(
            "Data de nascimento: 15/03/1990"
        )
        assert info.get("birth_date") == "15/03/1990"

    def test_parser_extracts_name_in_linkedin_multicolumn_style(self):
        text = """
        Contato
        lucas@mullerrodrigues.com
        www.linkedin.com/in/lucas-muller-
        rodrigues-9905931b

        Lucas Muller Rodrigues
        Senior Project Manager | IA & Transformacao Digital
        """
        info = ResumeParserService.extract_personal_info(text)
        assert info.get("name") == "Lucas Muller Rodrigues"
        assert info.get("linkedin") == "https://www.linkedin.com/in/lucas-muller-rodrigues-9905931b"
