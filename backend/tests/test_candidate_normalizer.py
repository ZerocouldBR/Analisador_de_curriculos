"""
Tests for CandidateNormalizer: normalize, compute_hash, to_candidate_dict,
extract_text, _normalize_phone, _normalize_state, _normalize_email.
"""
import pytest

from app.services.sourcing.candidate_normalizer import CandidateNormalizer
from app.services.sourcing.provider_base import CandidateCanonicalProfile


# ================================================================
# normalize()
# ================================================================

class TestNormalize:
    def test_normalize_linkedin_style_payload(self):
        """Should normalize a LinkedIn-style payload with all fields."""
        raw = {
            "full_name": "  maria  silva  ",
            "email": "  MARIA@Example.COM  ",
            "phone": "+55 11 99999-1234",
            "headline": "Engenheira de Software Senior",
            "about": "Apaixonada por tecnologia",
            "city": "  sao paulo  ",
            "state": "Sao Paulo",
            "country": "Brasil",
            "linkedin_url": "https://linkedin.com/in/maria-silva",
            "current_company": "TechCorp",
            "current_role": "Senior Engineer",
            "seniority": "senior",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "certifications": ["AWS Solutions Architect"],
            "education": [{"degree": "BSc", "field": "Computer Science", "school": "USP"}],
            "languages": ["Portugues", "Ingles"],
            "experiences": [
                {"title": "Senior Engineer", "company": "TechCorp", "description": "Backend dev"}
            ],
            "external_id": "li-12345",
            "external_url": "https://linkedin.com/in/maria-silva",
            "confidence": 0.9,
        }

        profile = CandidateNormalizer.normalize(raw, "linkedin")

        assert profile.full_name == "Maria Silva"
        assert profile.email == "maria@example.com"
        assert profile.phone == "(11) 99999-1234"
        assert profile.headline == "Engenheira de Software Senior"
        assert profile.city == "Sao Paulo"
        assert profile.state == "SP"
        assert profile.country == "Brasil"
        assert profile.linkedin_url == "https://linkedin.com/in/maria-silva"
        assert profile.current_company == "TechCorp"
        assert profile.seniority == "senior"
        assert "Python" in profile.skills
        assert profile.certifications == ["AWS Solutions Architect"]
        assert len(profile.education) == 1
        assert profile.external_id == "li-12345"
        assert profile.confidence == 0.9

    def test_normalize_csv_style_payload(self):
        """Should normalize a CSV-style payload with comma-separated skills."""
        raw = {
            "name": "joao pereira",
            "email": "joao@mail.com",
            "phone": "21987654321",
            "city": "rio de janeiro",
            "state": "rj",
            "skills": "Java, Spring Boot, Docker",
            "languages": "Portugues, Espanhol",
        }

        profile = CandidateNormalizer.normalize(raw, "csv_import")

        assert profile.full_name == "Joao Pereira"
        assert profile.email == "joao@mail.com"
        assert profile.phone == "(21) 98765-4321"
        assert profile.city == "Rio De Janeiro"
        assert profile.state == "RJ"
        assert len(profile.skills) == 3
        assert "Java" in profile.skills
        assert len(profile.languages) == 2

    def test_normalize_manual_entry_minimal(self):
        """Should handle minimal manual entry with just a name."""
        raw = {
            "full_name": "ana costa",
        }

        profile = CandidateNormalizer.normalize(raw, "manual")

        assert profile.full_name == "Ana Costa"
        assert profile.email is None
        assert profile.phone is None
        assert profile.city is None
        assert profile.state is None
        assert profile.country == "Brasil"
        assert profile.skills == []
        assert profile.confidence == 0.5

    def test_normalize_missing_name_uses_name_field(self):
        """Should fall back to 'name' if 'full_name' is absent."""
        raw = {"name": "Pedro Santos", "email": "pedro@test.com"}
        profile = CandidateNormalizer.normalize(raw, "csv_import")
        assert profile.full_name == "Pedro Santos"

    def test_normalize_empty_name_returns_na(self):
        """Should return 'N/A' when no name is provided."""
        raw = {"email": "nobody@test.com"}
        profile = CandidateNormalizer.normalize(raw, "manual")
        assert profile.full_name == "N/A"

    def test_normalize_deduplicates_skills(self):
        """Should deduplicate skills (case-insensitive)."""
        raw = {
            "full_name": "Test",
            "skills": ["Python", "python", "PYTHON", "Java"],
        }
        profile = CandidateNormalizer.normalize(raw, "manual")
        skill_lower = [s.lower() for s in profile.skills]
        assert skill_lower.count("python") == 1
        assert "java" in skill_lower

    def test_normalize_url_without_protocol(self):
        """Should add https:// to URLs that lack protocol."""
        raw = {
            "full_name": "Test User",
            "linkedin_url": "linkedin.com/in/test",
            "github_url": "github.com/test",
        }
        profile = CandidateNormalizer.normalize(raw, "manual")
        assert profile.linkedin_url == "https://linkedin.com/in/test"
        assert profile.github_url == "https://github.com/test"

    def test_normalize_invalid_url(self):
        """Should return None for invalid URLs."""
        raw = {
            "full_name": "Test User",
            "linkedin_url": "not-a-url",
        }
        profile = CandidateNormalizer.normalize(raw, "manual")
        assert profile.linkedin_url is None

    def test_normalize_preserves_raw_data(self):
        """Should store raw_data on the profile."""
        raw = {"full_name": "Test", "custom_field": "value"}
        profile = CandidateNormalizer.normalize(raw, "manual")
        assert profile.raw_data == raw
        assert profile.raw_data["custom_field"] == "value"


