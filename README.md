# Community Connect

An AI-powered community marketplace for Northern Virginia: buy, sell and give away items,
find local Indian & Telugu businesses and professionals, and keep up with deals, jobs,
movies and events. Fully bilingual: English and తెలుగు.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the seven-phase plan. **Phase 1 (foundation) is complete.**

## Stack

| Layer | Tech |
|-------|------|
| Web | Next.js 16 (App Router), React 19, Tailwind CSS 4, `@supabase/ssr` |
| API | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, GeoAlchemy2 |
| Data | PostgreSQL 17 + PostGIS 3.5 |
| Auth / files | Supabase Auth (magic link, Google), Supabase Storage (Phase 2) |
| AI | Claude API, vision (Phase 2) |
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
2. **Configure env**
   ```bash
   cp .env.example .env
   # fill SUPABASE_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
   ```
3. **Run**
   ```bash
   make up          # db + api (migrates & seeds automatically) + web
   ```
   - Web: http://localhost:3000
   - API docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health/ready

The UI still runs without Supabase keys (sign-in shows a "not configured" notice) and
without the API (pages show an "unavailable" banner).

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
- **Location privacy.** Listing coordinates are rounded to ~1 km before storage.
- **Enums as `VARCHAR + CHECK`.** Easier to evolve than native Postgres enums.
- **Soft deletes.** Removed listings keep their row for moderation history.
