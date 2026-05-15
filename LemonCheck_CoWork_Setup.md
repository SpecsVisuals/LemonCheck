# 🍋 LemonCheck — CoWork Setup Guide

> Paste the System Instructions first, then fire the First Prompt. Build day by day from there.

---

## STEP 1 — CoWork System Instructions

Paste this into CoWork's **Instructions / System Prompt** field before starting any session:

```
You are a senior full-stack AI engineer helping build LemonCheck — an AI-powered used car deal analyzer.

TECH STACK:
- Frontend: React + Vite, deployed on Vercel
- Backend: Python FastAPI, deployed on Railway
- AI Engine: Claude Sonnet 4 via Anthropic API with custom MCP tool orchestration
- Auth + DB: Supabase (Postgres + magic link auth)

PROJECT CONTEXT:
- This is a portfolio/work sample for a Solutions Engineer job search (AV → AI transition)
- Code quality and documentation matter as much as functionality — recruiters will review this
- Every file should include a clear docstring or comment block explaining what it does and why
- The /docs folder must stay updated as we build

FOLDER STRUCTURE:
- Follow the exact structure defined in LemonCheck_Folder_Structure below
- Never create files outside this structure without asking first

CODE STANDARDS:
- Python: type hints everywhere, Pydantic models for all data, async/await throughout
- React: functional components + hooks only, no class components
- All secrets via environment variables (.env), never hardcoded
- Write tests in /backend/tests alongside every new feature

DUAL-LEVEL EXPLANATIONS:
When I ask you to "explain" any file, component, or decision, always give me:
1. Plain-English summary (as if presenting to a non-technical recruiter)
2. Technical deep-dive (for engineering interviewers)
Always keep both levels ready.
```

---

## STEP 2 — First Prompt (Send This to Start)

```
Let's initialize the LemonCheck project. Please do the following in order, confirming after each step:

1. Create the complete folder structure (all folders + placeholder files with descriptive comment headers)

2. Set up the React + Vite frontend in /frontend

3. Set up the FastAPI backend in /backend with requirements.txt including:
   httpx, beautifulsoup4, fastapi, uvicorn, supabase, anthropic, pydantic, pytest

4. Create .env.example documenting every environment variable:
   ANTHROPIC_API_KEY=
   SUPABASE_URL=
   SUPABASE_ANON_KEY=
   SERPAPI_KEY=
   BRAVE_SEARCH_KEY=
   DEMO_CACHE_SECRET=
   FRONTEND_URL=

5. Create Supabase schema SQL for:
   - user_usage (user_id UUID, analysis_count INT, month TEXT, updated_at TIMESTAMP)
   - analyses (id UUID, user_id UUID, listing_url TEXT, result_json JSONB, created_at TIMESTAMP)

6. Write README.md with: project overview, problem statement, tech stack table, local setup instructions, and live URL placeholder

Confirm what was created after each step before moving to the next.
```

---

## STEP 3 — Daily Build Prompts

### Day 1 — MCP Data Tools
```
Build the MCP data layer. Work through these files in order:

1. backend/mcp/tools/web_fetch.py
   - Takes a CarGurus or AutoTrader listing URL
   - Fetches with httpx, parses with BeautifulSoup
   - Returns normalized dict: {year, make, model, trim, mileage, price, location, days_on_market, seller_type}

2. backend/mcp/tools/vin_decode.py
   - Calls NHTSA free API: https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json
   - No API key required
   - Returns: make, model, year, trim, body_style, engine

3. backend/mcp/tools/search_comps.py
   - Uses SerpAPI or Brave Search API
   - Query: "{year} {make} {model} {trim} for sale near {location}"
   - Returns top 5 results with: title, price, url, mileage if available

4. backend/mcp/server.py
   - Register all three tools as MCP tools
   - Add tool schemas and descriptions

5. backend/tests/test_tools.py
   - Unit test each tool with mock/fixture data
   - Add sample fixture files in backend/tests/fixtures/

6. Update docs/mcp-tools.md with tool API reference

Test each tool with a real listing before moving to the next.
```

### Day 2 — Claude Agent Chain
```
Build the Claude agent. Files to create:

1. backend/prompts/system_prompt.txt
   - Expert used car buyer's agent persona, 20+ years experience
   - Instructions for deal analysis: price vs. market, red flags, green flags, negotiation leverage
   - Make/model-specific known issues awareness

2. backend/prompts/analysis_schema.json
   - Define the full JSON output schema:
     {grade: "A-F", price_delta: int, price_verdict: string,
      red_flags: [{title, description}],
      green_flags: [{title, description}],
      comps: [{title, price, mileage, url, delta_vs_this}],
      negotiation_points: [string],
      summary: string}

3. backend/prompts/enrichment_prompt.txt
   - Step 1 prompt: instruct Claude to use MCP tools to gather all listing data

4. backend/services/claude_agent.py
   - Two-step chain: enrichment loop → analysis call
   - Returns typed DealReport Pydantic model
   - Handle tool call loop with max 8 iterations

5. backend/models/analysis.py
   - Pydantic models: AnalysisRequest, DealReport, CompListing, Flag

6. backend/tests/test_agent.py
   - Integration test with 3 real CarGurus URLs
   - Validate output schema on each

After building, test with these 3 listing types: overpriced, underpriced, and fairly priced.
Document what worked and what needed tuning in docs/prompt-engineering.md.
```

