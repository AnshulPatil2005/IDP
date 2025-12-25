# Titan-Guidance

Titan-Guidance is an automated document analysis platform for contracts and legal documents. It combines FastAPI, Celery, Redis, Qdrant, MinIO, and an LLM provider (OpenRouter by default) to run an OCR -> embeddings -> clause extraction -> deadlines -> rules -> summary -> guidance pipeline and expose results over HTTP.

This README is intentionally exhaustive and mirrors the current state of the repository, including placeholders and stubbed modules.

## High-level architecture

- Frontend: static HTML served by Nginx (Docker Compose service `frontend`)
- API: FastAPI app (`backend/app/main.py`)
- Worker: Celery worker for background pipeline (`backend/app/workers/celery_app.py`)
- Storage: MinIO (S3-compatible) and local filesystem fallbacks
- Vector store: Qdrant
- LLM: OpenRouter (OpenAI-compatible HTTP API), optional Ollama
- Database: SQLAlchemy (SQLite default, Postgres supported)

## Runtime services (Docker Compose)

Defined in `docker-compose.yml`:

- `redis`
  - Image: `redis:7`
  - Port: `6379:6379`
  - AOF enabled via `--appendonly yes`
  - Healthcheck: `redis-cli ping`
- `qdrant`
  - Image: `qdrant/qdrant:latest`
  - Ports: `6333` (HTTP), `6334` (gRPC optional)
  - Volume: `qdrant_storage:/qdrant/storage`
  - Healthcheck: TCP check to `127.0.0.1:6333`
- `minio`
  - Image: `minio/minio:latest`
  - Ports: `9000` (API), `9001` (console)
  - Env: `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
  - Volume: `minio_storage:/data`
  - Healthcheck: `http://localhost:9000/minio/health/live`
- `api`
  - Build: `backend/Dockerfile`, image `idp-backend:dev`
  - Port: `8000:8000`
  - Volume mounts: `./backend:/app`, `./configs:/configs`
  - Env: Redis, Celery, OpenRouter, MinIO settings, `PYTHONPATH=/app`
  - Command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - Depends on: `redis`, `qdrant`, `minio`
- `worker`
  - Image: `idp-backend:dev`
  - Volume mounts: same as `api`
  - Command: `celery -A app.workers.celery_app:celery worker -l info`
  - Depends on: `redis`, `qdrant`, `minio`, `api`
- `frontend`
  - Image: `nginx:alpine`
  - Port: `3000:80`
  - Volume: `./frontend:/usr/share/nginx/html:ro`
  - Depends on: `api`

Named volumes:

- `qdrant_storage` (local driver)
- `minio_storage` (local driver)

## Quick start (Docker)

1) Copy env file:

```sh
cp .env.example .env
```

2) Set `OPENROUTER_API_KEY` in `.env` (required for LLM).

3) Start services:

```sh
docker compose up --build
```

4) Open:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Frontend: `http://localhost:3000`
- MinIO console: `http://localhost:9001`

## Local development (without Docker)

The repository does not include a local dev script; run services manually:

1) Start dependencies (Redis, Qdrant, MinIO) however you prefer.
2) Install backend deps:

```sh
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) Run API:

```sh
uvicorn app.main:app --reload
```

4) Run worker:

```sh
celery -A app.workers.celery_app:celery worker -l info
```

5) Serve frontend (optional):

- Use Docker for Nginx, or open `frontend/index.html` directly in a browser.

## Environment variables and defaults

From `.env.example` and code defaults:

LLM:

- `OPENROUTER_API_KEY` (required for OpenRouter)
- `LLM_PROVIDER` (default `openrouter`, alternative `ollama`)
- `LLM_MODEL` (default `deepseek/deepseek-chat-v3-0324:free`)
- `OLLAMA_BASE` (default `http://localhost:11434`, used only if `LLM_PROVIDER=ollama`)

MinIO / S3:

