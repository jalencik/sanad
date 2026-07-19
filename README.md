# Sanad

**Sanad** (from the Uzbek/Persian-Arabic word for an official document or deed) reads
scanned official documents - passports, certificates, contracts, deeds - in whatever
language they were issued in, and gives back the structured details plus a plain
summary, in seconds.

I built this because paperwork is one of those "boring" problems nobody really wants
to touch, but it's a real one where I'm from. A lot of official documents in Uzbekistan
still get handled by hand, in Uzbek, Russian, or English depending when and where they
were issued, and that's slow and honestly error-prone. I think that's exactly the kind
of use case AI should be solving, more than another image generator.

Built with a Python/FastAPI backend, a Vue 3 + shadcn-vue frontend, self-hosted
Tesseract OCR, and the Gemini API (free tier, rotated across a few keys so a rate limit
on one doesn't stall the whole thing - more on that below) for structured extraction
and summarization.

## How it works

The workspace is a single view split by a vertical divider:

- **Left** - drag-and-drop upload, and a searchable, real-time list of every document
  you've uploaded with its live processing status (queued → analyzing → ready/failed).
- **Right, upper** - the extracted details: document type, document number, issuing
  authority, dates, detected language, OCR confidence, and any other fields found.
- **Right, lower** - an AI-generated summary of the document's main point, available
  in both its original language and English.

Documents are processed in the background: Tesseract OCR extracts the text (tuned for
Uzbek, Russian, and English - Latin and Cyrillic script both), then a single Gemini API
call returns structured fields and the two summaries via a JSON schema.

Accounts are required to use the workspace (sign up / sign in), and the interface is
available in English, Uzbek, and Russian.

## Staying up on free infrastructure

This runs on Render's free tier, which means fractional CPU and no real job queue, and
for a while that showed. Documents would get stuck mid-processing and just never move,
with no real explanation why. Turned out to be two separate problems wearing the same
costume:

1. Processing lived only in the web server's memory. Any restart - a deploy, a crash,
   the free instance recycling - silently abandoned whatever was mid-flight. Nothing
   ever picked it back up.
2. There was one Gemini API key, no timeout, no fallback, so a free-tier rate limit
   just killed the document outright.

Both are fixed now, on startup the backend requeues anything left pending or
processing from before (and skips OCR if the text was already saved, so a resume
doesn't waste the free host's CPU redoing finished work). Every document also gets a
hard 5-minute cap, so a genuine hang fails loudly instead of freezing forever. And
Gemini calls now rotate across up to 5 free-tier API keys - if one hits its limit, the
next request just moves on to the next key, with a short cooldown before it's retried.
Write-up of the actual reasoning is in [`docs/decisions/`](docs/decisions/) if you're
curious.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL |
| OCR | Tesseract (`pytesseract` + `PyMuPDF` for PDF rendering) |
| AI | Gemini API (Google, free tier), structured JSON-schema extraction, rotated across multiple keys |
| Auth | Argon2 password hashing, JWT access/refresh tokens in httpOnly cookies |
| Frontend | Vue 3, Vite, TypeScript, Tailwind CSS, shadcn-vue, Pinia, vue-router, vue-i18n |
| Infra | Docker Compose (Postgres + backend + nginx-served frontend) |

## Getting free Gemini API keys

The app runs fine on a single key, but 1 key means 1 free-tier rate limit, and once
you hit it every upload just fails until it resets. I'd rather use 5 keys from 5
different Google accounts and let the app rotate between them instead.

1. Go to [Google AI Studio](https://aistudio.google.com/apikey).
2. Sign in with a Google account and click **Create API key**. No billing/credit card
   needed for the free tier.
3. Repeat with up to 4 more Google accounts if you want the full rotation benefit.
4. Copy each key - you'll paste all of them into `.env` below, separated by commas.

## Running it

### With Docker (recommended)

```bash
cp .env.example .env
```

Open `.env` and fill in two values:

```env
GEMINI_API_KEYS=key-1,key-2,key-3,key-4,key-5
JWT_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
```

(1 to 5 keys work, comma-separated - see "Getting free Gemini API keys" above for why
5 beats 1.)

Then build and start everything:

```bash
docker compose up --build -d
```

Check that all three services are healthy:

```bash
docker compose ps
```

The app is served at `http://localhost:8080`. Watch the pipeline as you upload a
document:

```bash
docker compose logs -f backend
```

### Locally, without Docker

Backend:

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp ../.env.example .env  # fill in GEMINI_API_KEYS, JWT_SECRET_KEY
# for local dev without Postgres, set DATABASE_URL to a sqlite path instead, e.g.
#   DATABASE_URL=sqlite+aiosqlite:///./dev.db
alembic upgrade head
uvicorn app.main:app --reload
```

You'll also need Tesseract installed locally (with `eng`, `rus`, `uzb`, and `uzb_cyrl`
trained data) for OCR to work outside Docker - the Docker image installs this
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
    api/         # FastAPI routers (auth, documents, health, admin)
    core/        # settings, security (password hashing, JWT)
    db/          # SQLAlchemy engine/session setup
    models/      # ORM models (User, Document)
    schemas/     # Pydantic request/response models
    services/    # OCR, Gemini integration + key rotation, upload storage,
                 # pipeline orchestration, rate limiting
  alembic/       # database migrations
  tests/         # pytest suite

frontend/
  src/
    components/  # UI primitives (shadcn-vue) + workspace/layout components
    views/        # LandingPage, WorkspaceView, SignInView, SignUpView
    stores/       # Pinia stores (documents, auth)
    i18n/         # English / Uzbek / Russian translations
    lib/          # API client, formatting helpers, theme

docs/
  decisions/     # short write-ups for the less obvious engineering calls
```

## Design notes

The interface deliberately avoids the generic "AI-generated" look: no purple gradients,
no glow/aurora effects, no glassmorphism, no emoji icons, no identical icon-topped card
grids. The palette is a single dominant ink-navy with one restrained bronze accent (a
nod to an official seal), paired with a serif display face for headings and Inter for
dense UI text. Light mode is the default. Dark mode is a deliberate opt-in via the
toggle in the top bar, not a system-preference default.

I'm also not trying to build a proper durable job queue here, that would need
infrastructure this project doesn't have the budget for. The goal was just to make
sure a document is never silently lost, and that free-tier limits slow things down
instead of breaking them.
