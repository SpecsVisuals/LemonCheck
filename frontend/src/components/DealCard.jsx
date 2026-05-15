/**
 * DealCard.jsx
 *
 * Deal Analysis Result Card — The Hero Component
 * ------------------------------------------------
 * Renders the full output of a LemonCheck analysis in a structured,
 * human-readable layout. This is the thing users actually care about.
 *
 * Sections (in order):
 *   1. Header     — Letter grade (large, color-coded) + price verdict + summary
 *   2. Red flags  — Expandable list of concerns with icons
 *   3. Green flags — Expandable list of positives with icons
 *   4. Comparables — 3-up comparable listing cards with delta vs. this car
 *   5. Negotiation — Numbered talking points the user can bring to the dealer
 *   6. Share       — Copy a shareable URL to clipboard
 *
 * Props:
 *   report — DealReport object (matches backend Pydantic model):
 *     { grade, price_delta, price_verdict, summary,
 *       red_flags[{title, description}],
 *       green_flags[{title, description}],
 *       comps[{title, price, mileage, url, delta_vs_this}],
 *       negotiation_points[string] }
 *   analysisId — optional UUID for shareable URL
 *   className  — additional CSS classes
 *
 * Plain English:
 *   This is the payoff — the moment the user finds out if the car is worth it.
 *   Grade front-and-center, plain-English verdict right below it, then the
 *   supporting evidence. Designed to be read in 60 seconds.
 *
 * Technical:
 *   Fully controlled component — no internal data fetching.
 *   Flags use local toggle state for expand/collapse.
 *   Share uses the Clipboard API with a fallback prompt().
 */

import { useState } from 'react';

// ── Grade config ───────────────────────────────────────────────────────────

const GRADE_CONFIG = {
  A: { color: 'var(--color-grade-a)', bg: 'var(--color-grade-a-bg)', label: 'Great deal' },
  B: { color: 'var(--color-grade-b)', bg: 'var(--color-grade-b-bg)', label: 'Good deal' },
  C: { color: 'var(--color-grade-c)', bg: 'var(--color-grade-c-bg)', label: 'Fair deal' },
  D: { color: 'var(--color-grade-d)', bg: 'var(--color-grade-d-bg)', label: 'Overpriced' },
  F: { color: 'var(--color-grade-f)', bg: 'var(--color-grade-f-bg)', label: 'Avoid' },
};

function gradeConfig(grade) {
  return GRADE_CONFIG[grade?.toUpperCase()] ?? GRADE_CONFIG['C'];
}

function formatDelta(delta) {
  if (!delta && delta !== 0) return null;
  const abs = Math.abs(delta).toLocaleString('en-US');
  if (delta < 0) return { text: `$${abs} below market`, positive: true };
  if (delta > 0) return { text: `$${abs} above market`, positive: false };
  return { text: 'at market price', positive: null };
}


// ── Main component ─────────────────────────────────────────────────────────