- `MINIO_ENDPOINT` (default `minio:9000`)
- `MINIO_ACCESS_KEY` (default `minioadmin`)
- `MINIO_SECRET_KEY` (default `minioadmin`)
- `MINIO_BUCKET` (default `docs`)
- `MINIO_SECURE` (default `false`)

Vector store:

- `QDRANT_URL` (default `http://qdrant:6333`)
- `QDRANT_COLLECTION` (present in `.env.example` but not used in code; collection name is hard-coded to `spans`)

Celery / Redis:

- `REDIS_URL` (default `redis://redis:6379/0`)
- `CELERY_BROKER_URL` (defaults to `REDIS_URL` if unset)
- `CELERY_RESULT_BACKEND` (defaults to broker URL if unset)
- `CELERY_TASK_SOFT_TIME_LIMIT` (present in `.env.example`, not used in code)
- `CELERY_TASK_TIME_LIMIT` (present in `.env.example`, not used in code)

API:

- `API_KEY` (if set, `POST /ingest` requires `x-api-key` header)

Database:

- `DATABASE_URL` (default `sqlite:///./titan.db`)

Rules:

- `RULES_PATH` (default `/configs/rules.yaml` for `POST /rules/validate`)

Logging:

- `LOG_LEVEL` (default `INFO`, used in `backend/app/utils/logger.py`)

## Data flow and pipeline

The ingestion pipeline is orchestrated via Celery chain tasks in `backend/app/services/pipeline.py`:

1) `task_ocr` -> `app.services.ocr.run`
2) `task_tables` -> `app.services.tables.run`
3) `task_emb` -> `app.services.embeddings.run`
4) `task_clauses` -> `app.services.clauses.run`
5) `task_deadlines` -> `app.services.deadlines.run`
6) `task_rules` -> `app.services.rules.run`
7) `task_summary` -> `app.services.summarizer.run`
8) `task_compose` -> `app.services.guidance.compose`

Each task returns a small status dict; the chain is triggered by `enqueue_ingestion(doc_id)` in `backend/app/services/pipeline.py`.

Important storage expectations:

- The OCR service tries to fetch the original PDF from MinIO under key `"{doc_id}/original.pdf"`.
- The ingest API uploads the file to MinIO under the object name `"{doc_id}{ext}"`.
- This means OCR will not find the uploaded file unless you also store a copy at `doc_id/original.pdf` or update the ingest/ocr conventions.

## Backend API

Base app: `backend/app/main.py`

- CORS allows `http://localhost:3000` and `http://127.0.0.1:3000`
- Tables are auto-created on startup via `Base.metadata.create_all(bind=engine)`
- Routes are registered from `backend/app/routes/*`

Endpoints:

- `GET /`
  - Health check, returns `{"ok": true}`
- `POST /ingest`
  - Uploads a PDF to MinIO
  - Creates a `Document` row with status `uploaded`
  - Enqueues Celery pipeline
  - Returns: `{"doc_id": "...", "status": "queued", "bucket": "...", "object": "..."}`
  - Optional API key gate: `x-api-key` if `API_KEY` is set
- `GET /docs/{doc_id}/clauses`
  - Returns `ClauseOut[]` (see schemas)
  - Converts `Clause.type` to `ClauseTypeEnum` (raises if value is not in enum)
- `GET /docs/{doc_id}/guidance`
  - Returns `GuidanceItemOut[]`
  - Attempts to link evidence chips to `PolicyFire` for severity
- `GET /docs/{doc_id}/deadlines.ics`
  - Returns `text/calendar` payload (iCalendar)
- `POST /ask`
  - Request body: `AskRequest`
  - Response: `AskAnswer`
  - Returns HTTP 428 if confidence < 0.6 or answer has no citations
- `POST /rules/validate?doc_id=...`
  - Loads YAML spec from `RULES_PATH` (defaults to `/configs/rules.yaml`)
  - Evaluates rules against clauses in DB
  - Persists `PolicyFire` rows and returns match list

## Schemas (Pydantic)

`backend/app/schemas/common.py`

- `TextSpan`: `{doc_id, page, start, end}`
- `Risk`: alias for `str`

`backend/app/schemas/clause.py`

