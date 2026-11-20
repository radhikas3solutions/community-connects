# AskMitra: Seven-Phase Roadmap

| # | Phase | Status |
|---|-------|--------|
| 1 | Foundation: repository, auth, database, UI shell | ✅ Done |
| 2 | AI listings: photo upload → English/Telugu listing | ✅ Done |
| 3 | Business & professional directory | 🚧 In progress |
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

## Phase 3: Directory 🚧
Done:
- `businesses` + `menu_items` tables; businesses and individuals (helpers, tutors, tailors);
  new categories: plumbers & electricians, tailors, nannies/cooks/helpers
- Member submissions go to a moderator review queue (`/admin/directory`); staff entries go
  live at once; reject with a note, editing a rejected entry resubmits it; verified badge
- Privacy: no home address for individuals, and their phone/WhatsApp/email only for
  signed-in members; consent checkbox when adding someone else
- Directory search (name/description full-text, Telugu name trigram, category, language
  spoken, city/service area); entry pages with Call / WhatsApp / Directions / Share
- Restaurant menus: photos -> Claude (streamed structured output) -> editable dish list
  (EN + Telugu names, prices, veg/non-veg) -> saved; AI quota shared with listing drafts
- "Add with our assistant" chat (`/directory/assistant`, `POST /assistant/directory-intake`):
  people describe their business or service in English or Telugu; each turn returns a reply
  plus a validated draft shown as a live preview; the person ticks consent and submits it
  to the normal review queue (the AI never saves anything). ~1-3¢ per turn, own rate limit
- "Ask" search assistant (`/ask`, `POST /assistant/ask`, the search box on the home page, and the
  floating "✨ Ask Mitra" button on every page; one conversation per tab, kept across pages):
  questions like "dentist in Aldie" in English or Telugu; Claude calls read-only
  `search_directory` / `search_marketplace` tools, widens to neighboring towns when a town
  has no matches, and answers with a short reply plus result cards (call / WhatsApp). Cards
  are limited to entries the tools actually returned. ~2-3¢ per question, 4-12 s
- NPI Registry import (`/admin/directory/import`, `POST /admin/import/npi`, staff only):
  physicians (family, internal medicine and its specialists, pediatrics, OB/GYN,
  ophthalmology, dermatology, psychiatry/neurology, orthopedics, ENT, allergy, urology),
  optometrists and dentists, per ZIP across all of Northern Virginia (98 ZIPs) from the
  public CMS registry. Only specialties that start with the searched one count, so nurse
  practitioners and therapists aren't listed as doctors; dental-only practices go in their
  own "Dentists" category.
  The registry's search API misses providers (e.g. most plain "Pediatrics" physicians), so
  the complete import reads CMS's monthly full file instead:
  `python -m app.import_nppes data_imports/NPPES_Data_Dissemination_<Month>_<Year>_V2.zip`
  (download from https://download.cms.gov/nppes/NPI_Files.html; ~1 GB, read from the zip in
  ~10 min). The admin page's API import stays for quick per-ZIP top-ups. Practice LOCATION address only (mailing addresses are often homes),
  must be in the ZIP; providers sharing a practice phone become one entry listing them;
  live but unverified with a "Public record" label; re-import updates (keyed on ZIP + phone)
  and never revives removed/rejected entries; skips phones a member already listed.
  First run: 12 Loudoun/western Fairfax ZIPs -> 484 practices
- OpenStreetMap restaurant import (same admin page, `POST /admin/import/osm`): named restaurants,
  fast food and cafés per area via the Overpass API (open data, ODbL: every entry shows
  "© OpenStreetMap contributors" and links to its OSM record). Cuisine, diet (vegetarian/halal),
  takeout/delivery and hours go into the entry; Dulles terminals skipped; missing or misspelled
  towns get the nearest town centre; places mapped twice or already listed are skipped.
  First run: Loudoun + Herndon/Chantilly/Centreville -> 1,176 places (39 Indian)

- Only callable entries are listed: search and Ask Mitra show entries with a valid 10-digit US
  number (area code/exchange not starting with 0/1); the add/edit form and assistant require
  one; imports skip places without one (OSM 1,176 -> 709 restaurants; NPI drops registry filler)

Still to do:
- Re-run the NPI import every few months (a scheduled job); chains with one central phone
  number currently collapse to their first ZIP
- Restaurants closed since the last OSM import stay listed until a moderator removes them
  (mark entries no longer in OSM on re-import); about half of OSM places have no phone number
- Claim-your-business flow, reviews/ratings, map view (needs geocoding), photos/logos,
  opening-hours structure, duplicate detection

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
