/**
 * Home.jsx
 *
 * LemonCheck Homepage
 * --------------------
 * The landing page and primary entry point for users.
 *
 * Layout (top to bottom):
 *   1. Nav        — Logo (left) + ThemeToggle (right)
 *   2. Hero       — Headline, subhead, SearchInput
 *   3. Value props — 3 icons: Real market data · AI analysis · Plain English
 *   4. Demo preview — blurred/teased DealCard result to show what you get
 *   5. Footer     — minimal, just a tagline
 *
 * Behavior:
 *   - On submit, checks gate (auth modal if not signed in, upgrade if over limit)
 *   - If clear, navigates to /analysis?url=... with the listing URL
 *   - Demo preview fetches GET /demo on mount and renders a blurred card
 *
 * Design notes:
 *   - Earth-tone palette, calm on landing — this page shouldn't feel busy
 *   - Tone: dry confidence. "Is it a good deal? Find out in 30 seconds."
 *   - Mobile-first — hero stacks vertically at 375px
 *
 * Plain English (for recruiters):
 *   This is the front door. User pastes a link to a used car listing,
 *   hits Analyze, and 30 seconds later knows if it's a good deal.
 *
 * Technical:
 *   React Router v6 for navigation. Lazy-loads demo preview to avoid
 *   blocking the hero. Auth modal + upgrade modal are conditionally rendered
 *   based on useUsageGate() state.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { ThemeToggle } from '@/components/ThemeToggle';
import { SearchInput } from '@/components/SearchInput';
import { useUsageGate } from '@/hooks/useUsageGate';
import { getDemoResult } from '@/lib/api';

export default function Home() {
  const navigate = useNavigate();
  const { canAnalyze, showAuthModal, isLoading } = useUsageGate();

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [demoPreview, setDemoPreview] = useState(null);

  // Load demo preview in background (non-blocking)
  useEffect(() => {
    getDemoResult()
      .then(data => setDemoPreview(data))
      .catch(() => {/* demo preview failing silently is fine */});
  }, []);

  // Show auth modal when gate says we need it
  useEffect(() => {
    if (showAuthModal && isAnalyzing) {
      setAuthModalOpen(true);
    }
  }, [showAuthModal, isAnalyzing]);

  const handleSubmit = async (value, mode) => {
    setIsAnalyzing(true);

    // If not authed, open modal instead of navigating
    if (!isLoading && !canAnalyze) {
      setAuthModalOpen(true);
      setIsAnalyzing(false);
      return;
    }

    // Navigate to analysis page with input
    const params = new URLSearchParams();
    if (mode === 'url') params.set('url', value);
    else params.set('vin', value);
    navigate(`/analysis?${params.toString()}`);
  };

  return (
    <div style={styles.page}>
      {/* ── Nav ──────────────────────────────────────────────────────────── */}
      <nav style={styles.nav}>
        <div className="container" style={styles.navInner}>
          <Logo size="md" />
          <ThemeToggle />
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section style={styles.hero}>
        <div className="container" style={styles.heroInner}>
          <div style={styles.heroContent}>
            <p style={styles.eyebrow}>AI-powered used car analysis</p>

            <h1 style={styles.headline}>
              Is it a good deal?<br />
              <span style={styles.headlineAccent}>Find out in 30 seconds.</span>
            </h1>

            <p style={styles.subhead}>
              Paste any CarGurus or AutoTrader listing. We pull real market comps,
              decode the VIN, and give you a plain-English verdict — plus the
              exact lines to use when you negotiate.
            </p>

            <div style={styles.searchWrapper}>
              <SearchInput
                onSubmit={handleSubmit}
                isLoading={isAnalyzing}
              />
            </div>

            <p style={styles.demoHint}>
              Just browsing?{' '}
              <button
                onClick={() => navigate('/analysis?demo=true')}
                style={styles.demoLink}
              >
                See a sample analysis →
              </button>
            </p>
          </div>
        </div>
      </section>

      {/* ── Value Props ───────────────────────────────────────────────────── */}
      <section style={styles.valueProps}>
        <div className="container">
          <div style={styles.valuePropGrid}>
            <ValueProp
              icon={<DataIcon />}
              title="Real market data"
              body="We search actual listings in your area to find what this car is really worth — not a guess, not a sticker price."
            />
            <ValueProp
              icon={<BrainIcon />}
              title="AI analysis"
              body="Claude reads the listing like a 20-year car buyer: spotting red flags, known model issues, and overpriced trim levels."
            />
            <ValueProp
              icon={<SpeechIcon />}
              title="Plain English verdict"
              body="No jargon. You get a letter grade, a price delta, and the exact things to say when you sit across from the dealer."
            />
          </div>
        </div>
      </section>

      {/* ── Demo Preview (blurred teaser) ─────────────────────────────────── */}
      {demoPreview && (
        <section style={styles.previewSection}>
          <div className="container">
            <p style={styles.previewLabel}>What you'll get</p>
            <div style={styles.previewWrapper}>
              <DemoPreviewCard report={demoPreview} />
              {/* Blur + CTA overlay */}
              <div style={styles.previewOverlay}>
                <p style={styles.previewOverlayText}>
                  See the full analysis
                </p>
                <button
                  onClick={() => navigate('/analysis?demo=true')}
                  style={styles.previewBtn}
                >
                  Run a free analysis
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer style={styles.footer}>
        <div className="container" style={styles.footerInner}>
          <Logo size="sm" />
          <p style={styles.footerText}>
            Built to help real people not get ripped off on used cars.
          </p>
        </div>
      </footer>

      {/* ── Auth Modal ───────────────────────────────────────────────────── */}
      {authModalOpen && (
        <AuthModal onClose={() => { setAuthModalOpen(false); setIsAnalyzing(false); }} />
      )}
    </div>
  );
}


/* ── ValueProp card ──────────────────────────────────────────────────────── */

function ValueProp({ icon, title, body }) {
  return (
    <div style={styles.valuePropCard}>
      <div style={styles.valuePropIcon}>{icon}</div>
      <h3 style={styles.valuePropTitle}>{title}</h3>
      <p style={styles.valuePropBody}>{body}</p>
    </div>
  );
}


/* ── Blurred demo preview card ───────────────────────────────────────────── */

function DemoPreviewCard({ report }) {
  const gradeColor = {
    A: 'var(--color-grade-a)', B: 'var(--color-grade-b)',
    C: 'var(--color-grade-c)', D: 'var(--color-grade-d)', F: 'var(--color-grade-f)',
  }[report.grade] || 'var(--color-text-secondary)';

  const gradeBg = {
    A: 'var(--color-grade-a-bg)', B: 'var(--color-grade-b-bg)',
    C: 'var(--color-grade-c-bg)', D: 'var(--color-grade-d-bg)', F: 'var(--color-grade-f-bg)',
  }[report.grade] || 'var(--color-surface)';

  return (
    <div style={{ ...styles.previewCard, filter: 'blur(5px)', userSelect: 'none', pointerEvents: 'none' }}>
      {/* Grade badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <div style={{
          width: 72, height: 72, borderRadius: 'var(--radius-md)',
          background: gradeBg, color: gradeColor,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 40, fontWeight: 800, lineHeight: 1,
        }}>
          {report.grade}
        </div>
        <div>
          <p style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 4 }}>
            {report.price_verdict}
          </p>
          <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>{report.summary?.slice(0, 80)}...</p>
        </div>
      </div>

      {/* Flags preview */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {report.red_flags?.slice(0, 2).map((f, i) => (
          <div key={i} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', background: 'var(--color-grade-f-bg)', color: 'var(--color-grade-f)', fontSize: 13 }}>
            ⚑ {f.title}
          </div>
        ))}
        {report.green_flags?.slice(0, 2).map((f, i) => (
          <div key={i} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', background: 'var(--color-grade-a-bg)', color: 'var(--color-grade-a)', fontSize: 13 }}>
            ✓ {f.title}
          </div>
        ))}
      </div>
    </div>
  );
}


/* ── Auth Modal ──────────────────────────────────────────────────────────── */

import { useAuth } from '@/hooks/useAuth';

function AuthModal({ onClose }) {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.includes('@')) { setError('Enter a valid email'); return; }
    setLoading(true);
    const { error: signInError } = await signIn(email);
    setLoading(false);
    if (signInError) { setError(signInError.message); return; }
    setSent(true);
  };

  return (
    <div style={styles.modalBackdrop} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Sign in to analyze">
        <button onClick={onClose} style={styles.modalClose} aria-label="Close">✕</button>

        {sent ? (
          <div style={{ textAlign: 'center', padding: '8px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📬</div>
            <h2 style={styles.modalTitle}>Check your inbox</h2>
            <p style={styles.modalBody}>
              We sent a magic link to <strong>{email}</strong>.<br />
              Click it and you'll be right back here.
            </p>
          </div>
        ) : (
          <>
            <h2 style={styles.modalTitle}>One quick step</h2>
            <p style={styles.modalBody}>
              Enter your email and we'll send you a magic link — no password needed.
              Your first 5 analyses are free.
            </p>
            <form onSubmit={handleSubmit} style={{ marginTop: 20 }}>
              <input
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); setError(null); }}
                placeholder="you@example.com"
                autoFocus
                style={styles.modalInput}
              />
              {error && <p style={{ color: 'var(--color-grade-f)', fontSize: 13, marginTop: 6 }}>{error}</p>}
              <button type="submit" disabled={loading} style={styles.modalBtn}>
                {loading ? 'Sending...' : 'Send magic link'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}


/* ── Icons ───────────────────────────────────────────────────────────────── */

function DataIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.04-4.79A2.5 2.5 0 0 1 4.5 9.5a2.5 2.5 0 0 1 2.5-4.5 2.5 2.5 0 0 1 2.5-2.5Z" />
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.04-4.79A2.5 2.5 0 0 0 19.5 9.5a2.5 2.5 0 0 0-2.5-4.5 2.5 2.5 0 0 0-2.5-2.5Z" />
    </svg>
  );
}

function SpeechIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}


