# Backend API (FastAPI)

## Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoint de saúde:

```
GET http://localhost:8000/api/health
```
