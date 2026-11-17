# Community Connect: Seven-Phase Roadmap

| # | Phase | Status |
|---|-------|--------|
| 1 | Foundation: repository, auth, database, UI shell | ✅ Done |
| 2 | AI listings: photo upload → English/Telugu listing | ✅ Done |
| 3 | Business & professional directory | ⏳ Next |
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

## Phase 2: AI listings ✅
- Private Supabase Storage bucket `listing-photos`, written only by the API (service-role
  key) and read through batch-signed, expiring URLs; `listing_images` table
- Photos re-encoded server-side (JPEG/PNG/WebP in, JPEG out, ≤2048 px, 12 MB cap,
  decompression-bomb guard), dropping all EXIF/GPS; browser pre-shrinks before upload
- `POST /api/v1/ai/draft-listing`: Claude vision (`claude-opus-5-5`, effort `medium`,
  server-side refusal fallback) with a strict JSON schema → EN + TE title/description,
  category, condition, local used-price range, confidence, and `no_item` / `prohibited` /
  `unclear_photo` flags
- Sell flow: photos → AI draft → review/edit (both languages, photos, price hint) → publish;
  owner-only draft visibility; add/remove photos; "My listings" on the account page
- Listing detail page with gallery and the other language on demand; photos on cards
- Weighted English full-text search + `pg_trgm` for Telugu; `sort=relevance`
- Per-user AI quotas (hourly + daily, slot reserved before the call) and `ai_usage`
  cost/latency logging

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
  and a sample of AI-written Telugu listings (tune `SYSTEM_PROMPT` in
  `backend/app/services/ai_listing.py` from the feedback)
- An eval set of real item photos to check draft quality and price accuracy before launch
- Photo reordering / choosing the cover photo; adding photos from the edit page (API exists)
- Privacy policy & terms pages
- Mobile navigation menu (desktop nav is hidden below `md`)
