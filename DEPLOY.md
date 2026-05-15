# LemonCheck — Deploy Guide

> Step-by-step instructions to go from local code to live URLs.
> Estimated time: 30–45 minutes.

---

## Pre-Flight Checklist

Before deploying, confirm all of these locally:

```bash
# Backend builds clean
uvicorn backend.main:app --port 8000
curl http://localhost:8000/health
# → {"status": "ok", "service": "lemoncheck-api"}

# Frontend builds clean
cd frontend && npm run build
# → "88 modules transformed" with no errors

# Demo endpoint works with real API key
python scripts/seed_demo.py --url "https://www.cargurus.com/Cars/..."
# → saves backend/demo_cache.json
```

---

## Step 1 — Push to GitHub

```bash
# If you haven't initialized git yet:
git init
git add .
git commit -m "feat: LemonCheck v1 — full stack AI car deal analyzer"

# Create a new repo on github.com/new, then:
git remote add origin git@github.com:YOUR_USERNAME/lemoncheck.git
git push -u origin main
```

> **Important:** Make sure `.env` is in `.gitignore` (it is — check `.env.example` exists in the commit, `.env` does not).

---

## Step 2 — Deploy Backend to Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your `lemoncheck` repo
3. Railway will auto-detect Python via `nixpacks` and read `railway.toml`
4. In **Settings → Variables**, add every key from `.env.example`:

```
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SERPAPI_KEY=...           (optional — for search_comps tool)
BRAVE_SEARCH_KEY=...      (optional — alternative search API)
FRONTEND_URL=             (fill in after Vercel deploy in Step 3)
```

5. Railway will deploy automatically. Check the **Deployments** tab.
6. Copy your Railway URL (e.g. `https://lemoncheck-api.up.railway.app`)
7. Test it: `curl https://lemoncheck-api.up.railway.app/health`

---

## Step 3 — Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → import your GitHub repo
2. Set **Root Directory** to `frontend`
3. Vercel auto-detects Vite — no framework override needed
4. In **Settings → Environment Variables**, add:

```
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=https://lemoncheck-api.up.railway.app
VITE_SITE_URL=https://lemoncheck.vercel.app
```

5. Deploy. Copy your Vercel URL (e.g. `https://lemoncheck.vercel.app`)

---

## Step 4 — Wire Frontend URL into Railway

1. Go back to Railway → your project → Variables
2. Set `FRONTEND_URL=https://lemoncheck.vercel.app`
3. Railway will redeploy automatically (CORS now allows your Vercel domain)

---

## Step 5 — Configure Supabase

### Apply the database schema

1. Go to [supabase.com](https://supabase.com) → your project → **SQL Editor**
2. Paste and run the contents of `docs/supabase-schema.sql`

### Set the auth redirect URL

1. Go to **Authentication → URL Configuration**
2. Add to **Redirect URLs**: `https://lemoncheck.vercel.app/auth/callback`
3. Also add localhost for local dev: `http://localhost:5173/auth/callback`

### Set the site URL

1. Under **URL Configuration → Site URL**: `https://lemoncheck.vercel.app`

---

## Step 6 — Seed the Demo Cache

Once the backend is live, seed the demo result:

```bash
# From repo root, with .env loaded
ANTHROPIC_API_KEY=sk-ant-... python scripts/seed_demo.py \
  --url "https://www.cargurus.com/Cars/YOUR_CHOSEN_LISTING_URL"
```

Pick a listing that tells a good story — a B or C grade with 2–3 real red flags works best. Commit `backend/demo_cache.json` to the repo (it has no PII — just market data and AI analysis).

```bash
git add backend/demo_cache.json
git commit -m "feat: seed demo cache with real listing analysis"
git push
```

Railway will redeploy with the demo cache in place.

---

## Step 7 — Smoke Test

Test all three paths:

```bash
# 1. Demo (no auth) — should return DealReport instantly
curl https://lemoncheck-api.up.railway.app/demo

# 2. Browser demo mode
open "https://lemoncheck.vercel.app/analysis?demo=true"

# 3. Auth flow
open "https://lemoncheck.vercel.app"
# → paste a listing URL → sign in with magic link → get analysis

# 4. Mobile — paste this URL in iMessage to yourself
https://lemoncheck.vercel.app/analysis?demo=true
# → open on iPhone → check 375px layout
```

---

## Step 8 — Final README Update

Once you have the live URLs, update `README.md`:

```markdown
🔗 **Live demo:** https://lemoncheck.vercel.app
🔗 **Demo mode (no login):** https://lemoncheck.vercel.app/analysis?demo=true
🔗 **Case study:** https://lemoncheck.vercel.app/case-study
🔗 **API docs:** https://lemoncheck-api.up.railway.app/docs
```

---

## Environment Variables Reference

| Variable | Where | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Railway | Anthropic API key — `sk-ant-...` |
| `SUPABASE_URL` | Railway + Vercel | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Railway + Vercel | Public anon key (safe to expose) |
| `SUPABASE_SERVICE_ROLE_KEY` | Railway only | Service role key — never expose to frontend |
| `FRONTEND_URL` | Railway | Your Vercel URL (for CORS) |
| `SERPAPI_KEY` | Railway | SerpAPI key for comparable search |
| `BRAVE_SEARCH_KEY` | Railway | Alternative to SerpAPI |
| `VITE_SUPABASE_URL` | Vercel | Same as SUPABASE_URL, prefixed for Vite |
| `VITE_SUPABASE_ANON_KEY` | Vercel | Same as SUPABASE_ANON_KEY, prefixed for Vite |
| `VITE_API_URL` | Vercel | Your Railway backend URL |
| `VITE_SITE_URL` | Vercel | Your Vercel frontend URL (for magic link redirect) |

---

*If anything breaks, check Railway logs first (`railway logs`), then Vercel function logs, then Supabase auth logs.*