# ================================================================
# compute_hash()
# ================================================================

class TestComputeHash:
    def test_same_input_same_hash(self):
        """Identical profiles should produce the same hash."""
        profile1 = CandidateCanonicalProfile(
            full_name="Maria Silva",
            email="maria@test.com",
            phone="(11) 99999-0000",
            city="Sao Paulo",
            state="SP",
        )
        profile2 = CandidateCanonicalProfile(
            full_name="Maria Silva",
            email="maria@test.com",
            phone="(11) 99999-0000",
            city="Sao Paulo",
            state="SP",
        )

        hash1 = CandidateNormalizer.compute_hash(profile1)
        hash2 = CandidateNormalizer.compute_hash(profile2)

        assert hash1 == hash2

    def test_different_input_different_hash(self):
        """Profiles with different data should produce different hashes."""
        profile1 = CandidateCanonicalProfile(
            full_name="Maria Silva",
            email="maria@test.com",
        )
        profile2 = CandidateCanonicalProfile(
            full_name="Maria Silva",
            email="maria.different@test.com",
        )

        hash1 = CandidateNormalizer.compute_hash(profile1)
        hash2 = CandidateNormalizer.compute_hash(profile2)

        assert hash1 != hash2

    def test_hash_ignores_raw_data(self):
        """Hash should be the same regardless of raw_data content."""
        profile1 = CandidateCanonicalProfile(
            full_name="Joao",
            raw_data={"source": "linkedin"},
        )
        profile2 = CandidateCanonicalProfile(
            full_name="Joao",
            raw_data={"source": "csv"},
        )

        assert CandidateNormalizer.compute_hash(profile1) == CandidateNormalizer.compute_hash(profile2)

    def test_hash_ignores_confidence(self):
        """Hash should be the same regardless of confidence value."""
        profile1 = CandidateCanonicalProfile(
            full_name="Test",
            confidence=0.3,
        )
        profile2 = CandidateCanonicalProfile(
            full_name="Test",
            confidence=0.99,
        )

        assert CandidateNormalizer.compute_hash(profile1) == CandidateNormalizer.compute_hash(profile2)

    def test_hash_ignores_external_id(self):
        """Hash should be the same regardless of external_id."""
        profile1 = CandidateCanonicalProfile(
            full_name="Test",
            external_id="ext-1",
        )
        profile2 = CandidateCanonicalProfile(
            full_name="Test",
            external_id="ext-2",
        )

        assert CandidateNormalizer.compute_hash(profile1) == CandidateNormalizer.compute_hash(profile2)

    def test_hash_is_sha256_hex(self):
        """Hash should be a 64-character hex string (SHA-256)."""
        profile = CandidateCanonicalProfile(full_name="Test")
        h = CandidateNormalizer.compute_hash(profile)

        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_deterministic_across_calls(self):
        """Hash should be deterministic - same result on repeated calls."""
        profile = CandidateCanonicalProfile(
            full_name="Maria",
            skills=["Python", "Java"],
        )

        hashes = [CandidateNormalizer.compute_hash(profile) for _ in range(5)]
        assert len(set(hashes)) == 1


# ================================================================
# to_candidate_dict()
# ================================================================