- `ClauseTypeEnum`: enum of clause types
- `ClauseOut`: `{id, doc_id, type, parties, text_span, text, confidence, normalized}`

`backend/app/schemas/guidance.py`

- `GuidanceItemOut`: `{id, doc_id, title, what_it_means, action, risk, deadline, evidence, confidence, policy_rule}`

`backend/app/schemas/ask.py`

- `AskRequest`: `{doc_id, question}`
- `AskAnswer`: `{answer, confidence, evidence, quotes}`

## Database models (SQLAlchemy)

Defined in `backend/app/models.py`:

- `Document`: `{doc_id (PK), title, status, created_at}`
- `Clause`: `{id (PK), doc_id (FK), type, page, start, end, text, confidence, normalized}`
- `Guidance`: `{id (PK), doc_id (FK), title, what, action, risk, deadline, evidence, confidence}`
- `Deadline`: `{id (PK), doc_id (FK), title, due_at, source_clause_id (FK nullable)}`
- `PolicyFire`: `{id (PK), rule_id, doc_id (FK), clause_id (FK), severity, message}`

Additional model:

- `backend/app/models/audit.py` defines an `Audit` model (JSONB fields) but it is not imported anywhere, so it is not created by `Base.metadata.create_all` unless imported manually.

## Service modules (backend/app/services)

OCR: `backend/app/services/ocr.py`

- Uses docTR (`ocr_predictor`) with `db_resnet50` detector and `crnn_vgg16_bn` recognizer
- Reads PDF bytes from MinIO (`{doc_id}/original.pdf`) or local fallback `/app_storage/{doc_id}/original.pdf`
- Builds per-page spans with bounding boxes and confidences
- Stores `layout_index.json` under `{doc_id}/layout_index.json`
- Stores page images under `{doc_id}/pages/{page}.jpg`

Tables: `backend/app/services/tables.py`

- Stub, returns `{"tables": 0}`

Embeddings: `backend/app/services/embeddings.py`

- Loads `layout_index.json`
- Converts spans into Qdrant vectors using `sentence-transformers/all-mpnet-base-v2`
- Upserts points into Qdrant collection `spans`

Clauses: `backend/app/services/clauses.py`

- Stubbed clause extraction; inserts two fixed clauses into DB
- Clause types: `limitation_of_liability`, `renewal`
- Uses SQLAlchemy `SessionLocal`

Deadlines: `backend/app/services/deadlines.py`

- Stubbed; inserts one fixed deadline at now + 15 days

Rules: `backend/app/services/rules.py`

- YAML/JSON rules engine with:
  - `when` predicates (supports `any`, `all`, and flat keys)
  - Operators in string form: `<, <=, ==, !=, >, >=`
  - Dot-path access via `clause.normalized.some_field`
- Pipeline `run` reads from `/app_storage/{doc_id}/rules.yaml` or `rules.json`
- Writes results to `{doc_id}/policy_results.json` via MinIO storage

Summarizer: `backend/app/services/summarizer.py`

- Builds a bullet list from first 8 clauses
- Stores a `Guidance` row titled `Evidence-cited summary`
- Deletes any existing guidance with same title before insert

Guidance composer: `backend/app/services/guidance.py`

- Creates one guidance item per clause
- Sets `risk` from matching `PolicyFire` if available
- Creates evidence chips: `"DOC:PAGE:START-END"`
- Title currently contains a stray non-ASCII character in the string literal

RAG: `backend/app/services/rag.py`

- Searches Qdrant for top spans
- Builds evidence quotes with chip references
- Calls LLM with citation instructions

LLM: `backend/app/services/llm.py`

- OpenRouter integration via `https://openrouter.ai/api/v1/chat/completions`
- Ollama legacy support (HTTP)
- Confidence heuristic: 0.8 if citations present, else 0.55

Qdrant: `backend/app/services/qdrant.py`

- Creates collection `spans` with cosine distance, 768 dims
- Uses `sentence-transformers/all-mpnet-base-v2`
- Stable IDs via UUID5 of `doc_id::index`

