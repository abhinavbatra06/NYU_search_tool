# Search Tool Launch Plan

Build the current NYU faculty search prototype into a real internal web app with a better user experience, scalable authentication, and minimal infrastructure overhead. The recommended launch stack is: Node-based frontend for the product UI, FastAPI backend for the search API, Supabase Auth for managed user accounts and sessions, Railway for hosting the backend plus persisted Chroma data, and the existing local Chroma store under `data/chroma_db` for launch one. Keep the existing crawl/chunk/embed scripts as manual operator workflows for now.

The core product decision is to stop treating `app.py` as the long-term product surface. It remains useful as a temporary migration harness, but the real launch surface should become a Node UI backed by a proper API and managed auth.

## Architecture

1. **Frontend**: a small Node app, ideally Vite + React, responsible for login, query submission, and rendering results.
2. **Backend**: a thin FastAPI service that owns API routes, token validation, search orchestration, Chroma access, and LLM generation.
3. **Auth**: Supabase Auth as the application auth layer.
4. **Data store**: the existing Chroma collection in `data/chroma_db` remains the vector store for launch one.
5. **Ingestion**: `scripts/crawl.py`, `scripts/chunk_data.py`, and `scripts/embed_chunks.py` remain manual operator jobs.
6. **Hosting**: Railway is the primary deployment target; Render is the fallback; Cloud Run is deferred.

## Why This Stack

1. Railway fits the repo's current dependency on a writable local Chroma directory with the least hosting friction.
2. Supabase Auth gives managed users, sessions, and account flows without building auth from scratch.
3. A Node UI gives a materially better product surface than Streamlit while still being lightweight.
4. FastAPI gives a clean backend boundary so the UI, auth, and search system are not tangled together.
5. This path avoids premature complexity like managed vector DBs, multi-service orchestration, or custom auth systems.

## Hosting Decision

- **Primary**: Railway. Good fit for a single-container app with mounted persistent storage for `data/chroma_db`.
- **Secondary**: Render. Also workable for the same architecture, but not better for this repo.
- **Not recommended for launch one**: Cloud Run. Current Chroma-on-local-disk design is a poor fit for an ephemeral filesystem and would complicate refreshes.

## Auth Decision

1. **Primary auth layer**: Supabase Auth.
2. **Best-case auth path**: connect NYU identity into Supabase using OIDC or SAML if NYU supports app registration.
3. **Fallback auth path**: use Supabase-managed accounts and restrict access by invite list or allowed email domain until NYU SSO is available.
4. **Backend rule**: all protected API endpoints must validate Supabase-issued tokens.
5. **Launch-one auth rule**: do not build custom accounts, shared passwords, or a local user database.

## Product Boundary For Launch One

**Included**
- internal-user search experience
- managed login
- search API
- Node UI
- Railway deployment
- manual refresh workflow
- current Chroma store

**Excluded**
- scheduled crawling
- admin dashboard
- managed vector DB migration
- multi-instance scaling
- advanced analytics/observability stack
- custom auth/account systems

## Repo Structure

1. Keep `scripts/` as the operator surface for crawl, chunk, and embed jobs.
2. Keep `data/` in place, especially `data/chroma_db`, as persisted runtime storage.
3. Add `backend/` for FastAPI plus extracted search logic.
4. Add `frontend/` for the Node UI.
5. Keep `app.py` only as a migration harness during the transition.

## Proposed File Layout

### Backend
- `backend/main.py` — FastAPI entrypoint; mounts API routes, health checks, and static frontend assets.
- `backend/config.py` — environment loading for OpenAI, Supabase, Chroma path, and runtime settings.
- `backend/auth.py` — Supabase token validation and auth dependencies.
- `backend/schemas.py` — request and response models for the API.
- `backend/services/chroma.py` — Chroma initialization, collection lookup, and retrieval helpers.
- `backend/services/search.py` — main search orchestration extracted from `app.py` and `scripts/query.py`.
- `backend/services/llm.py` — prompt building, context assembly, and answer generation.
- `backend/services/ranking.py` — hybrid scoring and keyword helpers extracted from `scripts/query.py`.

### Frontend
- `frontend/package.json` — frontend manifest.
- `frontend/src/main.tsx` — frontend bootstrap.
- `frontend/src/App.tsx` — authenticated app shell.
- `frontend/src/lib/supabase.ts` — browser-side Supabase client.
- `frontend/src/lib/api.ts` — typed API calls to FastAPI.
- `frontend/src/components/LoginGate.tsx` — auth gate and login/session handling.
- `frontend/src/components/SearchForm.tsx` — query input and submit flow.
- `frontend/src/components/ResultsPanel.tsx` — answer rendering, ranked faculty display, and source links.

