# Sanad

**Sanad** (from the Uzbek/Persian-Arabic word for an official document or deed) reads
scanned official documents — passports, certificates, contracts, deeds — in whatever
language they were issued in, and returns structured details plus a plain-language
summary in seconds.

Built with a Python/FastAPI backend, a Vue 3 + shadcn-vue frontend, self-hosted
Tesseract OCR, and Claude for structured extraction and summarization.

## How it works

The workspace is a single view split by a vertical divider:

- **Left** — drag-and-drop upload, and a searchable, real-time list of every document
  you've uploaded with its live processing status (queued → analyzing → ready/failed).
- **Right, upper** — the extracted details: document type, document number, issuing
  authority, dates, detected language, OCR confidence, and any other fields found.
- **Right, lower** — an AI-generated summary of the document's main point, available
  in both its original language and English.

Documents are processed in the background: Tesseract OCR extracts the text (tuned for
Uzbek, Russian, and English — Latin and Cyrillic script both), then a single Claude API
call returns structured fields and the two summaries via a tool-use schema.

Accounts are required to use the workspace (sign up / sign in), and the interface is
available in English, Uzbek, and Russian.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL |
| OCR | Tesseract (`pytesseract` + `PyMuPDF` for PDF rendering) |
| AI | Claude API (Anthropic), structured tool-use extraction |
| Auth | Argon2 password hashing, JWT access/refresh tokens in httpOnly cookies |
| Frontend | Vue 3, Vite, TypeScript, Tailwind CSS, shadcn-vue, Pinia, vue-router, vue-i18n |
| Infra | Docker Compose (Postgres + backend + nginx-served frontend) |

## Running it

### With Docker (recommended)

```bash
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY and JWT_SECRET_KEY
#   generate a secret with: python -c "import secrets; print(secrets.token_hex(32))"

docker compose up --build
```

The frontend will be available at `http://localhost:8080`.

### Locally, without Docker

Backend:

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp ../.env.example .env  # fill in ANTHROPIC_API_KEY, JWT_SECRET_KEY
# for local dev without Postgres, set DATABASE_URL to a sqlite path instead, e.g.
#   DATABASE_URL=sqlite+aiosqlite:///./dev.db
alembic upgrade head
uvicorn app.main:app --reload
```

You'll also need Tesseract installed locally (with `eng`, `rus`, `uzb`, and `uzb_cyrl`
trained data) for OCR to work outside Docker — the Docker image installs this
automatically.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
pytest
```

## Project layout

```
backend/
  app/
    api/         # FastAPI routers (auth, documents, health)
    core/        # settings, security (password hashing, JWT)
    db/          # SQLAlchemy engine/session setup
    models/      # ORM models (User, Document)
    schemas/     # Pydantic request/response models
    services/    # OCR, Claude integration, upload storage, pipeline orchestration, rate limiting
  alembic/       # database migrations
  tests/         # pytest suite

frontend/
  src/
    components/  # UI primitives (shadcn-vue) + workspace/layout components
    views/        # LandingPage, WorkspaceView, SignInView, SignUpView
    stores/       # Pinia stores (documents, auth)
    i18n/         # English / Uzbek / Russian translations
    lib/          # API client, formatting helpers, theme
```

## Design notes

The interface deliberately avoids the generic "AI-generated" look: no purple gradients,
no glow/aurora effects, no glassmorphism, no emoji icons, no identical icon-topped card
grids. The palette is a single dominant ink-navy with one restrained bronze accent (a
nod to an official seal), paired with a serif display face for headings and Inter for
dense UI text. Light mode is the default; dark mode is a deliberate opt-in via the
toggle in the top bar, not a system-preference default.
