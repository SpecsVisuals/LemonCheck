# LemonCheck — Architecture

> System design overview and component diagram.
> Update this file whenever a significant architectural change is made.

## High-Level Flow

```
User (browser)
  │
  ▼
Frontend (React + Vite, Vercel)
  │  POST /analyze or GET /demo
  ▼
Backend (FastAPI, Railway)
  │  Auth check → Usage gate → Claude agent
  ▼
Claude Sonnet 4 (Anthropic API)
  │  Tool calls (MCP protocol)
  ├──► web_fetch → listing page scrape
  ├──► vin_decode → NHTSA API
  ├──► search_comps → SerpAPI / Brave
  └──► price_lookup → market aggregation
  │
  ▼
DealReport (JSON) → returned to frontend → rendered as DealCard
```

## Data Storage (Supabase)

- `user_usage` — tracks monthly analysis count per user
- `analyses` — archives full DealReport results with metadata

## TODO: add Mermaid architecture diagram on Day 5
