# Pipeline de Extracao de Curriculos

Este documento descreve como o sistema extrai dados estruturados de um curriculo
(PDF, DOCX, imagem com OCR) e como cada campo e decidido. Serve de referencia
para desenvolvedores e operadores que precisam depurar extracoes ruins.

---

## 1. Visao geral

```
           +-------------------+
 Arquivo ->| Extracao de texto |---+
           +-------------------+   |
                                   v
                        +-----------------------+
                        | Parser por regex      |  (resume_parser_service.py)
                        | - personal_info       |
                        | - experiencias        |
                        | - skills/certs/idioma |
                        +-----------+-----------+
                                    |
                                    v
                        +-----------------------+
                        | Extracao via LLM      |  (resume_ai_extraction_service.py)
                        | - Mesmos campos       |
                        | - Prompt + few-shot   |
                        +-----------+-----------+
                                    |
                                    v
                        +-----------------------+
                        | Reconciliacao         |  (validate_extraction)
                        | - Cross-validation    |
                        | - Escolha da fonte    |
                        | - Sanitizacao final   |
                        +-----------+-----------+
                                    |
                                    v
                          Dados enriquecidos
                          + telemetria de extracao
```

A IA e a **camada primaria** quando configurada; o regex funciona como fallback
e tambem como _cross-check_. A reconciliacao escolhe o melhor valor por campo.

---

## 2. Fontes possiveis por campo

| Campo | Fonte primaria | Fallback | Heuristicas aplicadas |
|---|---|---|---|
| `name` | IA (conf >= 0.7) | regex rotulado -> heuristica de primeiras linhas | rejeita enderecos, competencias, frases narrativas ("geram", "impacto", stopwords), exige palavras capitalizadas, maximo 6 palavras |
| `email` | IA ou regex (o primeiro que normaliza) | - | `normalize_email` (lowercase, strip) |
| `phone` | IA ou regex | bruto | `normalize_phone_br` (E.164) |
| `cpf` | IA ou regex | - | `is_valid_cpf` (checksum mod 11); invalidos sao descartados |
| `linkedin` | `_pick_best_linkedin` | texto bruto | afinidade slug vs nome do candidato |
| `github` | IA ou regex | - | prefixa `https://` se faltar |
| `location` | IA ou regex | - | - |
| `birth_date` | IA ou regex | bruto | `parse_birth_date` (dd/mm/yyyy) |
| `skills.*` | IA sanitizada | `categorize_skills(regex_skills)` | filtros de prosa/artefato + categorizacao heuristica |
| `languages` | IA sanitizada | regex sanitizado | canonicalizacao (Portugues, Ingles, ...) + dedup |
| `certifications` | IA sanitizada | regex sanitizado | mesmos filtros + min_len 4, max_len 100 |

---

## 3. Heuristicas de limpeza (sanitizacao)

Implementadas em `resume_parser_service.py` e reaproveitadas na sanitizacao da
saida da IA em `resume_ai_extraction_service.py`.

### 3.1. `_is_pdf_artifact(line)`
Detecta:
- `Page 1 of 9`, `Pagina 3 de 10`, `Page 1 / 9`
- `[TABELA]`, `[IMAGEM]`, `[FIGURA]`
- Linhas apenas com bullets/separadores (`---`, `———`)
- Strings vazias

### 3.2. `_looks_like_narrative(line)`
Classifica como narrativa (e portanto **nao eh** skill/cert) se:
- Tem mais de 8 palavras
- Termina com conjuncao/preposicao (`... e`, `... ou`, `... para`, `... com`, `... de`, ...)
- Termina com gerundio `-ando/-endo/-indo`
- Tem 2+ stopwords portuguesas narrativas (`que, para, com, pelo, sobre, ...`)
- Tem `em/na/no` no meio e >5 palavras
- Termina com ponto e tem 4+ palavras
- Comeca com letra minuscula e tem 3+ palavras

### 3.3. `_is_clean_list_item(text, max_len)`
Combina os anteriores:
- Tamanho entre `min_len` e `max_len`
- Nao e artefato de PDF
- Nao e cabecalho de secao (`Contato`, `Resumo`, ...)
- Nao e texto narrativo

