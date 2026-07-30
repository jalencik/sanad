# Pipeline durability + Gemini key rotation

Date: 2026-07-19
Status: Accepted

## Problem

Documents were getting permanently stuck in "processing," visually frozen at
22% (`useAnimatedProgress.ts`'s `real + 12` animation ceiling against
`PROGRESS_QUEUED = 10` - the math is exact, not a coincidence). Two root
causes, verified by reading the actual code paths:

1. Document processing runs as an in-process FastAPI `BackgroundTasks` job
   with no persistence. A server restart (deploy, crash, Render free-tier
   instance recycling) silently abandons whatever was mid-flight - nothing
   ever resumes it.
2. The AI step used a single hardcoded Gemini API key with no request
   timeout and no fallback. A free-tier rate limit fails the document
   outright, and a slow/stalled connection could hang a worker thread
   indefinitely (no timeout was ever configured on the `genai.Client`).

## Decision

- On process startup, requeue any document left in `pending`/`processing` -
  by definition, if the process is just starting, no prior process can
  still legitimately own that work.
- Cap total processing time per document so a genuine hang fails loudly and
  visibly instead of freezing forever. Originally 5 minutes; raised to 15
  (`PROCESS_TIMEOUT_SECONDS` in `pipeline.py`) once the math caught up with
  it - a full multi-page PDF's own per-page OCR ceilings could legitimately
  add up to more than 5 minutes before this cap even got involved, which
  meant it could kill an honestly-still-working document. See the comment
  above `PROCESS_TIMEOUT_SECONDS` for the current worst-case arithmetic.
- On resume, skip OCR if `ocr_text` was already saved from a prior attempt -
  don't burn the free tier's fractional CPU redoing finished work.
- Support up to 5 Gemini API keys via `GEMINI_API_KEYS` (comma-separated).
  Rotate across them; on any failure from a key, put it on a short cooldown
  and immediately try the next key rather than backing off on the same one.
- Set an explicit 30s timeout on every Gemini call.

## Rejected alternatives

- A durable task queue (Celery/RQ + Redis): the textbook answer, but adds a
  paid or self-hosted broker the free-tier deployment has no room for.
  Startup-recovery gets the same practical guarantee - no document is ever
  abandoned - at zero extra infrastructure.
- Stacking the Gemini SDK's own built-in retry on top of key rotation:
  the SDK would retry the same rate-limited key with growing backoff before
  ever raising, which delays the rotation instead of helping it. One
  rotation loop across keys is simpler and faster than two overlapping
  retry mechanisms.
- Parsing the `retryDelay` Google sometimes returns on a 429 to size the
  cooldown precisely: adds brittle parsing of a nested error shape for
  marginal benefit over a fixed, generous cooldown.
