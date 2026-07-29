# Deploying Travel Desk

Four free services, none of which need a card:

| Piece | Host | Why |
|---|---|---|
| Frontend | **Vercel** | Next.js, zero config beyond the API URL |
| Backend | **Render** | Runs the existing Dockerfile, supports SSE streaming |
| Postgres | **Neon** | Free tier does not expire (Render's own free Postgres does, after 90 days) |
| Redis | **Upstash** | Free serverless Redis, plain `redis://` URL |

The models are the thing to understand before starting: **local models cannot
run on any of this.** Qwen and Gemma need Ollama on the same machine as the
backend, and a hosted backend has no GPU. The deployed app therefore locks
them in the picker, with a note explaining they run locally, and serves
Gemini — which executes on Google's side and works from anywhere.

That is not a limitation to hide. It is the honest shape of the project: a
local-first app with a cloud fallback, deployed where only the cloud half can
run.

---

## 1. Postgres (Neon)

1. Create a project at [neon.tech](https://neon.tech).
2. Copy the connection string. It looks like
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`.

Tables are created automatically on first boot — no migration step.

## 2. Redis (Upstash)

1. Create a database at [upstash.com](https://upstash.com).
2. Copy the **`redis://` (TCP)** URL, not the REST one — this app uses a
   normal Redis client.

Redis is optional in the sense that every call is wrapped and the app keeps
working without it, but you lose conversation memory, tool caching and rate
limiting. Losing the cache also means every revision round re-hits the travel
APIs, so it is worth the five minutes.

## 3. Backend (Render)

**New → Blueprint**, point it at this repo. `ai-travel-agent/render.yaml`
describes the service; Render will ask for the values marked `sync: false`:

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Neon string |
| `REDIS_URL` | the Upstash `redis://` string |
| `GOOGLE_API_KEY` | your Gemini key — this is what makes the deploy usable |
| `ALLOWED_ORIGINS` | your Vercel URL, e.g. `https://travel-desk.vercel.app` |
| `SERPAPI_KEY`, `RAPIDAPI_KEY` | optional; without them flights and hotels come back as clearly marked estimates |

Already set in the blueprint: `MODEL_NAME=gemini-flash-latest`,
`PLANNER=graph`, `OPENAI_API_BASE=""` (deliberately empty — pointing it at an
Ollama that does not exist would make the model probe wait for a timeout on
every request).

Check it came up:

```bash
curl https://<your-service>.onrender.com/health/
curl https://<your-service>.onrender.com/api/models/
```

The second should show the Gemini models `available: true` and every local
model `available: false` with a reason.

## 4. Frontend (Vercel)

**New Project** → import the repo, then:

- **Root Directory:** `ai-travel-agent/frontend`
- **Environment variable:** `NEXT_PUBLIC_API_URL=https://<your-service>.onrender.com`

Deploy, then put the resulting domain into Render's `ALLOWED_ORIGINS` and let
it redeploy. Until you do, every request fails CORS before it reaches the
planner.

> The browser calls Render **directly** rather than through Next's
> `/api/*` rewrite. That rewrite exists for local development; in production
> a plan can stream for a minute or more, which is the kind of long-lived
> proxied response a frontend edge network will cut off. Going direct also
> keeps SSE unbuffered.

---

## What to expect

**The first request after a quiet spell takes about a minute.** Render's free
tier sleeps after 15 minutes idle, and the container has to start before the
planner even begins. Subsequent plans run at normal speed. If that matters,
Render's cheapest paid tier removes it; nothing in the code needs to change.

**Plans take 15–40 seconds on Gemini** — faster than local models, but this is
still an agent doing real searching, not a chat completion. The progress
events keep the UI honest while it works.

**Rate limiting is per IP**, 20 plans per hour, configurable with
`RATE_LIMIT_PER_HOUR`. The limit exists because a public URL with your API key
behind it is exactly the thing that gets scraped. It is keyed on IP rather
than the session id, since the browser generates the session id and rotating
it costs nothing.

**Watch your Gemini quota** for the first few days. If the app gets shared
more widely than you expected, lower `RATE_LIMIT_PER_HOUR`, or put the deploy
behind an access code.

## Running it fully locally

The local models are only locked on the hosted deployment. Cloned and run with
Docker Compose against a host Ollama, the same picker unlocks Qwen and Gemma
automatically — the backend probes for Ollama and reports what it finds, so
nothing needs configuring to switch between the two worlds.

```bash
ollama pull qwen3:8b
docker compose up --build
```