### Infrastructure & Docs
- `Dockerfile` — single-container build for backend plus compiled frontend.
- `.dockerignore` — build context cleanup.
- `README.md` — authoritative local dev, auth, deploy, and reindex runbook.

## Implementation Order

1. **Stabilize the runtime contract**
   - Files: `scripts/embed_chunks.py`, `data/chroma_db`
   - Work: confirm the collection name `faculty_search`, embedding model, metadata shape, and current Chroma path that the new backend must preserve.

2. **Extract the pure search core**
   - Files: `scripts/query.py`, `app.py`, new `backend/services/*` files
   - Work: move retrieval, deduping, ranking, context building, and LLM generation into backend service modules without changing behavior.

3. **Add backend configuration and startup checks**
   - Files: `backend/config.py`, `backend/services/chroma.py`, `backend/main.py`
   - Work: centralize config and fail fast for missing OpenAI key, missing Chroma path, or missing collection.

4. **Add the protected API surface**
   - Files: `backend/main.py`, `backend/auth.py`, `backend/schemas.py`
   - Work: create health and search endpoints, validate Supabase bearer tokens, and standardize request/response payloads.

5. **Build the frontend auth shell**
   - Files: `frontend/` package and auth-related source files
   - Work: implement Supabase login, logout, session restore, and protected app shell behavior.

6. **Build the frontend search experience**
   - Files: `frontend/src/components/*`, `frontend/src/lib/api.ts`
   - Work: add the query form, loading states, answer display, ranked faculty list, and source-link rendering.

7. **Package for single-container deployment**
   - Files: `Dockerfile`, `.dockerignore`, backend static serving setup, frontend build config
   - Work: compile frontend assets and serve them from FastAPI in the same container.

8. **Update docs and operator runbooks**
   - Files: `README.md` and optional docs
   - Work: document local setup, Supabase config, Railway deployment, volume mount expectations, and the manual reindex workflow.

9. **Deploy to Railway and validate**
   - Files: deployment config and environment only
   - Work: mount `data/chroma_db`, inject secrets, verify auth, and verify search end to end.

## File-Ordered Checklist

1. `scripts/embed_chunks.py` — Confirm runtime contract: collection name, embedding model, Chroma path, and metadata fields.
2. `scripts/query.py` — Extract reusable retrieval and ranking logic.
3. `app.py` — Remove long-term ownership of Chroma/OpenAI clients from the production UI path.
4. `requirements.txt` — Add backend runtime dependencies required by FastAPI and the new service shape.
5. `backend/*` — Implement configuration, auth, schemas, Chroma integration, search orchestration, and API routes.
6. `frontend/*` — Implement Supabase login flow, protected shell, query UI, and results rendering.
7. `Dockerfile` and `.dockerignore` — Package backend and compiled frontend into one deployable image.
8. `README.md` — Rewrite to reflect the real runtime and deployment architecture.

## Verification Gates

1. After search-core extraction, compare fixed sample queries against the current behavior in `app.py` and `scripts/query.py`.
2. After the API is added, verify health, valid search, invalid request, missing OpenAI key, missing Chroma path, and missing collection behavior.
3. After auth is added, verify unauthenticated API requests fail and authenticated Supabase-backed requests succeed.
4. After the frontend auth shell is added, verify login and session restore locally.
5. After the frontend search UI is added, verify an authenticated user can submit a query and see answer plus faculty results.
6. After Railway deployment, verify restart persistence against `data/chroma_db`.
7. After docs are written, run one full manual refresh via `scripts/crawl.py`, `scripts/chunk_data.py`, and `scripts/embed_chunks.py`, then confirm the deployed app still works.

## Open Dependency

1. NYU SSO support remains a separate institutional dependency.
2. If NYU can integrate with Supabase through OIDC or SAML, plug that in without changing the rest of the architecture.
3. If not, launch with Supabase-managed access and keep the rest of the architecture unchanged.

## Working Summary

We are building a proper productized version of the current faculty search prototype. The system keeps its current data pipeline and Chroma vector store for launch one, but replaces the Streamlit-first app shape with a Node frontend, FastAPI backend, Supabase-managed auth, and Railway deployment. The goal is to get a real internal app in front of users with minimal infra while still leaving a credible path to stronger auth, better data infrastructure, and broader scale later.