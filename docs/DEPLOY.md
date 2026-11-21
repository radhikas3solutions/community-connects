# Going live: domain, website, API and database

Setup: **Vercel** (website) + **Fly.io** (API) + **Supabase** (database, sign-in, photos).
Domain: **askmitra.ai** (buy it first, step 1).

| Address | Serves | Host |
|---|---|---|
| `https://askmitra.ai` (and `www.`) | Website | Vercel |
| `https://api.askmitra.ai` | API | Fly.io |
| Supabase project URL | Database, sign-in, photos | Supabase |

Do the steps in order. Each one lists what to copy into the next.

## 1. Buy the domain

Cloudflare Registrar, Porkbun or Namecheap. `.ai` domains cost about $70-90 for the first
2 years (often sold in 2-year terms), then about $70-80/year. Turn on auto-renew: an expired
`.ai` name can be registered by someone else.
You will add DNS records in steps 4 and 5.

## 2. Supabase production project

Use a **new** project for production, so test accounts and data stay out of it.

1. supabase.com -> New project. Region: **East US (North Virginia)**. Save the database password.
2. Project Settings -> API: copy the **Project URL**, the **anon/publishable key** and the
   **service_role/secret key** (server only, never in the website).
3. Project Settings -> Database -> Connection string -> URI (direct connection). Change the start
   to `postgresql+psycopg://` and add `?sslmode=require`. This is `DATABASE_URL`.
4. Storage -> New bucket `listing-photos`, **Public: off**.
5. Authentication -> URL Configuration:
   - Site URL: `https://askmitra.ai`
   - Redirect URLs: `https://askmitra.ai/**`, `https://www.askmitra.ai/**`
6. Authentication -> Providers -> Google: same client ID/secret as development, and in Google Cloud
   Console add `askmitra.ai` to the OAuth consent screen's authorized domains.
7. Members register with name, email, phone and a password. The email is confirmed once, with
   a code; after that they sign in with email and password and no email is sent.
   - Authentication -> Providers -> Email: **Confirm email** on, minimum password length 8.
   - Authentication -> Emails -> Templates: the app asks for a **code**, so the emails must show
     `{{ .Token }}` (the default templates only have a link).

     **Confirm signup** (subject "Your AskMitra code"):

     ```html
     <h2>Welcome to AskMitra</h2>
     <p>Your code is <strong style="font-size:24px">{{ .Token }}</strong></p>
     <p>Enter it on the AskMitra page to finish creating your account. You only do this once.</p>
     ```

     **Reset password** (subject "Reset your AskMitra password"):

     ```html
     <h2>Reset your AskMitra password</h2>
     <p>Your code is <strong style="font-size:24px">{{ .Token }}</strong></p>
     <p>Enter it on the AskMitra page with your new password. If you didn't ask, ignore this email.</p>
     ```
   - Members who used email links before: they tap "Forgot password?" once to set a password.
8. Authentication -> Emails: set up custom SMTP (e.g. Resend or Postmark) before launch. Supabase's
   built-in email is limited to a few messages an hour.

## 3. API on Fly.io

Install the CLI (`brew install flyctl`), then from `backend/`:

```sh
fly auth signup            # or: fly auth login
fly apps create askmitra-api      # if taken, pick another name and update fly.toml
fly secrets set \
  DATABASE_URL='postgresql+psycopg://postgres:...@db.<ref>.supabase.co:5432/postgres?sslmode=require' \
  SUPABASE_URL='https://<ref>.supabase.co' \
  SUPABASE_SERVICE_ROLE_KEY='...' \
  STORAGE_BUCKET='listing-photos' \
  ANTHROPIC_API_KEY='...' \
  CORS_ORIGINS='https://askmitra.ai,https://www.askmitra.ai'
fly deploy                 # runs database migrations, then starts the API
fly ssh console -C "python -m app.seed"   # categories (safe to re-run)
fly certs add api.askmitra.ai             # prints the DNS record to add
```

Check: `https://askmitra-api.fly.dev/health` returns `{"status": "ok"}`.