Storage: `backend/app/services/storage.py`

- Uses `boto3` S3 client against MinIO endpoint
- Helpers: `put_json`, `get_json`, `put_bytes`, `get_bytes`

MinIO client: `backend/app/services/minio_client.py`

- Thin wrapper around `minio` SDK
- `ensure_bucket` and `bucket_name` helpers

Audit service: `backend/app/services/audit.py`

- Empty placeholder file

## Rule configuration

`configs/rules.yaml`:

- `liability_cap_minimum`
  - If `clause.type == limitation_of_liability` and `cap_ratio_to_annual_fees < 1.0`
  - Severity `high`
- `auto_renew_notice`
  - If `clause.type == renewal` and `notice_days < 30`
  - Severity `medium`

## Frontend

`frontend/index.html` is a self-contained static page with:

- Inline CSS and JS
- Upload widget for PDF
- Calls `POST /ingest` using `fetch`
- Displays a "Processing Status" section and a pipeline checklist
- Links to Swagger and ReDoc

Note: the frontend expects `result.document_id` but the API returns `doc_id`.

## Scripts and utilities

Backend seed scripts:

- `backend/scripts/seed_demo_doc.py`
  - Creates tables, inserts a Document, two Clauses, and one Deadline
  - Uses `db.flush()` before inserting child rows
- `backend/app/scripts/seed_demo_doc.py`
  - Similar to the above but without `db.flush()`

Root scripts directory (placeholders):

- `scripts/dev_up.sh` (empty)
- `scripts/dev_down.sh` (empty)
- `scripts/load_rules.py` (empty)
- `scripts/wait_for_it.sh` (empty)

## Configuration and infra placeholders

These files exist but are currently empty:

- `configs/logging.ini`
- `infra/nginx/nginx.conf`
- `infra/qdrant/collections.json`
- `backend/pyproject.toml`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/2025_08_24_init.py`
- `backend/app/utils/spans.py`
- `backend/app/utils/ics.py`
- `backend/app/services/audit.py`
- `backend/app/assets/prompts/qa_system.txt`
- `backend/app/assets/prompts/summary_system.txt`
- `Makefile`

## File inventory (complete)

```
.env
.env.example
.gitignore
README.md
Makefile
docker-compose.yml
backend/
  Dockerfile
  requirements.txt
  pyproject.toml
  alembic.ini
  alembic/
    env.py
    versions/
      2025_08_24_init.py
  scripts/
    seed_demo_doc.py
  app/
    __init__.py
    main.py
    db.py
    deps.py
    models.py
    models/
      audit.py
    workers/
      __init__.py
      celery_app.py
    routes/
      __init__.py
      ingest.py
      clauses.py
      guidance.py
      deadlines.py
      ask.py
      rules.py
    schemas/
      __init__.py
      common.py
      clause.py
      guidance.py
      ask.py
    services/
      __init__.py
      pipeline.py
      ocr.py
      tables.py
      embeddings.py
      clauses.py
      deadlines.py
      rules.py
      summarizer.py
      guidance.py
      rag.py
      llm.py
      qdrant.py
      storage.py
      minio_client.py
      audit.py
    utils/
      spans.py
      logger.py
      ics.py
    assets/
      prompts/
        qa_system.txt
        summary_system.txt
configs/
  rules.yaml
  logging.ini
frontend/
  index.html
infra/
  nginx/
    nginx.conf
  qdrant/
    collections.json
scripts/
  dev_up.sh
  dev_down.sh
  load_rules.py
  wait_for_it.sh
```

## Known gaps and stub behavior (current state)

- Several files are placeholders and empty (see list above).
- Clause, deadline, and table extraction are stubbed and insert fixed data.
- OCR expects a different MinIO key naming convention than the ingest endpoint currently writes.
- `QDRANT_COLLECTION` env var is not used; the collection name is hard-coded to `spans`.
- Several routes define `require_api_key` helpers but only `/ingest` uses them.

## License

No license file is present in the repo. The previous README referenced MIT but there is no `LICENSE` file yet.
