# Community Connect: Seven-Phase Roadmap

| # | Phase | Status |
|---|-------|--------|
| 1 | Foundation: repository, auth, database, UI shell | ✅ Done |
| 2 | AI listings: photo upload → English/Telugu listing | ⏳ Next |
| 3 | Business & professional directory | |
| 4 | Community content: deals, jobs, movies, events | |
| 5 | Sharing & engagement: WhatsApp / Facebook / Instagram | |
| 6 | Trust & safety: moderation and admin dashboard | |
| 7 | Monetisation & launch: Stripe business subscriptions, hardening | |

## Phase 1: Foundation ✅
- Monorepo layout, Docker Compose (PostGIS 17, FastAPI, Next.js 16), Makefile, CI
- Supabase Auth (email magic link + Google OAuth) with PKCE callback; API verifies
  JWTs via JWKS (asymmetric keys) or the legacy HS256 secret
- Profiles provisioned just-in-time on first API call; roles (`user`, `business`,
  `moderator`, `admin`) live in our DB, not the token
- PostGIS schema: `profiles`, `categories` (bilingual, 30 seeded incl. Indian/Telugu),
  `listings` (sell/buy/free, bilingual title/description, geography point, GIST index)
- Listings CRUD + geo search (radius, nearest, price sort, category, text), owner/staff
  authorization, soft delete, location rounding (~1 km) for privacy
- UI: bilingual (EN/తెలుగు) via cookie + Accept-Language, Noto Sans Telugu, home,
  browse, login, account, graceful API-down states
- Tests: pytest unit + PostGIS integration, Playwright e2e (desktop + mobile)

## Phase 2: AI listings
- Supabase Storage bucket `listing-photos` (private upload, signed URLs, size/type limits,
  EXIF/GPS stripping), `listing_images` table
- `POST /api/v1/ai/draft-listing`: Claude vision (`claude-opus-5-5`) with structured output
  → title/description in EN + TE, category, condition, suggested price range, confidence
- Sell flow: camera/upload → AI draft → edit → publish; draft status until confirmed
- Postgres full-text search (English) + trigram for Telugu; listing detail page
- Rate limiting per user on AI endpoints; cost logging

## Phase 3: Directory
- `businesses` table (owner, hours, languages spoken, service area polygon, verified flag),
  claim-your-business flow, reviews/ratings, directory search with map

## Phase 4: Community content
- `deals`, `jobs`, `events`, `movies` (showtimes at local theatres) with expiry, RSVP,
  calendar export (ICS)

## Phase 5: Sharing & engagement
- Share buttons (WhatsApp deep links, Facebook, Instagram story-friendly image),
  dynamic Open Graph images per listing (`next/og`), saved items, in-app messaging,
  email notifications

## Phase 6: Trust & safety
- AI pre-moderation of new content (Claude) → `pending_review` queue, user reports,
  moderator dashboard, audit log, bans, appeal flow

## Phase 7: Monetisation & launch
- Stripe Checkout + Billing for business tiers (featured placement, analytics),
  webhooks, customer portal; production deploy, observability, backups, load test

## Open items
- Native-speaker review of all Telugu copy (`backend/app/seed.py`, `frontend/src/i18n`)
- Privacy policy & terms pages
- Mobile navigation menu (desktop nav is hidden below `md`)
