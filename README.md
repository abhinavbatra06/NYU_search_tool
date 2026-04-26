# NYU Research Scholar Search Tool

An AI-powered RAG search application for discovering NYU faculty research fit.

## Current Architecture

- Backend: FastAPI in [backend/main.py](backend/main.py)
- Frontend: Vite + React in [frontend](frontend)
- Vector Store: Local Chroma collection at `data/chroma_db`
- Search Pipeline: retrieval, ranking, and LLM answer synthesis in [backend/services](backend/services)

## Local Development

### 1) Python backend

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then run:

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Useful backend endpoints:

- `GET /health` - runtime health checks
- `GET /startup` - startup validation report
- `POST /api/v1/search` - protected search endpoint
- `GET /docs` - Swagger UI

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend default URL: `http://localhost:5173`
Backend default URL: `http://localhost:8000`

## Configuration Notes

The backend validates these required settings at startup:

- `OPENAI_API_KEY`
- `CHROMA_DIR` path (defaults to `data/chroma_db`)

Optional but recommended:

- `SUPABASE_URL`
- `SUPABASE_KEY`

Strict auth toggle:

- `REQUIRE_SUPABASE=true` forces Supabase config presence at startup.

## Docker Local Smoke Test

Build image from repo root:

```bash
docker build -t nyu-faculty-search .
```

Run container:

```bash
docker run -p 8000:8000 --env-file .env nyu-faculty-search
```

Verify:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/startup`

## Railway Deployment Checklist

1. Push repository with [Dockerfile](Dockerfile).
2. In Railway, set environment variables from `.env`.
3. Mount persistent volume for Chroma path at `/app/data/chroma_db`.
4. Confirm health endpoint and one search query post-deploy.

## Data Pipeline (Operator Workflow)

Ingestion remains manual for launch one:

1. [scripts/crawl.py](scripts/crawl.py)
2. [scripts/chunk_data.py](scripts/chunk_data.py)
3. [scripts/embed_chunks.py](scripts/embed_chunks.py)

## Documentation

- [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)
- [Plan.md](Plan.md)