export function DealCard({ report, analysisId, className = '' }) {
  const [redExpanded, setRedExpanded] = useState(true);
  const [greenExpanded, setGreenExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  if (!report) return null;

  const config = gradeConfig(report.grade);
  const delta = formatDelta(report.price_delta);

  const handleShare = async () => {
    const url = analysisId
      ? `${window.location.origin}/analysis/${analysisId}`
      : window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt('Copy this link:', url);
    }
  };

  return (
    <div className={`lc-deal-card ${className}`} style={styles.card}>

      {/* ── 1. Header ──────────────────────────────────────────────────── */}
      <div style={styles.header}>
        {/* Grade badge */}
        <div style={{ ...styles.gradeBadge, color: config.color, background: config.bg }}>
          <span style={styles.gradeLetterLarge}>{report.grade}</span>
          <span style={styles.gradeLabel}>{config.label}</span>
        </div>

        {/* Verdict + summary */}
        <div style={styles.verdictBlock}>
          <p style={styles.priceVerdict}>{report.price_verdict}</p>
          {delta && (
            <span style={{ ...styles.deltaPill, color: delta.positive ? 'var(--color-grade-a)' : delta.positive === false ? 'var(--color-grade-f)' : 'var(--color-text-secondary)', background: delta.positive ? 'var(--color-grade-a-bg)' : delta.positive === false ? 'var(--color-grade-f-bg)' : 'var(--color-surface)' }}>
              {delta.text}
            </span>
          )}
          <p style={styles.summary}>{report.summary}</p>
        </div>
      </div>

      <div style={styles.divider} />

      {/* ── 2. Red flags ───────────────────────────────────────────────── */}
      {report.red_flags?.length > 0 && (
        <FlagSection
          title={`Red flags (${report.red_flags.length})`}
          flags={report.red_flags}
          isExpanded={redExpanded}
          onToggle={() => setRedExpanded(v => !v)}
          variant="red"
        />
      )}

      {/* ── 3. Green flags ─────────────────────────────────────────────── */}
      {report.green_flags?.length > 0 && (
        <FlagSection
          title={`Green flags (${report.green_flags.length})`}
          flags={report.green_flags}
          isExpanded={greenExpanded}
          onToggle={() => setGreenExpanded(v => !v)}
          variant="green"
        />
      )}

      <div style={styles.divider} />

      {/* ── 4. Comparable listings ─────────────────────────────────────── */}
      {report.comps?.length > 0 && (
        <section style={styles.section}>
          <h3 style={styles.sectionTitle}>Similar cars for sale nearby</h3>
          <div style={styles.compsGrid}>
            {report.comps.slice(0, 3).map((comp, i) => (
              <CompCard key={i} comp={comp} />
            ))}
          </div>
        </section>
      )}

      <div style={styles.divider} />

      {/* ── 5. Negotiation points ──────────────────────────────────────── */}
      {report.negotiation_points?.length > 0 && (
        <section style={styles.section}>
          <h3 style={styles.sectionTitle}>
            <NegotiateIcon /> What to say when you negotiate
          </h3>
          <ol style={styles.negotiationList}>
            {report.negotiation_points.map((point, i) => (
              <li key={i} style={styles.negotiationItem}>
                <span style={styles.negotiationNum}>{i + 1}</span>
                <span style={styles.negotiationText}>{point}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <div style={styles.divider} />

      {/* ── 6. Share ───────────────────────────────────────────────────── */}
      <div style={styles.shareRow}>
        <p style={styles.shareHint}>Know someone car shopping? Send them this.</p>
        <button onClick={handleShare} style={styles.shareBtn}>
          {copied ? <><CheckIcon /> Copied!</> : <><ShareIcon /> Share this analysis</>}
        </button>
      </div>

    </div>
  );
}


// ── FlagSection ────────────────────────────────────────────────────────────

function FlagSection({ title, flags, isExpanded, onToggle, variant }) {
  const isRed = variant === 'red';
  const accentColor = isRed ? 'var(--color-grade-f)' : 'var(--color-grade-a)';
  const accentBg    = isRed ? 'var(--color-grade-f-bg)' : 'var(--color-grade-a-bg)';
  const icon        = isRed ? '⚑' : '✓';

  return (
    <section style={styles.section}>
      <button onClick={onToggle} style={styles.flagToggle} aria-expanded={isExpanded}>
        <span style={{ ...styles.flagToggleLabel, color: accentColor }}>{icon} {title}</span>
        <ChevronIcon rotated={isExpanded} />
      </button>

      {isExpanded && (
        <ul style={styles.flagList}>
          {flags.map((flag, i) => (
            <li key={i} style={{ ...styles.flagItem, borderLeftColor: accentColor }}>
              <div style={{ ...styles.flagDot, background: accentBg, color: accentColor }}>
                {icon}
              </div>
              <div>
                <p style={styles.flagTitle}>{flag.title}</p>
                <p style={styles.flagDesc}>{flag.description}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}


// ── CompCard ───────────────────────────────────────────────────────────────

function CompCard({ comp }) {
  const delta = comp.delta_vs_this;
  const deltaStr = delta === 0 ? 'same price'
    : delta > 0 ? `$${delta.toLocaleString()} more`
    : `$${Math.abs(delta).toLocaleString()} less`;
  const deltaColor = delta > 0 ? 'var(--color-grade-f)' : delta < 0 ? 'var(--color-grade-a)' : 'var(--color-text-secondary)';

  return (
    <a
      href={comp.url}
      target="_blank"
      rel="noopener noreferrer"
      style={styles.compCard}
    >
      <p style={styles.compTitle}>{comp.title}</p>
      <p style={styles.compPrice}>${comp.price?.toLocaleString()}</p>
      {comp.mileage && (
        <p style={styles.compMileage}>{comp.mileage.toLocaleString()} mi</p>
      )}
      <span style={{ ...styles.compDelta, color: deltaColor }}>{deltaStr}</span>
    </a>
  );
}


// ── Styles ─────────────────────────────────────────────────────────────────

const styles = {
  card: {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-xl)',
    overflow: 'hidden',
    boxShadow: 'var(--shadow-md)',
  },
  header: {
    display: 'flex',
    gap: 24,
    padding: '32px 32px 24px',
    flexWrap: 'wrap',
    alignItems: 'flex-start',
  },
  gradeBadge: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    width: 96,
    height: 96,
    borderRadius: 'var(--radius-lg)',
    flexShrink: 0,
    gap: 2,
  },
  gradeLetterLarge: {
    fontSize: 52,
    fontWeight: 800,
    lineHeight: 1,
  },
  gradeLabel: {
    fontSize: 10,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    opacity: 0.8,
  },
  verdictBlock: {
    flex: 1,
    minWidth: 200,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  priceVerdict: {
    fontSize: 22,
    fontWeight: 700,
    color: 'var(--color-text-primary)',
    lineHeight: 1.25,
  },
  deltaPill: {
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: 'var(--radius-sm)',
    fontSize: 13,
    fontWeight: 600,
    alignSelf: 'flex-start',
  },
  summary: {
    fontSize: 15,
    lineHeight: 1.65,
    color: 'var(--color-text-secondary)',
  },
  divider: {
    height: 1,
    background: 'var(--color-border)',
    marginInline: 32,
  },
  section: {
    padding: '24px 32px',
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: 600,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    color: 'var(--color-text-secondary)',
    marginBottom: 16,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },

  // Flags
  flagToggle: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
    marginBottom: 16,
  },
  flagToggleLabel: {
    fontSize: 13,
    fontWeight: 600,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  flagList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  flagItem: {
    display: 'flex',
    gap: 12,
    borderLeft: '3px solid',
    paddingLeft: 14,
  },
  flagDot: {
    width: 28,
    height: 28,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 12,
    flexShrink: 0,
    marginTop: 1,
  },
  flagTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    marginBottom: 3,
  },
  flagDesc: {
    fontSize: 13,
    lineHeight: 1.6,
    color: 'var(--color-text-secondary)',
  },

  // Comps
  compsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: 12,
  },
  compCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    padding: '14px 16px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--color-border)',
    background: 'var(--color-surface-raised)',
    textDecoration: 'none',
    transition: 'border-color 150ms ease, box-shadow 150ms ease',
  },
  compTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    lineHeight: 1.35,
    marginBottom: 2,
  },
  compPrice: {
    fontSize: 16,
    fontWeight: 700,
    color: 'var(--color-text-primary)',
  },
  compMileage: {
    fontSize: 12,
    color: 'var(--color-text-tertiary)',
  },
  compDelta: {
    fontSize: 12,
    fontWeight: 600,
    marginTop: 4,
  },

  // Negotiation
  negotiationList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    listStyle: 'none',
  },
  negotiationItem: {
    display: 'flex',
    gap: 14,
    alignItems: 'flex-start',
  },
  negotiationNum: {
    width: 24,
    height: 24,
    borderRadius: '50%',
    background: 'var(--color-yellow)',
    color: 'var(--color-text-primary)',
    fontSize: 12,
    fontWeight: 700,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 1,
  },
  negotiationText: {
    fontSize: 14,
    lineHeight: 1.65,
    color: 'var(--color-text-primary)',
  },

  // Share
  shareRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '20px 32px',
    gap: 16,
    flexWrap: 'wrap',
    background: 'var(--color-surface-raised)',
  },
  shareHint: {
    fontSize: 14,
    color: 'var(--color-text-secondary)',
  },
  shareBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 18px',
    borderRadius: 'var(--radius-md)',
    border: '1.5px solid var(--color-border)',
    background: 'var(--color-surface)',
    color: 'var(--color-text-primary)',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'border-color 150ms ease',
    whiteSpace: 'nowrap',
  },
};


// ── Small icons ────────────────────────────────────────────────────────────

function ChevronIcon({ rotated }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
         style={{ transform: rotated ? 'rotate(180deg)' : 'none', transition: 'transform 200ms ease', color: 'var(--color-text-tertiary)' }}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function ShareIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function NegotiateIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

export default DealCard;
