/**
 * CaseStudy.jsx
 *
 * LemonCheck Case Study — Recruiter-Facing Portfolio Page
 * --------------------------------------------------------
 * A narrative page that explains what LemonCheck is, why it was built,
 * how it works technically, and what it demonstrates as a portfolio piece.
 *
 * Audience: Solutions Engineer interviewers and hiring managers.
 * Register: Conversational but substantive. Written as if spoken out loud.
 *
 * Sections:
 *   1. The Problem  — why used car buying is broken
 *   2. The Solution — what LemonCheck does and how
 *   3. Tech Stack   — table of decisions with rationale
 *   4. MCP Deep Dive — why MCP matters and what it demonstrates
 *   5. What's Next  — honest roadmap + what wasn't built yet
 *   6. About the Builder — 2-sentence bio + LinkedIn
 *
 * Plain English:
 *   This is the "I made this, here's why, here's how, here's what I learned"
 *   page. It should read like a strong interview answer, written down.
 *
 * Technical:
 *   Static page — no data fetching.
 *   All content inline, no CMS.
 *   Uses semantic HTML (article, section, h2, p) for readability and SEO.
 */

import { Link } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { ThemeToggle } from '@/components/ThemeToggle';

export default function CaseStudy() {
  return (
    <div style={styles.page}>
      {/* Nav */}
      <nav style={styles.nav}>
        <div className="container" style={styles.navInner}>
          <Link to="/" style={{ textDecoration: 'none' }}>
            <Logo size="md" />
          </Link>
          <ThemeToggle />
        </div>
      </nav>

      <main>
        {/* Hero */}
        <div style={styles.hero}>
          <div className="container" style={styles.heroInner}>
            <p style={styles.eyebrow}>Case Study</p>
            <h1 style={styles.heroTitle}>LemonCheck</h1>
            <p style={styles.heroSub}>
              An AI-powered used car deal analyzer. Here's how it was built,
              why each decision was made, and what comes next.
            </p>
            <Link to="/analysis?demo=true" style={styles.heroBtn}>
              See it in action →
            </Link>
          </div>
        </div>

        <article className="container" style={styles.article}>

          {/* ── The Problem ─────────────────────────────────────── */}
          <Section id="problem" label="01 — The Problem">
            <p>
              Buying a used car is one of the most asymmetric transactions most people
              ever make. The dealer has run thousands of deals. You've done maybe three.
              They know the margins, the real market comps, the known issues with the
              specific trim you're looking at. You have a CarGurus listing and a gut feeling.
            </p>
            <p>
              The information exists to level that playing field. Comparable listings, NHTSA
              recall data, VIN decode, days on market — it's all out there. But it takes 45
              minutes of research to pull it together for one car, and by then you're
              emotionally committed and not thinking clearly anyway.
            </p>
            <p>
              LemonCheck does that research in 30 seconds and gives you the verdict in plain
              English — including the exact lines to use when you negotiate.
            </p>
          </Section>

          {/* ── The Solution ────────────────────────────────────── */}
          <Section id="solution" label="02 — The Solution">
            <p>
              Paste a CarGurus or AutoTrader URL (or just a VIN). LemonCheck runs a
              two-step Claude analysis: first it uses MCP tools to gather real data —
              scraping the listing, decoding the VIN via the NHTSA free API, and pulling
              comparable listings via search. Then it feeds everything to a Claude agent
              with a 20-year car buyer's persona and a structured JSON output schema.
            </p>
            <p>
              The result is a letter grade (A–F), a price delta vs. market, red and green
              flags, three comp listings with price deltas, and numbered negotiation talking
              points. The whole thing takes under 30 seconds.
            </p>
            <p>
              Access is gated after 5 free analyses per month — magic link auth (no
              password) so the sign-up friction is nearly zero. The recruiter path uses
              <code style={styles.code}>?demo=true</code> to bypass auth entirely and show
              a pre-seeded result instantly.
            </p>
          </Section>

          {/* ── Tech Stack ──────────────────────────────────────── */}
          <Section id="stack" label="03 — Tech Stack">
            <p>
              Every decision was made for a reason. Here's the short version:
            </p>

            <div style={styles.tableWrapper}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Layer</th>
                    <th style={styles.th}>Choice</th>
                    <th style={styles.th}>Why</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['AI Model', 'Claude Sonnet 4', 'Best balance of speed and structured JSON output for this use case. Haiku is cheaper but less reliable on complex analysis; Opus is slower than needed.'],
                    ['Integration Pattern', 'MCP tool orchestration', 'Mirrors how enterprise AI integrations actually work — not just prompt-in, answer-out. Clean separation between data gathering and reasoning, with independently debuggable steps.'],
                    ['Backend', 'Python FastAPI', 'Async-first, Pydantic native, well-documented. Deploys easily to Railway. The Python ecosystem also has the best libraries for the scraping + AI work.'],
                    ['Frontend', 'React + Vite', "Fast dev experience, excellent ecosystem, most likely to match the hiring company's stack. Vite's HMR makes iteration fast."],
                    ['Auth', 'Supabase magic link', 'Zero password management burden. One-click sign-in via email means real users actually complete it. Service role key handles RLS bypass for backend writes.'],
                    ['Database', 'Supabase Postgres', 'Row-level security, instant REST API, generous free tier. Analyses persist per-user for potential history feature later.'],
                    ['Deploy', 'Vercel + Railway', 'Both have free tiers and GitHub integration. Zero-config for the respective frameworks. Railway handles Python/FastAPI cleanly.'],
                  ].map(([layer, choice, why]) => (
                    <tr key={layer} style={styles.tr}>
                      <td style={{ ...styles.td, ...styles.tdLabel }}>{layer}</td>
                      <td style={{ ...styles.td, ...styles.tdChoice }}>{choice}</td>
                      <td style={{ ...styles.td, ...styles.tdWhy }}>{why}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          {/* ── MCP Deep Dive ───────────────────────────────────── */}
          <Section id="mcp" label="04 — Why MCP?">
            <p>
              Model Context Protocol (MCP) is Anthropic's open standard for connecting
              AI models to external tools. In LemonCheck, it orchestrates three tools:
              a listing scraper, a NHTSA VIN decoder, and a comparable listings search.
            </p>
            <p>
              The alternative would be direct API calls embedded in the agent prompt.
              That works for simple cases, but MCP gives you something more useful: a
              clean separation between "what data do I need" and "how do I get it." The
              agent asks for data by tool name; the tool implementation can change without
              touching the prompt or the business logic.
            </p>
            <p>
              More importantly: MCP is where enterprise AI deployments are headed.
              Knowing how to design MCP tool schemas, handle tool call loops, and manage
              failure modes (tools that time out, APIs that go down) is exactly the kind
              of hands-on knowledge that shows in technical conversations.
            </p>
            <p>
              The two-step chain — enrichment loop first, analysis call second — is
              deliberate. It separates data gathering from reasoning, which makes both
              steps debuggable independently. If the analysis is wrong, you can check the
              enrichment data separately without re-running the full chain.
            </p>
          </Section>

          {/* ── What's Next ─────────────────────────────────────── */}
          <Section id="next" label="05 — What I'd Build Next">
            <p>
              This is a v1. A few things deliberately left for later:
            </p>
            <p>
              <strong>PDF export.</strong> The negotiation talking points are the thing
              people want to bring into a dealership. A shareable, printable PDF of the
              full report is the obvious next feature.
            </p>
            <p>
              <strong>Analysis history.</strong> The schema stores every analysis per user.
              A simple history page would let users track listings they're monitoring over time.
            </p>
            <p>
              <strong>Real-time price tracking.</strong> Hook into a listings API and alert
              users when a saved listing drops in price or goes off market.
            </p>
            <p>
              <strong>Make/model reliability layer.</strong> The agent prompt currently
              relies on Claude's training knowledge for known issues. Adding a structured
              reliability database (Consumer Reports data, forum scraping) would make the
              red flags more specific and defensible.
            </p>
            <p>
              <strong>What wasn't built yet:</strong> The mobile UI needs polish below
              375px. The MCP tool sandbox blocks live NHTSA and search API calls
              during development — the tools are built and tested with fixtures, but a
              real Brave Search key in production would complete that flow. The upgrade/Pro
              tier is a placeholder.
            </p>
          </Section>

          {/* ── About ───────────────────────────────────────────── */}
          <Section id="about" label="06 — About the Builder">
            <p>
              Kevin Torres. I build things that make complex information easy to act on —
              LemonCheck is a clean example of that. Real tech stack, real API integrations,
              real user problem. If you're curious about the work, I'd love to talk.
            </p>
            <div style={styles.aboutLinks}>
              <a href="mailto:karbonlabs01@gmail.com" style={styles.aboutLink}>
                karbonlabs01@gmail.com →
              </a>
              <a href="mailto:specsvisuals@gmail.com" style={styles.aboutLink}>
                specsvisuals@gmail.com →
              </a>
              <a href="https://linkedin.com/in/kevinatorres" target="_blank" rel="noopener noreferrer" style={styles.aboutLink}>
                LinkedIn →
              </a>
              <Link to="/" style={styles.aboutLink}>
                Try LemonCheck →
              </Link>
            </div>
          </Section>

        </article>
      </main>

      <footer style={styles.footer}>
        <div className="container" style={styles.footerInner}>
          <Logo size="sm" />
          <p style={styles.footerText}>Built to get hired. Designed to actually help people.</p>
        </div>
      </footer>
    </div>
  );
}


// ── Section wrapper ────────────────────────────────────────────────────────

function Section({ id, label, children }) {
  return (
    <section id={id} style={styles.section}>
      <p style={styles.sectionLabel}>{label}</p>
      <div style={styles.sectionBody}>{children}</div>
    </section>
  );
}


// ── Styles ─────────────────────────────────────────────────────────────────

const styles = {
  page: { minHeight: '100vh', background: 'var(--color-bg)' },
  nav: { borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)', position: 'sticky', top: 0, zIndex: 'var(--z-raised)' },
  navInner: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60 },

  hero: {
    background: 'var(--color-cream)',
    borderBottom: '1px solid var(--color-border)',
    padding: '80px 0 64px',
  },
  heroInner: { maxWidth: 640 },
  eyebrow: { fontSize: 12, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-green)', marginBottom: 16 },
  heroTitle: { fontSize: 'clamp(40px, 6vw, 64px)', fontWeight: 800, color: 'var(--color-text-primary)', marginBottom: 16, lineHeight: 1.1 },
  heroSub: { fontSize: 18, lineHeight: 1.7, color: 'var(--color-text-secondary)', marginBottom: 32, maxWidth: 520 },
  heroBtn: { display: 'inline-block', padding: '12px 28px', borderRadius: 'var(--radius-md)', background: 'var(--color-yellow)', color: 'var(--color-text-primary)', fontSize: 15, fontWeight: 600, textDecoration: 'none' },

  article: { maxWidth: 680, paddingTop: 64, paddingBottom: 96 },

  section: { marginBottom: 72 },
  sectionLabel: { fontSize: 11, fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--color-sand)', marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid var(--color-border)' },
  sectionBody: { display: 'flex', flexDirection: 'column', gap: 20 },

  // Body text — all child <p> tags get these via parent
  // (applied inline since no CSS class system here)
  code: { fontFamily: 'var(--font-mono)', fontSize: '0.9em', background: 'var(--color-surface)', padding: '2px 6px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' },

  tableWrapper: { overflowX: 'auto', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 14 },
  th: { padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-secondary)', background: 'var(--color-surface-raised)', borderBottom: '1px solid var(--color-border)' },
  tr: { borderBottom: '1px solid var(--color-border)' },
  td: { padding: '12px 16px', verticalAlign: 'top', lineHeight: 1.55, color: 'var(--color-text-primary)' },
  tdLabel: { fontWeight: 600, whiteSpace: 'nowrap', color: 'var(--color-text-primary)', width: '15%' },
  tdChoice: { fontWeight: 500, color: 'var(--color-green)', width: '22%' },
  tdWhy: { color: 'var(--color-text-secondary)', width: '63%' },

  aboutLinks: { display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 8 },
  aboutLink: { color: 'var(--color-green)', fontWeight: 600, fontSize: 15, textDecoration: 'none' },

  footer: { borderTop: '1px solid var(--color-border)', padding: '32px 0' },
  footerInner: { display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' },
  footerText: { fontSize: 13, color: 'var(--color-text-tertiary)' },
};

// Apply body text styles to all <p> elements inside .article
// Since we're using inline styles throughout, style the p tags via a global rule
if (typeof document !== 'undefined' && !document.getElementById('lc-case-study-styles')) {
  const style = document.createElement('style');
  style.id = 'lc-case-study-styles';
  style.textContent = `
    .lc-case-study p {
      font-size: 16px;
      line-height: 1.75;
      color: var(--color-text-secondary);
    }
    .lc-case-study p strong {
      color: var(--color-text-primary);
      font-weight: 600;
    }
    .lc-case-study tr:last-child {
      border-bottom: none;
    }
    .lc-case-study a[href]:not([style]) {
      color: var(--color-green);
    }
  `;
  document.head.appendChild(style);
}
