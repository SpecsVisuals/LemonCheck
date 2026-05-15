# Architecture Decision Records

> LemonCheck — Key Technical Decisions
> 
> Each ADR follows the format: **Context → Decision → Consequences**.
> Each ADR explains the context, the choice made, and the trade-offs accepted.

---

## ADR-001: MCP Tool Orchestration Over Direct API Calls

**Status:** Accepted  
**Date:** 2025

### Context

LemonCheck needs to gather data from multiple sources before running its Claude analysis:
- The car listing itself (CarGurus / AutoTrader)
- VIN data (NHTSA free API)
- Comparable listings (Brave Search or SerpAPI)

The simplest approach would be to call those APIs directly in Python before constructing the Claude prompt — one function per data source, results assembled into a big context string.

That approach works. We chose not to use it.

### Decision

We use **Anthropic's Model Context Protocol (MCP)** to expose each data source as a named tool. Claude decides which tools to call, in what order, and uses the results to construct its analysis. The agent runs a tool-call loop (max 8 iterations) until it has enough data, then issues its final structured response.

```
User request
    │
    ▼
Enrichment prompt → Claude (with MCP tools)
    │
    ├─ tool_use: web_fetch(url)      → listing data
    ├─ tool_use: vin_decode(vin)     → NHTSA vehicle data
    └─ tool_use: search_comps(...)   → comparable listings
    │
    ▼
Analysis prompt → Claude (with enriched context)
    │
    ▼
Structured DealReport JSON
```

### Consequences

**Why this is better:**

1. **Separation of concerns.** Tool implementations are independent of the prompt. If the NHTSA API changes its response shape, we update `vin_decode.py` — the prompt doesn't change.

2. **Debuggability.** Because data gathering and reasoning are separate steps, a bad analysis can be diagnosed without re-running the whole chain. Check the enrichment output first; if the data is good, the prompt is the problem.

3. **Closer to production patterns.** Real enterprise AI deployments use tool orchestration, not prompt stuffing. MCP reflects how these systems actually work at scale — clean tool boundaries, independent failure modes, and room to add new data sources without touching the agent logic.

4. **Claude handles missing data gracefully.** If a tool returns an error or partial data, Claude can decide to try a different tool or proceed with what it has, rather than the whole pipeline failing on a network error.

**Trade-offs:**

- More complex than direct API calls — requires understanding the tool call loop and handling `tool_use` / `tool_result` message turns.
- Adds latency (each tool call is a round-trip through the agent loop).
- MCP tool sandbox in local development blocks real external HTTP calls — mitigated by fixture-based testing and a SOCKS proxy workaround for the Anthropic client.

---

## ADR-002: Supabase Magic Link Auth Over Password Auth

**Status:** Accepted  
**Date:** 2025

### Context

LemonCheck needs authentication to enforce the 5 analyses/month free tier and to associate analyses with users. The auth flow appears on the critical path — if a user has to create an account before seeing any value, a significant fraction will drop off before the gate.

Standard options considered:
- Username + password (with reset flow)
- OAuth (Google / GitHub)
- Magic link (email OTP)
- Anonymous session with email capture later

### Decision

We use **Supabase magic link auth** (`signInWithOtp`). Users enter their email, receive a link, click it, and are signed in. No password, no OAuth app setup, no credential storage.

```
User enters email
    │
    ▼
supabase.auth.signInWithOtp({ email })
    │
Supabase sends email with magic link
    │
User clicks link → redirected to /auth/callback
    │
Supabase extracts token, sets session in localStorage
    │
onAuthStateChange fires → user state updates
    │
All subsequent API calls use session.access_token as Bearer token
```

### Consequences

**Why this is better for this use case:**

1. **Zero friction at the gate.** The conversion rate from "saw the gate" to "completed sign-up" is dramatically higher with magic link than password auth. Users don't have to think of a password or worry about security.

2. **No password management burden.** No reset flows, no breach exposure, no hashed credential storage. Supabase handles the entire auth lifecycle.

3. **Real email capture.** Unlike OAuth, magic link guarantees we have a verified email address. Every signed-up user is a real, verified contact — valuable as the product grows.

4. **Supabase JWT works natively with the backend.** `supabase.auth.get_user(token)` validates the JWT server-side with real-time revocation support — better than local decode which can't check revocation.

**Trade-offs:**

- Requires the user to have email access at the moment of sign-up (not a problem for 99% of users).
- Magic links expire (typically 1 hour) — if the email is delayed, the link may be stale. Supabase handles resend.
- No social sign-in means some users who expect "Continue with Google" may hesitate. Acceptable trade-off for v1.

---

## ADR-003: Python FastAPI Over Node.js Backend

**Status:** Accepted  
**Date:** 2025

### Context

The backend needs to:
- Run an async Claude agent with a tool-call loop
- Scrape HTML listing pages
- Make multiple external HTTP calls per request
- Validate all inputs and outputs with strict schemas
- Deploy cheaply on Railway

Both Python and Node.js are reasonable choices. The team (solo developer) has experience with both.

### Decision

We use **Python FastAPI** for the backend.

```
POST /analyze
    │
    ├─ FastAPI route (async def)
    ├─ Pydantic validation (AnalysisRequest)
    ├─ Supabase auth (httpx async)
    ├─ Claude agent (anthropic async client)
    │   └─ MCP tool loop (httpx + bs4 + NHTSA API)
    ├─ Pydantic output validation (DealReport)
    └─ Supabase write (usage + analysis)
```

### Consequences

**Why Python:**

1. **Anthropic SDK is Python-native.** The `anthropic` Python SDK has the best support for tool use, streaming, and async patterns. The TypeScript SDK exists but is less mature for complex agent loops.

2. **Best scraping ecosystem.** `httpx` + `BeautifulSoup4` is the standard for async HTML scraping. The Node alternatives (`axios` + `cheerio`) work but have less community guidance for our specific patterns.

3. **Pydantic is the right tool for this job.** Every input and output in LemonCheck is strictly typed and validated. FastAPI + Pydantic gives us automatic request validation, serialization, and OpenAPI docs with zero extra work. Express equivalents (Zod, Joi) require more wiring.

4. **async/await throughout.** FastAPI is ASGI-native. Every route, every service call, every DB write is `async def`. The Claude agent's tool-call loop runs without blocking other requests.

5. **Railway deploys Python cleanly.** `requirements.txt` + `uvicorn` on `$PORT` is a two-line deploy config. No build step, no transpilation.

**Trade-offs:**

- Node.js would share a language with the React frontend, reducing context switching. Acceptable — the frontend and backend are separate processes with a clear HTTP boundary; shared language matters less than it would in a monorepo with shared types.
- Python's GIL means CPU-bound work blocks the event loop. For LemonCheck, all work is I/O-bound (API calls, scraping) so this is not a concern in practice.
- Cold start on Railway free tier is slightly slower for Python than Node. Mitigated by Railway's keep-alive and the health check endpoint.

---

*LemonCheck Architecture Decision Records — v1.0*  
*Author: Kevin Torres*