class TestToCandidateDict:
    def test_output_matches_candidate_model_fields(self):
        """Should return dict with Candidate model fields."""
        profile = CandidateCanonicalProfile(
            full_name="Maria Silva",
            email="maria@test.com",
            phone="(11) 99999-0000",
            city="Sao Paulo",
            state="SP",
            country="Brasil",
        )

        result = CandidateNormalizer.to_candidate_dict(profile)

        assert result["full_name"] == "Maria Silva"
        assert result["email"] == "maria@test.com"
        assert result["phone"] == "(11) 99999-0000"
        assert result["city"] == "Sao Paulo"
        assert result["state"] == "SP"
        assert result["country"] == "Brasil"

    def test_only_candidate_fields(self):
        """Should not include non-Candidate fields like skills, headline, etc."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            email="test@test.com",
            headline="Engineer",
            skills=["Python"],
            current_company="ACME",
        )

        result = CandidateNormalizer.to_candidate_dict(profile)

        assert "headline" not in result
        assert "skills" not in result
        assert "current_company" not in result
        assert set(result.keys()) == {"full_name", "email", "phone", "city", "state", "country"}

    def test_none_fields(self):
        """Should include None for missing optional fields."""
        profile = CandidateCanonicalProfile(full_name="Test")
        result = CandidateNormalizer.to_candidate_dict(profile)

        assert result["full_name"] == "Test"
        assert result["email"] is None
        assert result["phone"] is None
        assert result["city"] is None
        assert result["state"] is None
        assert result["country"] == "Brasil"


# ================================================================
# extract_text()
# ================================================================

class TestExtractText:
    def test_includes_name(self):
        """Should always include the full name."""
        profile = CandidateCanonicalProfile(full_name="Maria Silva")
        text = CandidateNormalizer.extract_text(profile)
        assert "Maria Silva" in text

    def test_includes_headline(self):
        """Should include headline."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            headline="Senior Python Developer",
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "Senior Python Developer" in text

    def test_includes_about(self):
        """Should include about text."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            about="10 years of experience in software engineering",
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "10 years of experience" in text

    def test_includes_role_and_company(self):
        """Should include current role and company."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            current_role="Tech Lead",
            current_company="BigCorp",
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "Cargo: Tech Lead" in text
        assert "Empresa: BigCorp" in text

    def test_includes_location(self):
        """Should include city and state."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            city="Sao Paulo",
            state="SP",
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "Cidade: Sao Paulo" in text
        assert "Estado: SP" in text

    def test_includes_skills(self):
        """Should include skills as comma-separated."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            skills=["Python", "Java", "Docker"],
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "Skills: Python, Java, Docker" in text

    def test_includes_certifications(self):
        """Should include certifications."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            certifications=["AWS SAA", "PMP"],
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "Certificacoes: AWS SAA, PMP" in text

    def test_includes_languages(self):
        """Should include languages."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            languages=["Portugues", "Ingles", "Espanhol"],
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "Idiomas: Portugues, Ingles, Espanhol" in text

    def test_includes_experiences(self):
        """Should include experience details."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            experiences=[
                {"title": "Engineer", "company": "TechCo", "description": "Built APIs"},
            ],
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "Engineer" in text
        assert "TechCo" in text
        assert "Built APIs" in text

    def test_includes_education(self):
        """Should include education details."""
        profile = CandidateCanonicalProfile(
            full_name="Test",
            education=[
                {"degree": "BSc", "field": "Computer Science", "school": "USP"},
            ],
        )
        text = CandidateNormalizer.extract_text(profile)
        assert "BSc" in text
        assert "Computer Science" in text
        assert "USP" in text

    def test_all_fields_combined(self):
        """Should produce newline-separated text with all fields."""
        profile = CandidateCanonicalProfile(
            full_name="Maria Silva",
            headline="Engineer",
            about="Backend specialist",
            current_role="Lead",
            current_company="Corp",
            city="SP",
            state="SP",
            skills=["Python"],
            certifications=["AWS"],
            languages=["PT"],
            experiences=[{"title": "Dev", "company": "X"}],
            education=[{"degree": "BSc", "school": "Y"}],
        )
        text = CandidateNormalizer.extract_text(profile)
        lines = text.split("\n")
        assert len(lines) >= 10


# ================================================================
# _normalize_phone()
# ================================================================

class TestNormalizePhone:
    def test_11_digit_mobile(self):
        """Standard 11-digit Brazilian mobile: (DD) 9XXXX-XXXX."""
        result = CandidateNormalizer._normalize_phone("11999991234")
        assert result == "(11) 99999-1234"

    def test_10_digit_landline(self):
        """10-digit Brazilian landline: (DD) XXXX-XXXX."""
        result = CandidateNormalizer._normalize_phone("1133334444")
        assert result == "(11) 3333-4444"

    def test_13_digit_with_country_code(self):
        """13-digit with +55: strip country code and format."""
        result = CandidateNormalizer._normalize_phone("5511999991234")
        assert result == "(11) 99999-1234"

    def test_formatted_with_dashes_and_parens(self):
        """Should handle formatted input like (11) 99999-1234."""
        result = CandidateNormalizer._normalize_phone("(11) 99999-1234")
        assert result == "(11) 99999-1234"

    def test_with_plus_and_spaces(self):
        """Should handle +55 11 99999-1234."""
        result = CandidateNormalizer._normalize_phone("+55 11 99999-1234")
        assert result == "(11) 99999-1234"

    def test_too_short_returns_none(self):
        """Phone with less than 8 digits should return None."""
        result = CandidateNormalizer._normalize_phone("1234")
        assert result is None

    def test_empty_returns_none(self):
        """Empty string should return None."""
        result = CandidateNormalizer._normalize_phone("")
        assert result is None

    def test_none_returns_none(self):
        """None input should return None."""
        result = CandidateNormalizer._normalize_phone(None)
        assert result is None

    def test_8_digit_number(self):
        """8-digit numbers should be returned as-is (stripped)."""
        result = CandidateNormalizer._normalize_phone("  3333-4444  ")
        assert result is not None


# ================================================================
# _normalize_state()
# ================================================================

class TestNormalizeState:
    def test_full_name_to_abbreviation(self):
        """Should convert full state name to 2-letter abbreviation."""
        assert CandidateNormalizer._normalize_state("Sao Paulo") == "SP"
        assert CandidateNormalizer._normalize_state("Rio de Janeiro") == "RJ"
        assert CandidateNormalizer._normalize_state("Minas Gerais") == "MG"

    def test_full_name_with_accents(self):
        """Should handle accented state names."""
        assert CandidateNormalizer._normalize_state("Ceara") == "CE"
        assert CandidateNormalizer._normalize_state("Ceará") == "CE"
        assert CandidateNormalizer._normalize_state("Paraná") == "PR"
        assert CandidateNormalizer._normalize_state("Pará") == "PA"

    def test_abbreviation_passthrough(self):
        """Already-abbreviated states should pass through."""
        assert CandidateNormalizer._normalize_state("SP") == "SP"
        assert CandidateNormalizer._normalize_state("rj") == "RJ"
        assert CandidateNormalizer._normalize_state("mg") == "MG"

    def test_none_returns_none(self):
        """None input should return None."""
        assert CandidateNormalizer._normalize_state(None) is None

    def test_empty_returns_none(self):
        """Empty string should return None."""
        assert CandidateNormalizer._normalize_state("") is None

    def test_whitespace_handling(self):
        """Should strip whitespace."""
        assert CandidateNormalizer._normalize_state("  SP  ") == "SP"
        assert CandidateNormalizer._normalize_state("  Bahia  ") == "BA"

    def test_unknown_state_passthrough(self):
        """Unknown state names should be returned as-is."""
        assert CandidateNormalizer._normalize_state("Unknown State") == "Unknown State"

    def test_distrito_federal(self):
        """Should handle Distrito Federal."""
        assert CandidateNormalizer._normalize_state("Distrito Federal") == "DF"
        assert CandidateNormalizer._normalize_state("DF") == "DF"


# ================================================================
# _normalize_email()
# ================================================================

class TestNormalizeEmail:
    def test_lowercase_and_strip(self):
        """Should lowercase and strip whitespace."""
        assert CandidateNormalizer._normalize_email("  USER@Example.COM  ") == "user@example.com"

    def test_valid_email(self):
        """Should return normalized valid email."""
        assert CandidateNormalizer._normalize_email("test@domain.com") == "test@domain.com"

    def test_invalid_email_no_at(self):
        """Should return None for email without @."""
        assert CandidateNormalizer._normalize_email("not-an-email") is None

    def test_none_returns_none(self):
        """None input should return None."""
        assert CandidateNormalizer._normalize_email(None) is None

    def test_empty_returns_none(self):
        """Empty string should return None."""
        assert CandidateNormalizer._normalize_email("") is None

    def test_whitespace_only_returns_none(self):
        """Whitespace-only string should return None."""
        assert CandidateNormalizer._normalize_email("   ") is None