Max length por categoria:
| Categoria | max_len |
|---|---|
| `skills.*` | 50 |
| `certifications` | 100 |
| `name` (via fallback de primeiras linhas) | 60 |

### 3.4. `_canonical_language` / `_canonical_level`
Mapeia variacoes para forma canonica em portugues (evita duplicatas):
- `portugues`, `português`, `portuguese` -> `Portugues`
- `ingles`, `inglês`, `english` -> `Ingles`
- `nativo`, `native`, `mother tongue` -> `Nativo`

### 3.5. `categorize_skills(list)` (fallback do regex)
Classifica cada skill em `technical / soft / tools / frameworks` por keyword match.
Prioridade: frameworks > tools > soft > technical (default).

---

## 4. Escolha de LinkedIn (`_pick_best_linkedin`)

Problema: PDFs do LinkedIn as vezes listam perfis relacionados ("Pessoas que
tambem viram"). Sem filtro o sistema pega o primeiro, que pode ser de outra
pessoa.

Solucao: extrai **todos** os perfis com `_find_all_linkedin_urls` e pontua
cada um pela sobrescricao de tokens entre o slug e o nome do candidato.

Exemplo:
- Nome: `Lucas Muller Rodrigues`
- Candidatos:
  - `linkedin.com/in/outra-pessoa` -> 0 tokens em comum
  - `linkedin.com/in/lucas-muller-rodrigues-9905931b` -> 3 tokens em comum
- Vencedor: o segundo.

Se todos empatarem em 0 (nenhum casa), retorna o primeiro (preserva a ordem
IA > regex > texto bruto).

---

## 5. Validacao de nome (`_validate_name`)

Ordem de decisao:

1. **IA valida + confianca >= 0.7** -> usa IA.
2. **IA e endereco ou competencia** -> tenta regex; se regex tambem falhar,
   usa heuristica de primeiras linhas.
3. **Sem nome da IA, regex valido** -> usa regex.
4. **Sem IA e sem regex** -> heuristica de primeiras linhas.
5. **IA com baixa confianca mas estrutura valida** -> usa IA com conf 0.5.
6. **Ultimo caso** -> heuristica de primeiras linhas. Se ainda assim nada,
   retorna `value: None` (nao propaga valor ruim).

Cross-validation extra: se o nome escolhido tem overlap com o email
abaixo de 30%, a confianca eh reduzida em 20% e uma nota e adicionada
(`name_email_match`).

---

## 6. Prompt da IA (few-shot)

`RESUME_EXTRACTION_PROMPT` em `resume_ai_extraction_service.py` inclui 5 exemplos
negativos/positivos cobrindo:

| Exemplo | Problema |
|---|---|
| A | Nome confundido com frase do resumo |
| B | Skills poluidas com prosa |
| C | LinkedIn de outra pessoa |
| D | Idiomas duplicados |
| E | Certificacoes com `Page X of Y`, `[TABELA]`, `Contato` |

O prompt tambem define **regras criticas** para cada campo e o formato JSON
esperado. Temperatura = 0.0 para maxima determinismo.

### Multi-pass

Se a IA falhar em gerar JSON parseavel, o codigo tenta de novo com texto
reduzido (24k -> 16k -> 10k chars) e `max_tokens` menor.

### Retry em erros transientes

Erros com marcadores `429, rate_limit, 503, 502, 504, timeout, connection`
disparam backoff exponencial (1s -> 2s -> 4s) antes do proximo attempt.

---

## 7. Telemetria

`validate_extraction` emite log estruturado:

```python
logger.info("resume_extraction.validate", extra={
    "event": "resume_extraction.validate",
    "name_source": "ai" | "regex" | "regex_fallback" | "heuristic_fallback" | "none",
    "name_confidence": 0.95,
    "linkedin_source": "ai" | "regex" | "text_fallback" | "none",
    "email_present": True,
    "phone_present": True,
    "skills_count": 12,
    "certifications_count": 4,
    "languages_count": 2,
    "validation_notes_count": 0,
})
```

Quando o nome cai no fallback heuristico ou retorna `None`, emite tambem
`resume_extraction.name_fallback` como **warning**. Use esse log para achar
CVs com extracao duvidosa em producao.

---

## 8. Como depurar uma extracao ruim

1. **Pegue os logs do processamento**: filtre por `resume_extraction.validate` e
   `resume_extraction.name_fallback` para o `document_id` / `candidate_id`.
2. **Cheque `validation_notes`** no payload retornado pelo pipeline. Elas dizem
   se a IA tentou colocar um endereco no campo nome, se CPF foi descartado por
   checksum, ou se o LinkedIn foi trocado.
3. **Reproduza localmente**:
   ```python
   from app.services.resume_parser_service import ResumeParserService
   from app.services.resume_ai_extraction_service import ResumeAIExtractionService

   text = open("seu_curriculo.txt").read()
   regex_data = ResumeParserService.parse_resume(text)
   ai_data = await ResumeAIExtractionService.extract_with_ai(text, regex_data)
   validated = await ResumeAIExtractionService.validate_extraction(
       regex_data, ai_data, text
   )
   print(validated["telemetry"])
   print(validated["validation_notes"])
   ```
4. **Rode os testes unitarios** antes de mudar a heuristica:
   ```bash
   cd backend
   pytest tests/test_resume_extraction.py -v
   ```

### Sintomas comuns

| Sintoma | Causa provavel | Onde corrigir |
|---|---|---|
| Nome e frase do meio do CV | Heuristica de primeiras linhas nao filtrou; IA retornou frase | `_validate_name`, `_extract_name_from_first_lines` |
| Skill com "... e", gerundio, ou ">8 palavras" | IA devolveu prosa; filtro da IA e fallback do regex nao pegaram | `_looks_like_narrative` (ajustar heuristica) |
| LinkedIn de pessoa errada | PDF tinha multiplos perfis; `_pick_best_linkedin` precisa dos tokens do nome | garantir que `validated_personal["name"]` ja foi definido antes |
| Idioma duplicado | Nao foi normalizado via `_canonical_language` | `_clean_languages` ou `extract_languages` |
| Page X of Y como certificacao | `_is_pdf_artifact` nao cobriu o formato | adicionar regex em `_is_pdf_artifact` |

---

## 9. Como adicionar um novo idioma

1. Em `resume_parser_service.py`, acrescente uma entrada em `_LANGUAGE_CANONICAL`:
   ```python
   'holandes': 'Holandes', 'dutch': 'Holandes', 'nederlands': 'Holandes',
   ```
2. A forma canonica deve seguir portugues sem acentos (ex.: `Holandes`,
   `Russo`, `Hindi`).
3. Adicione um teste em `tests/test_resume_extraction.py::TestLanguageCanonical`.
4. Sem mudanca no prompt da IA - a sanitizacao em `_clean_languages` usa o
   mesmo mapping.

---

## 10. Como versionar o prompt da IA

O prompt atual esta em `RESUME_EXTRACTION_PROMPT` (constante no modulo). Para
uma mudanca significativa (ex.: trocar o modelo ou introduzir novo campo):

1. Crie um commit separado para a mudanca do prompt.
2. Inclua no PR: exemplo de CV problematico antes, output da IA atual, output
   com o prompt novo.
3. Cheque `extraction_metadata.model_used` em amostras de producao antes e
   depois - mudanca de modelo (`gpt-4o-mini` -> `gpt-4o`) muda drasticamente
   o comportamento.
4. Futuramente: guardar o hash do prompt em cada extracao para audit.

---

## 11. Limites conhecidos

- Extracao de **experiencias** e **educacao** depende quase 100% da IA; o
  regex e muito simples.
- **Foto do candidato** e sinalizada como boolean `has_photo` mas nao
  extraida - fica como enrichment de LinkedIn.
- **Cross-validation email x nome** usa token overlap; nomes muito
  diferentes do email (ex.: "Maria Oliveira" com email "mosilva@...") podem
  gerar falso-positivo de "nao combina".
- **OCR** influencia diretamente a qualidade: PDF escaneado com OCR ruim
  vai produzir extracao ruim. Cheque `OCR_MIN_CONFIDENCE` no `.env`.
