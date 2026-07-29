# Faster free hosting than Render

Date: 2026-07-29
Status: Proposed (not migrated - this is the research + recommendation, migrating
still needs someone with a real account on the new host)

## Problem

Render's free tier spins a service down after 15 minutes idle, and the next
request pays a 30-60s cold start - by far the slowest and most confusing
thing a user of this app ever hits (it shows up as a bare 502 from Render's
own edge if the wake-up takes long enough that the browser or an upstream
proxy gives up first). `keep-alive.yml` already papers over part of this
during 03:00-13:59 UTC, but outside that window - or if a request lands
exactly mid-wake - the raw cold start is still what a real visitor sees.

There is no genuinely free host in mid-2026 that never sleeps *and* costs
nothing *and* needs no setup - if that combination existed everyone would
already be using it. What's actually achievable is a **much faster** wake
(1-5s instead of 30-60s), which is the real fix: nobody notices a 2s delay.

## Options considered

| Host | Free tier | Cold start | Fits this app's architecture as-is? |
|---|---|---|---|
| **Render (current)** | 2 Docker services, 750 pooled instance-hours/mo | 30-60s | yes |
| **Koyeb** | 1 free Docker instance (512MB/0.1vCPU), Frankfurt or Washington DC only | 1-5s | Only 1 free instance per org - this app currently ships as 2 services (backend + nginx/frontend) |
| **Google Cloud Run** | 2M requests/mo + 360k GiB-seconds/mo, pooled across as many services as you deploy | 1-3s | **No, not without a change** - see caveat below |
| **Fly.io / Railway** | Neither has a real free tier anymore in 2026 (both now require a card and bill usage) | - | - |
| **Cloudflare Pages / Netlify / Vercel (static)** | Free, effectively unlimited for a small app | none (CDN, not a container) | Frontend only - none of these run a Python/Tesseract backend |

Sources: [Koyeb pricing FAQ](https://www.koyeb.com/docs/faqs/pricing), [Koyeb free tier scale-to-zero behavior](https://runhooks.app/blog/keeping-koyeb-free-tier-awake/), [Cloud Run free tier & pricing](https://cloud.google.com/run/pricing), [Cloud Run cold start guidance](https://cloud.google.com/blog/topics/developers-practitioners/a-guide-to-ai-cold-starts-on-cloud-run), [Fly.io free tier status in 2026](https://www.saaspricepulse.com/blog/flyio-free-tier-2026), [Render vs Railway vs Fly.io 2026](https://hostim.dev/blog/render-vs-railway-vs-fly-pricing/).

### The Cloud Run caveat, specifically

Cloud Run's default billing mode only allocates CPU **while a request is in
flight** - once the HTTP response for an upload is sent, the container can be
frozen before `BackgroundTasks` finishes running `process_document`. That's
exactly the mechanism this app's whole pipeline depends on (see
[`2026-07-19-pipeline-durability-and-key-rotation.md`](2026-07-19-pipeline-durability-and-key-rotation.md)).
Startup recovery would eventually pick a frozen document back up on the next
cold start, but "eventually, on the next unrelated request" is a worse
version of the exact bug that doc already fixed once. Cloud Run only avoids
this with "CPU always allocated," which is billed, not free. Skip Cloud Run
unless a redesign to a request-triggered worker (e.g. Cloud Tasks calling
back into the app) is also on the table.

## Recommendation

**Koyeb for the backend**, because it's the only option that is (a) actually
free with no redesign, (b) a normal long-lived container so `BackgroundTasks`
keeps working exactly as it does on Render today, and (c) a 1-5s cold start
instead of 30-60s.

The catch is the single free instance. Two ways to fit this app into it:

1. **Move the frontend off Koyeb/Render entirely, onto a static host**
   (Cloudflare Pages, Netlify, or Vercel - all genuinely free, and a static
   Vite build has *no* cold start at all, ever, since it's served from a
   CDN rather than a container). The backend keeps its own Koyeb URL. This
   is the better long-term shape, but it moves frontend and backend to
   different origins, which means:
   - `CORS_ORIGINS` on the backend must include the new frontend origin.
   - Auth cookies need `SAMESITE=None` (cross-site) instead of today's
     `lax`, which also means adding real CSRF protection - SameSite=Lax is
     currently doing that job for free (see the security notes below), and
     giving it up isn't free to replace.
   - The frontend's `/api` relative base URL needs to become the backend's
     real Koyeb URL at build time.

   This is a real change, not a config tweak - worth doing deliberately as
   its own follow-up rather than folded into this pass.

2. **Keep frontend and backend on one Koyeb instance**, by having FastAPI
   serve the built Vue files directly (`StaticFiles` + an SPA fallback
   route) instead of the current nginx container. This keeps everything
   same-origin - no cookie or CORS changes at all - at the cost of removing
   nginx from the production image (gzip/cache headers would need to move
   into FastAPI, or stay handled by whatever CDN sits in front, if any).

Given the size of either change, this pass stops at the recommendation +
migration shape rather than executing one - happy to build out whichever
option once you've picked one and have a Koyeb (or Cloudflare Pages) account
to point it at.

## Migrating the backend to Koyeb (once you're ready)

1. Create a free account at [koyeb.com](https://www.koyeb.com) (a card is
   required for verification but the free instance itself is never billed).
2. New service → Docker → point it at this repo, `backend/Dockerfile`,
   region Frankfurt or Washington DC.
3. Set the same environment variables currently on Render's backend service
   (`DATABASE_URL`, `GROQ_API_KEYS`/`GEMINI_API_KEYS`, `JWT_SECRET_KEY`,
   `COOKIE_SECURE=true`, `CORS_ORIGINS`, etc. - see `.env.example`).
4. Point the frontend's `BACKEND_URL` build arg (or wherever the frontend
   ends up living, per the two options above) at the new Koyeb URL.
5. Update `keep-alive.yml` (or retire it - a 1-5s cold start may just be
   fine to let happen).

## Rejected

- **Fly.io / Railway**: no free tier left as of 2026 for either - both now
  require a card on file and bill for usage, so neither is actually a "free
  tier" comparison anymore.
- **Staying on Render but tuning keep-alive further**: the 750 pooled
  instance-hours/month cap means covering more hours just shifts the gap
  elsewhere in the month; it doesn't fix the underlying 30-60s wake time
  when a request does land outside covered hours.
