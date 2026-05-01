# Code Roaster

AI-powered code review using the Anthropic API and FastAPI.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

## Run

```bash
uvicorn main:app --reload
```

## Usage

```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{"code": "def add(a,b):\n  return a+b", "language": "python"}'
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/review` | Submit code for review |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |
