# AskMitra

An AI-powered community marketplace for Northern Virginia: buy, sell and give away items,
find local Indian & Telugu businesses and professionals, and keep up with deals, jobs,
movies and events. Fully bilingual: English and తెలుగు.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the seven-phase plan. **Phases 1 (foundation) and 2 (AI listings) are complete.**

## Stack

| Layer | Tech |
|-------|------|
| Web | Next.js 16 (App Router), React 19, Tailwind CSS 4, `@supabase/ssr` |
| API | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, GeoAlchemy2 |
| Data | PostgreSQL 17 + PostGIS 3.5 |
| Auth / files | Supabase Auth (magic link, Google), Supabase Storage (private bucket, signed URLs) |
| AI | Claude API (`claude-opus-5-5`, vision + structured outputs) |
| Payments | Stripe (Phase 7) |
| Tests | Pytest, Playwright |

```
.
├── backend/            FastAPI app
│   ├── app/
│   │   ├── api/        deps (auth, roles) + routes
│   │   ├── core/       settings, JWT verification
│   │   ├── db/         engine/session, declarative base
│   │   ├── models/     SQLAlchemy models
│   │   ├── schemas/    Pydantic request/response models
│   │   ├── services/   photo processing, Supabase Storage, Claude listing drafts
│   │   └── seed.py     bilingual category seed
│   ├── alembic/        migrations
│   └── tests/          unit + PostGIS integration tests
├── frontend/           Next.js app
│   ├── src/app/        routes (home, listings, login, account, auth/*)
│   ├── src/components/
│   ├── src/i18n/       EN/TE dictionaries
│   ├── src/lib/        api client, supabase clients, types
│   ├── src/proxy.ts    session refresh + protected routes (Next 16 "proxy")
│   └── e2e/            Playwright tests
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Quick start (Docker)

1. **Create a Supabase project** at supabase.com, then:
   - *Authentication → URL Configuration*: set Site URL `http://localhost:3000` and add
     `http://localhost:3000/auth/callback` to Redirect URLs.
   - *Authentication → Providers*: Email is on by default; enable Google if you want it.
   - *Storage → New bucket*: name it `listing-photos` and leave **Public bucket off**.
     No storage policies are needed: only the API uploads (with the service-role key) and
     browsers get short-lived signed URLs.
2. **Get a Claude API key** at platform.claude.com (needed for "Snap & sell").
3. **Configure env**
   ```bash
   cp .env.example .env
   # fill SUPABASE_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY,
   #      SUPABASE_SERVICE_ROLE_KEY (server only!) and ANTHROPIC_API_KEY
   ```
4. **Run**
   ```bash
   make up          # db + api (migrates & seeds automatically) + web
   ```
   - Web: http://localhost:3000
   - API docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health/ready

The UI still runs without Supabase keys (sign-in shows a "not configured" notice) and
without the API (pages show an "unavailable" banner). Without the service-role key or the
Claude key, "Snap & sell" returns a friendly "not available" message.

### How "Snap & sell" works
1. The browser shrinks each photo to ≤2048 px JPEG and uploads 1–5 to
   `POST /api/v1/ai/draft-listing` (with `listing_type` = `sell`/`free` and an optional note).
2. The API re-encodes every photo (dropping all EXIF, including GPS), checks the user's
   AI quota, and sends the photos to Claude with a strict JSON schema.
3. Claude returns English + Telugu title/description, category, condition, a local
   used-price range and a confidence score, or flags the photo (`no_item`, `prohibited`,
   `unclear_photo`), in which case nothing is created.
4. The API saves a **draft** listing with the photos. The seller reviews and edits it at
   `/listings/{id}/edit`, then publishes it (`PATCH /listings/{id}` with `status: active`).

Every AI call is logged in `ai_usage` (tokens, cost, latency, outcome); per-user limits
are `AI_DRAFTS_PER_HOUR` / `AI_DRAFTS_PER_DAY`. Daily spend:
```bash
docker compose exec db psql -U cc community_connect -c \
  "SELECT date(created_at), count(*), sum(cost_usd) FROM ai_usage GROUP BY 1 ORDER BY 1 DESC;"
```

### Make yourself an admin
```bash
docker compose exec db psql -U cc community_connect \
  -c "UPDATE profiles SET role='admin' WHERE email='you@example.com';"
```
(Sign in once first so your profile row exists.)

## Running without Docker

```bash
# API (needs a PostGIS database; set DATABASE_URL in backend/.env)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload

# Web (put NEXT_PUBLIC_* and API_INTERNAL_URL=http://localhost:8000 in frontend/.env.local)
cd frontend
npm install
npm run dev
```

## Tests

```bash
make test-api     # pytest in the api container, incl. PostGIS integration tests
cd backend && pytest -q   # locally: integration tests skip unless TEST_DATABASE_URL is set
cd frontend && npm run lint && npm run typecheck
cd frontend && npx playwright install chromium && npx playwright test
```

## Key design decisions

- **Supabase issues tokens; our API owns authorization.** The API verifies the Supabase
  JWT (JWKS for asymmetric signing keys, or the legacy HS256 secret) and looks up the
  user's role in our `profiles` table, so roles change without re-issuing tokens.
- **Bilingual by design.** Listings store `title_en/title_te` and `description_en/te` plus
  a `source_language`; categories carry both names. UI language comes from a cookie,
  falling back to the browser's `Accept-Language`.
- **Location privacy.** Listing coordinates are rounded to ~1 km before storage, and
  photo metadata (EXIF/GPS) is stripped in the browser and again on the server.
- **AI drafts, humans publish.** Claude's output lands in `draft` status; nothing it writes
  is public until the seller reviews it. Text in photos is treated as data, not instructions.
- **Search.** English uses a weighted Postgres full-text index (stemming, `websearch` syntax,
  `sort=relevance`); Telugu, which has no Postgres stemmer, uses `pg_trgm` substring indexes.
- **Enums as `VARCHAR + CHECK`.** Easier to evolve than native Postgres enums.
- **Soft deletes.** Removed listings keep their row for moderation history.