**Automatic deploys:** Fly dashboard -> Tokens -> create a deploy token, then GitHub repo ->
Settings -> Secrets and variables -> Actions -> `FLY_API_TOKEN`. After that, every push to `main`
that passes CI deploys the API (`.github/workflows/deploy-api.yml`).

## 4. Website on Vercel

1. vercel.com -> Add New -> Project -> import the GitHub repo. **Root directory: `frontend`**.
2. Environment variables (Production):

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | Supabase Project URL |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/publishable key |
   | `NEXT_PUBLIC_API_URL` | `https://api.askmitra.ai` |
   | `API_INTERNAL_URL` | `https://api.askmitra.ai` |
   | `NEXT_PUBLIC_SITE_URL` | `https://askmitra.ai` |

3. Deploy. Then Project -> Settings -> Domains -> add `askmitra.ai` and `www.askmitra.ai`.
   Vercel deploys every push to `main` from then on.

## 5. DNS records (at your registrar)

| Type | Name | Value |
|---|---|---|
| A | `@` | as shown by Vercel (usually `76.76.21.21`) |
| CNAME | `www` | `cname.vercel-dns.com` |
| CNAME | `api` | `askmitra-api.fly.dev` (or what `fly certs add` printed) |

Certificates (https) are issued automatically within minutes. If you use Cloudflare, set the
records to **DNS only** (grey cloud) so Vercel and Fly can issue certificates.

## 6. First admin and the directory data

1. Sign in on `https://askmitra.ai` once.
2. Supabase -> SQL editor:
   `update profiles set role = 'admin' where email = '<your sign-in email>';`
   (or match on `id`, from Authentication -> Users). This is needed only for the first admin:
   after that, admins give or remove access on `https://askmitra.ai/admin/users`
   (My account -> Manage members).
3. **Doctors and dentists** run on the API server, so the database password never leaves Fly.
   Download the monthly file from https://download.cms.gov/nppes/NPI_Files.html into
   `backend/data_imports/nppes.zip`, then cut it down to Northern Virginia (about 7 MB) and run it:

   ```sh
   # on your computer (local docker): keep only Northern Virginia rows
   docker compose exec api python -c "
   import io,re,zipfile
   from app.import_nppes import _main_member
   from app.services.npi import DEFAULT_ZIPS
   hint=re.compile(r'\"VA\",\"('+'|'.join(DEFAULT_ZIPS)+')')
   with zipfile.ZipFile('/app/data_imports/nppes.zip') as zf, zf.open(_main_member(zf)) as raw:
       m=_main_member(zf); lines=io.TextIOWrapper(raw,encoding='utf-8',errors='replace',newline='')
       with zipfile.ZipFile('/app/data_imports/nppes_nova.zip','w',zipfile.ZIP_DEFLATED) as o, o.open(m,'w') as w:
           w.write(next(lines).encode()); [w.write(l.encode()) for l in lines if hint.search(l)]
   "
   # upload to one API machine and import there (pick the machine id from `fly machines list`)
   fly ssh sftp put backend/data_imports/nppes_nova.zip /tmp/nppes_nova.zip --app askmitra-api
   fly ssh console --app askmitra-api --machine <id> -C "python -m app.import_nppes /tmp/nppes_nova.zip"
   ```

4. **Restaurants:** `https://askmitra.ai/admin/directory/import` -> OpenStreetMap -> Start.

Repeat 3 and 4 every month or two to pick up new and closed places.

## 7. Before announcing it

- Privacy policy and terms pages (also required by the app stores).
- Test sign-in (email link and Google), posting a listing with photos, Ask CC, and a phone call
  link on a real phone.
- Supabase -> Database -> Backups: confirm daily backups (Pro plan for point-in-time recovery).
- Rough monthly cost to start: Vercel free, Fly ~$5-10, Supabase free (Pro $25 when you grow),
  Claude API usage (Ask CC ~2-3¢ a question, listing drafts ~1-3¢).

Next: the iOS and Android apps (docs/MOBILE.md) load this live site, so finish this first.