### Day 3 — Auth & Usage Gating
```
Build the auth and usage gating layer:

1. backend/routers/auth.py
   - Middleware that runs on every /analyze request
   - Logic order:
     a. Check for ?demo=true → skip all checks, return demo result
     b. Check Authorization header → validate Supabase JWT
     c. Look up user_usage for current month → check count < 5
     d. If over limit → return 402 with {error: "limit_reached", upgrade_url: "/pro"}
   - Helper: increment_usage(user_id) after successful analysis

2. backend/routers/demo.py
   - GET /demo → return cached DealReport from file/Redis
   - Must look real: use an actual listing that analyzes well

3. scripts/seed_demo.py
   - Run a real analysis on a known good listing
   - Save result to backend/demo_cache.json
   - This is what ?demo=true returns

4. backend/routers/analysis.py
   - POST /analyze with AnalysisRequest body
   - Wire auth middleware → agent → response
   - Return DealReport JSON

5. frontend/src/hooks/useAuth.js
   - Supabase magic link login
   - Session state management

6. frontend/src/hooks/useUsageGate.js
   - Check if user is authenticated
   - Show email gate modal if not
   - Show upgrade prompt if at limit

Test all three paths:
- ?demo=true → instant result, no auth
- Authenticated, under limit → full analysis
- Authenticated, over limit → 402 upgrade prompt
```

### Day 4 — Frontend UI
```
Build the full frontend. Start with the most important component and work outward:

1. frontend/src/components/DealCard.jsx (build this first — it's the hero)
   - Letter grade: large, bold, color-coded (A=green, B=blue, C=yellow, D=orange, F=red)
   - Price verdict sentence: "This car is priced $1,200 BELOW market"
   - Red flags section: expandable list with icons
   - Green flags section: expandable list with icons
   - Comparable listings: 3 cards side by side (title, price, mileage, delta vs. this car)
   - Negotiation talking points: numbered list
   - Share button: copy unique analysis URL to clipboard

2. frontend/src/components/SearchInput.jsx
   - URL input with validation (must be CarGurus or AutoTrader URL)
   - VIN input alternative with format validation
   - Submit button with loading state

3. frontend/src/components/LoadingStates.jsx
   - Animated cycling text:
     "Fetching listing data..." → "Searching comparable listings..." → "Running deal analysis..."
   - Progress bar that fills over ~8 seconds
   - Small car icon animation if possible

4. frontend/src/pages/Home.jsx
   - Hero: "Is it a good deal? Find out in 30 seconds."
   - SearchInput component
   - 3-icon value prop: Real market data · AI analysis · Plain English
   - Example output teaser (blurred/obscured to tease)

5. frontend/src/pages/Analysis.jsx
   - Loading state → DealCard result
   - Share this analysis button
   - "Run another analysis" CTA

6. frontend/src/pages/CaseStudy.jsx
   - Written narrative (not bullet points) explaining:
     What LemonCheck is and why it was built
     The tech stack and key decisions
     What the MCP tools do and why MCP was chosen
     What you'd build next
   - This is the recruiter-facing artifact inside the product

DESIGN DIRECTION (updated):
- Light mode default. Dark mode toggle always visible with a fun wash/ripple transition animation.
- Premium but approachable — serious in how data is presented, loose and warm everywhere else.
- Vibe: "car shopping with a funny, trustworthy older relative." Confident data, human delivery.
- Tone of voice: dry and confident. "This one's overpriced. We checked." Never mean, never stuffy.
- Kill the Bloomberg Terminal reference. Kill "not playful."

LOGO:
- Wordmark: "LEMON" bold full-weight + "CHECK" lighter weight, smaller, stacked below on a new line.
- Logo mark: lemon silhouette as the O in LEMON, yellow accent color. Placeholder — will develop further.

COLOR PALETTE (earth tone, calm on landing):
- Primary accent: citrus yellow (#FFD600 range)
- Supporting accents: warm green, sand, cream
- Very little blue — only where semantically necessary (links, info states)
- All colors should feel earth-tone leaning. Sense of calm when first landing. Not neon, not corporate.
- Dark mode: near-black background, same earth-tone accents

TYPOGRAPHY:
- "LEMON" — bold display weight
- "CHECK" — light/regular weight, smaller, below
- Body: system-ui / Inter — clean, fast, readable

Mobile-first — must look excellent at 375px width.
```