/* ── Styles ──────────────────────────────────────────────────────────────── */

const styles = {
  page: { minHeight: '100vh', background: 'var(--color-bg)', display: 'flex', flexDirection: 'column' },

  // Nav
  nav: { borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)', position: 'sticky', top: 0, zIndex: 'var(--z-raised)', backdropFilter: 'blur(8px)' },
  navInner: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60 },

  // Hero
  hero: { padding: '72px 0 56px', flex: 1 },
  heroInner: { display: 'flex', justifyContent: 'center' },
  heroContent: { maxWidth: 640, width: '100%' },
  eyebrow: { fontSize: 13, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-green)', marginBottom: 16 },
  headline: { fontSize: 'clamp(32px, 5vw, 52px)', fontWeight: 800, lineHeight: 1.15, color: 'var(--color-text-primary)', marginBottom: 20 },
  headlineAccent: { color: 'var(--color-green)' },
  subhead: { fontSize: 17, lineHeight: 1.7, color: 'var(--color-text-secondary)', marginBottom: 36, maxWidth: 560 },
  searchWrapper: { marginBottom: 16 },
  demoHint: { fontSize: 13, color: 'var(--color-text-tertiary)' },
  demoLink: { background: 'none', border: 'none', padding: 0, color: 'var(--color-green)', fontSize: 13, fontWeight: 500, cursor: 'pointer', textDecoration: 'underline' },

  // Value props
  valueProps: { padding: '56px 0', borderTop: '1px solid var(--color-border)' },
  valuePropGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 32 },
  valuePropCard: { display: 'flex', flexDirection: 'column', gap: 12 },
  valuePropIcon: { width: 48, height: 48, borderRadius: 'var(--radius-md)', background: 'var(--color-cream)', color: 'var(--color-green)', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  valuePropTitle: { fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)' },
  valuePropBody: { fontSize: 14, lineHeight: 1.65, color: 'var(--color-text-secondary)' },

  // Demo preview
  previewSection: { padding: '48px 0 64px', borderTop: '1px solid var(--color-border)' },
  previewLabel: { fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-text-tertiary)', marginBottom: 20 },
  previewWrapper: { position: 'relative', maxWidth: 600 },
  previewCard: { background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', padding: 28 },
  previewOverlay: {
    position: 'absolute', inset: 0, borderRadius: 'var(--radius-lg)',
    background: 'linear-gradient(to bottom, transparent 0%, var(--color-bg) 55%)',
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', padding: 32, gap: 16,
  },
  previewOverlayText: { fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', textAlign: 'center' },
  previewBtn: {
    padding: '12px 28px', borderRadius: 'var(--radius-md)',
    background: 'var(--color-yellow)', color: 'var(--color-text-primary)',
    fontSize: 15, fontWeight: 600, border: 'none', cursor: 'pointer',
  },

  // Footer
  footer: { borderTop: '1px solid var(--color-border)', padding: '32px 0', marginTop: 'auto' },
  footerInner: { display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' },
  footerText: { fontSize: 13, color: 'var(--color-text-tertiary)' },

  // Auth modal
  modalBackdrop: {
    position: 'fixed', inset: 0, background: 'rgba(28, 26, 20, 0.5)',
    backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 'var(--z-modal)', padding: 24,
  },
  modal: {
    background: 'var(--color-surface)', borderRadius: 'var(--radius-xl)',
    padding: '40px 36px', maxWidth: 400, width: '100%',
    boxShadow: 'var(--shadow-lg)', position: 'relative',
  },
  modalClose: { position: 'absolute', top: 16, right: 16, fontSize: 16, color: 'var(--color-text-tertiary)', cursor: 'pointer', padding: 4 },
  modalTitle: { fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 10 },
  modalBody: { fontSize: 14, lineHeight: 1.65, color: 'var(--color-text-secondary)' },
  modalInput: {
    width: '100%', height: 44, padding: '0 14px', borderRadius: 'var(--radius-md)',
    border: '1.5px solid var(--color-border)', background: 'var(--color-bg)',
    color: 'var(--color-text-primary)', fontSize: 15, outline: 'none',
  },
  modalBtn: {
    marginTop: 12, width: '100%', height: 44, borderRadius: 'var(--radius-md)',
    background: 'var(--color-text-primary)', color: 'var(--color-bg)',
    fontSize: 15, fontWeight: 600, border: 'none', cursor: 'pointer',
  },
};
