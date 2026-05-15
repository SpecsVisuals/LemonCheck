# LemonCheck — Prompt Engineering Log

> Living document tracking Claude prompt design decisions, test results, and iteration history.
> Update this after every round of testing against real listings.

---

## Prompt Files

| File | Role | Step |
|------|------|------|
| `backend/prompts/system_prompt.txt` | Car analyst persona, grading rubric, output rules | Both steps |
| `backend/prompts/enrichment_prompt.txt` | Data-gathering instructions with tool sequence | Step 1 only |
| `backend/prompts/analysis_schema.json` | JSON output schema shown to Claude at analysis time | Step 2 only |

---

## Architecture Decision: Why Two Steps?

**The single-step problem:** A single-prompt approach (gather data and analyze in one call) produces weaker analysis. Claude tends to rush through tool calls without gathering complete data, and mixes data-gathering reasoning with analytical reasoning in ways that degrade output quality.

**The two-step solution:**
1. **Enrichment step** — Claude only gathers data. Tools are available; analysis is explicitly deferred. The loop runs until `stop_reason == "end_turn"` or `MAX_TOOL_CALLS = 8` is hit.
2. **Analysis step** — Claude receives the enriched summary and has no tools. This forces focused analytical reasoning on the data it has, without detours back to data-gathering.

This mirrors how a good analyst actually works: research first, then assess.

---

## System Prompt Design Decisions

**Persona over rules.** Defining Claude as a 20+-year expert car advisor (rather than a list of rules) produces more natural, confident output. The persona primes Claude to apply domain knowledge it already has without needing to enumerate every case.

**Explicit grading rubric.** A precise A–F rubric with percentage thresholds (e.g., ">10% above median = red flag") ensures consistent grading across different vehicles and price points. Without this, Claude grades too generously.

**Known issues by make/model.** Including specific reliability issues (Honda oil dilution, GM AFM lifters, etc.) lets Claude flag model-specific risks without a dedicated tool call. Significant quality improvement for common vehicles at zero API cost.

**"Return ONLY valid JSON" constraint.** Prevents Claude from wrapping the response in explanation. Combined with `_parse_deal_report`'s fence-stripping logic, this ensures clean programmatic parsing even when the instruction is occasionally ignored.

---

## Enrichment Prompt Design Decisions

**Explicit tool sequence.** Rather than letting Claude decide tool order, the prompt specifies: web_fetch → vin_decode → search_comps → price_lookup. This ensures we have vehicle identity data before searching comps, and VIN decode confirms identity before the search query is built.

**Required summary format.** The enrichment prompt specifies a structured summary output (Vehicle, Asking price, Mileage, etc.). This formats the enrichment output in a way that's easy for the analysis step to parse and reference, even though it's being read by Claude rather than code.

**"ENRICHMENT COMPLETE" signal.** The explicit end signal helps with the MAX_TOOL_CALLS fallback — when we force Claude to wrap up, we can detect whether it completed naturally vs. was cut off by the iteration cap.

**Graceful failure handling.** "If a tool fails, note the failure and continue" is critical. Without this, Claude sometimes retries failed tool calls in a loop, burning all 8 iterations on a single blocked scrape.

---

## Analysis Schema Design Decisions

**`price_delta` as integer.** Dollar amounts as integers (no cents) are cleaner in the UI and sufficient precision for deal analysis. Claude never has cent-level accuracy from search snippets anyway.

**`delta_vs_this` in CompListing.** Pre-computing the comp-to-analyzed delta in Claude's output keeps the UI simpler and lets Claude incorporate the delta into its reasoning naturally.

**`negotiation_points` as free-form strings.** Free-form strings give Claude room to write specific, data-backed points ("Comps average $17,700 — start at $15,800") rather than forcing a rigid structure that would produce generic advice.

**Grade as `Literal["A", "B", "C", "D", "F"]`.** No plus/minus. Pydantic enforces this. Prevents ambiguity in the UI (which color-codes by grade) and forces Claude to commit to a clear tier rather than hedging with "B+".

---

## Iteration Log

### v1.0 — Day 2 initial build

**What was built:**
- Two-step chain with MAX_TOOL_CALLS = 8
- System prompt: expert persona, A–F rubric, red/green flag triggers, make/model known issues
- Enrichment prompt: explicit 4-tool sequence, structured summary format, failure handling
- Analysis schema: 8 fields, all required except comps (may be empty list)

**Test results:** 24 unit tests passing. Integration tests pending API key + real listing URLs.

**Tuning backlog (to address after first real run):**
- [ ] Test grade distribution across 10+ real listings — are we too harsh or too lenient?
- [ ] Check whether JSON fence-stripping is needed in practice (model may already comply)
- [ ] Test with listings where web_fetch is blocked — does agent degrade gracefully?
- [ ] Evaluate whether 8 tool iterations is the right cap for simple vs. complex listings
- [ ] Consider adding a `data_confidence` field (high/medium/low) for insufficient data cases

---

## Testing Protocol for Real Listings

Once `ANTHROPIC_API_KEY` is set in `.env`, run integration tests:

```bash
RUN_INTEGRATION_TESTS=1 pytest backend/tests/test_agent.py -v -m integration
```

Then manually validate these archetypes and record results below:

| Archetype | Expected Grade | price_delta direction | Result | Notes |
|-----------|---------------|----------------------|--------|-------|
| Overpriced listing | D or F | Positive (above market) | TBD | |
| Below-market deal | A or B | Negative (below market) | TBD | |
| Fair listing | B or C | Near zero | TBD | |
| VIN-only input | Any | 0 (no price data) | TBD | Should note data gaps |
| Blocked scrape | Any | 0 or actual | TBD | Should not crash |