### Day 5 — Deploy & Polish
```
Ship it. Work through this checklist:

1. Deploy frontend to Vercel
   - vercel deploy from /frontend directory
   - Set all environment variables in Vercel dashboard
   - Confirm live URL works

2. Deploy backend to Railway
   - Connect GitHub repo
   - Set environment variables
   - Confirm /demo endpoint returns a result

3. Test the full ?demo=true flow on:
   - Desktop Chrome
   - Mobile Safari (375px)
   - Share the URL in Slack/iMessage to yourself — confirm it looks right

4. Final README.md pass
   - Add live URL at the top
   - Add architecture diagram (ASCII or Mermaid)
   - Add "Built by [Your Name]" with LinkedIn link

5. docs/decisions.md — write 3 Architecture Decision Records:
   - Why MCP over direct API calls
   - Why magic link auth over password auth
   - Why FastAPI over Node.js backend

6. Confirm /case-study page reads well out loud (you'll talk through it in interviews)

Give me the final live URL and ?demo=true URL when done.
```

---

## Folder Structure Reference

```
lemoncheck/
├── README.md                          # Project overview, setup, architecture
├── .env.example                       # All required env vars documented
├── docker-compose.yml                 # Local dev environment
│
├── frontend/                          # React + Vite web app
│   ├── src/
│   │   ├── components/
│   │   │   ├── DealCard.jsx           # Hero — letter grade, flags, comps, tips
│   │   │   ├── SearchInput.jsx        # URL + VIN input with validation
│   │   │   ├── LoadingStates.jsx      # Animated progress messages
│   │   │   ├── ComparableListings.jsx # 3-up comparable listing cards
│   │   │   └── NegotiationTips.jsx    # Expandable tips section
│   │   ├── pages/
│   │   │   ├── Home.jsx               # Landing page with input
│   │   │   ├── Analysis.jsx           # Results page
│   │   │   ├── CaseStudy.jsx          # Recruiter-facing case study
│   │   │   └── Login.jsx              # Magic link auth
│   │   ├── hooks/
│   │   │   ├── useAnalysis.js         # API call + loading state
│   │   │   ├── useAuth.js             # Supabase auth state
│   │   │   └── useUsageGate.js        # Free tier check logic
│   │   ├── lib/
│   │   │   ├── supabase.js            # Supabase client init
│   │   │   └── api.js                 # Backend API wrappers
│   │   └── styles/                    # Global CSS + design tokens
│   ├── public/                        # favicon, OG images
│   ├── index.html
│   └── vite.config.js
│
├── backend/                           # Python FastAPI app
│   ├── main.py                        # App entry — routes, CORS, middleware
│   ├── requirements.txt
│   ├── routers/
│   │   ├── analysis.py                # POST /analyze — main endpoint
│   │   ├── auth.py                    # Auth validation + usage gating
│   │   └── demo.py                    # GET /demo — cached demo response
│   ├── services/
│   │   ├── claude_agent.py            # Two-step Claude chain orchestrator
│   │   ├── usage_tracker.py           # Supabase usage read/write
│   │   └── cache.py                   # Analysis result caching
│   ├── mcp/
│   │   ├── server.py                  # MCP server + tool registration
│   │   └── tools/
│   │       ├── web_fetch.py           # Listing scraper (httpx + BS4)
│   │       ├── vin_decode.py          # NHTSA API integration
│   │       ├── search_comps.py        # Comparable listings search
│   │       └── price_lookup.py        # Market range aggregation
│   ├── prompts/
│   │   ├── system_prompt.txt          # Car analyst persona + instructions
│   │   ├── analysis_schema.json       # JSON output schema
│   │   └── enrichment_prompt.txt      # Step 1 data gathering prompt
│   ├── models/
│   │   ├── analysis.py                # AnalysisRequest, DealReport, CompListing
│   │   └── user.py                    # User, UsageRecord models
│   └── tests/
│       ├── test_tools.py              # MCP tool unit tests
│       ├── test_agent.py              # Claude chain integration tests
│       ├── test_api.py                # Endpoint tests
│       └── fixtures/                  # Sample listings, expected outputs
│
├── docs/                              # Living documentation
│   ├── architecture.md                # System design + diagrams
│   ├── prompt-engineering.md          # Claude prompt iteration log
│   ├── mcp-tools.md                   # MCP tool API reference
│   ├── api-reference.md               # FastAPI endpoint docs
│   └── decisions.md                   # Architecture Decision Records
│
└── scripts/                           # Utility scripts
    ├── seed_demo.py                   # Generate + cache demo result
    ├── test_listings.py               # Batch test 20 real listings
    └── check_accuracy.py              # Grade accuracy vs. outcomes
```

---

## Quick Reference — Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| AI Model | Claude Sonnet 4 | Best balance of speed + reasoning for structured output |
| Integration Pattern | MCP tool orchestration | Mirrors real enterprise AI integration — better recruiter signal than direct API calls |
| Auth | Supabase magic link | Frictionless for users, no password management burden |
| Access Model | 1 free → email gate → 5/month | Wow moment before gate + real user list for job search |
| Demo Mode | `?demo=true` param | Recruiter frictionless path without compromising real funnel |
| Frontend Deploy | Vercel | Free, instant, connects to GitHub |
| Backend Deploy | Railway | Free tier, simple env var management, supports Python |

---

*LemonCheck — Work Sample Playbook v1.0*
*Built to get hired. Designed to actually help people.*
