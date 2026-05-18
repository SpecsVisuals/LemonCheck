/**
 * Analysis.jsx
 *
 * Analysis Results Page
 * ----------------------
 * Reads the listing URL or VIN from query params, runs the analysis,
 * and renders the result inside a DealCard.
 *
 * URL shape:
 *   /analysis?url=https://...   — from URL input
 *   /analysis?vin=2HGFC...      — from VIN input
 *   /analysis?demo=true         — run demo (no auth required)
 *
 * State machine:
 *   loading → success (DealCard) | error (error state with retry)
 *
 * Auth flow:
 *   - ?demo=true bypasses auth entirely
 *   - Otherwise uses session.access_token from useAuth()
 *   - 401 → redirects to /?auth=required
 *   - 402 → shows upgrade modal via useUsageGate()
 *
 * Plain English:
 *   This page is the payoff — the user gets their answer here.
 *   If something goes wrong, we give a clear error and a retry button.
 *
 * Technical:
 *   Kicks off the API call in useEffect on mount.
 *   Uses React Router's useSearchParams to read query params.
 *   Scrolls to top on result so the grade is immediately visible.
 */

import { useState, useEffect, useRef, Component } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { ThemeToggle } from '@/components/ThemeToggle';
import { DealCard } from '@/components/DealCard';
import { LoadingStates } from '@/components/LoadingStates';
import { useAuth } from '@/hooks/useAuth';
import { useUsageGate } from '@/hooks/useUsageGate';
import { analyzeListingUrl, analyzeVin, ApiError } from '@/lib/api';
import { DEMO_REPORT } from '@/lib/demoData';

export default function Analysis() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { session, isLoading: authLoading } = useAuth();
  const { onLimitHit } = useUsageGate();

  const [state, setState] = useState('loading'); // 'loading' | 'success' | 'error'
  const [report, setReport] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const hasFetched = useRef(false);
  // Track actual unmount (not re-renders). Using a ref avoids the stale-closure
  // bug where Supabase's second auth-state-change fires the effect cleanup and
  // sets `cancelled = true` on a still-live fetch, silently swallowing the result.
  const unmounted = useRef(false);
  useEffect(() => {
    return () => { unmounted.current = true; };
  }, []);

  const isDemo = searchParams.get('demo') === 'true';
  const listingUrl = searchParams.get('url');
  const vin = searchParams.get('vin');

  useEffect(() => {
    // Wait for auth to resolve before making the call (except demo)
    if (!isDemo && authLoading) return;
    // Guard: only run the analysis once per page load
    if (hasFetched.current) return;
    hasFetched.current = true;

    async function run() {
      try {
        let result;

        if (isDemo) {
          // Serve demo data from static import — no network call needed.
          // Avoids Railway cold-start latency on the recruiter demo path.
          result = DEMO_REPORT;
        } else if (!session) {
          // Not authed — redirect home
          navigate('/?auth=required');
          return;
        } else {
          const token = session.access_token;
          if (listingUrl) result = await analyzeListingUrl(listingUrl, token);
          else if (vin)   result = await analyzeVin(vin, token);
          else { navigate('/'); return; }
        }

        if (unmounted.current) return;
        setReport(result);
        setState('success');
        window.scrollTo(0, 0);

      } catch (err) {
        if (unmounted.current) return;

        if (err instanceof ApiError) {
          if (err.status === 402) {
            onLimitHit(err.detail);
            setUpgradeOpen(true);
            setState('error');
            setErrorMsg("You've hit your monthly limit. Upgrade for unlimited analyses.");
            return;
          }
          if (err.status === 401) {
            navigate('/?auth=required');
            return;
          }
          if (err.status === 422) {
            setState('error');
            setErrorMsg("We couldn't parse this listing. Try a different URL or VIN.");
            return;
          }
        }

        setState('error');
        setErrorMsg('Something went wrong on our end. Give it a moment and try again.');
      }
    }

    run();
  }, [authLoading, session, isDemo, listingUrl, vin, navigate, onLimitHit]);

  return (
    <div style={styles.page}>
      {/* Nav */}
      <nav style={styles.nav}>
        <div className="container" style={styles.navInner}>
          <Link to="/" style={{ textDecoration: 'none' }}>
            <Logo size="md" />
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {state === 'success' && (
              <Link to="/" style={styles.newAnalysisLink}>
                ← Analyze another car
              </Link>
            )}
            <ThemeToggle />
          </div>
        </div>
      </nav>

      <main className="container" style={styles.main}>
        {/* Loading */}
        {state === 'loading' && <LoadingStates />}

        {/* Success */}
        {state === 'success' && report && (
          <div style={styles.resultWrapper}>
            {isDemo && (
              <div style={styles.demoBanner}>
                <span>👀 This is a sample analysis.</span>
                <Link to="/" style={styles.demoBannerLink}>Try it with a real listing →</Link>
              </div>
            )}
            <DealCardBoundary report={report} />
            <div style={styles.ctaRow}>
              <p style={styles.ctaText}>Want to check another car?</p>
              <Link to="/" style={styles.ctaBtn}>Run another analysis</Link>
            </div>
          </div>
        )}

        {/* Error */}
        {state === 'error' && (
          <div style={styles.errorWrapper}>
            <div style={styles.errorIcon}>⚠️</div>
            <h2 style={styles.errorTitle}>Couldn't complete the analysis</h2>
            <p style={styles.errorMsg}>{errorMsg}</p>
            <div style={styles.errorActions}>
              <button onClick={() => window.location.reload()} style={styles.retryBtn}>
                Try again
              </button>
              <Link to="/" style={styles.homeLink}>Back to home</Link>
            </div>
          </div>
        )}
      </main>

      {/* Upgrade modal */}
      {upgradeOpen && <UpgradeModal onClose={() => setUpgradeOpen(false)} />}
    </div>
  );
}


// ── DealCard error boundary ────────────────────────────────────────────────
// Catches any runtime crash inside DealCard (e.g. unexpected null field from
// the AI response) and shows a fallback instead of a blank screen.

class DealCardBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { crashed: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { crashed: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[DealCardBoundary] DealCard crashed:', error, info);
  }

  render() {
    if (this.state.crashed) {
      return (
        <div style={{ maxWidth: 400, margin: '0 auto', textAlign: 'center', padding: '48px 24px' }}>
          <p style={{ fontSize: 40 }}>⚠️</p>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 12 }}>Couldn't display the result</h2>
          <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>
            The analysis completed but the result had an unexpected format. Try again — this is usually transient.
          </p>
          <button onClick={() => window.location.reload()}
            style={{ padding: '10px 24px', borderRadius: 'var(--radius-md)', background: 'var(--color-text-primary)', color: 'var(--color-bg)', fontSize: 14, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
            Try again
          </button>
        </div>
      );
    }
    return <DealCard report={this.props.report} />;
  }
}


// ── Upgrade modal ──────────────────────────────────────────────────────────

function UpgradeModal({ onClose }) {
  return (
    <div style={styles.modalBackdrop} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <button onClick={onClose} style={styles.modalClose} aria-label="Close">✕</button>
        <div style={{ fontSize: 40, marginBottom: 12 }}>🍋</div>
        <h2 style={styles.modalTitle}>You've used your 5 free analyses</h2>
        <p style={styles.modalBody}>
          Upgrade for unlimited analyses, priority processing, and PDF reports.
          Coming soon — drop your email to get notified.
        </p>
        <a href="mailto:hello@lemoncheck.app?subject=Pro interest" style={styles.upgradeBtn}>
          Get notified when Pro launches
        </a>
        <button onClick={onClose} style={styles.maybeLater}>Maybe later</button>
      </div>
    </div>
  );
}


// ── Styles ─────────────────────────────────────────────────────────────────

const styles = {
  page: { minHeight: '100vh', background: 'var(--color-bg)' },
  nav: { borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)', position: 'sticky', top: 0, zIndex: 'var(--z-raised)' },
  navInner: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60 },
  newAnalysisLink: { fontSize: 14, color: 'var(--color-text-secondary)', textDecoration: 'none', fontWeight: 500 },

  main: { padding: '40px 0 80px' },

  // Result
  resultWrapper: { maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 },
  demoBanner: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12,
    padding: '12px 20px', borderRadius: 'var(--radius-md)',
    background: 'var(--color-cream)', border: '1px solid var(--color-sand)',
    fontSize: 14, color: 'var(--color-text-secondary)',
  },
  demoBannerLink: { color: 'var(--color-green)', fontWeight: 600, textDecoration: 'none' },
  ctaRow: {
    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, flexWrap: 'wrap',
    padding: '20px 0', borderTop: '1px solid var(--color-border)',
  },
  ctaText: { fontSize: 14, color: 'var(--color-text-secondary)' },
  ctaBtn: {
    padding: '10px 24px', borderRadius: 'var(--radius-md)',
    background: 'var(--color-yellow)', color: 'var(--color-text-primary)',
    fontSize: 14, fontWeight: 600, textDecoration: 'none',
  },

  // Error
  errorWrapper: { maxWidth: 400, margin: '80px auto', textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'center' },
  errorIcon: { fontSize: 48 },
  errorTitle: { fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)' },
  errorMsg: { fontSize: 15, lineHeight: 1.65, color: 'var(--color-text-secondary)' },
  errorActions: { display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center', marginTop: 8 },
  retryBtn: {
    padding: '10px 24px', borderRadius: 'var(--radius-md)',
    background: 'var(--color-text-primary)', color: 'var(--color-bg)',
    fontSize: 14, fontWeight: 600, border: 'none', cursor: 'pointer',
  },
  homeLink: { padding: '10px 24px', borderRadius: 'var(--radius-md)', border: '1.5px solid var(--color-border)', fontSize: 14, color: 'var(--color-text-secondary)', textDecoration: 'none', fontWeight: 500 },

  // Upgrade modal
  modalBackdrop: { position: 'fixed', inset: 0, background: 'rgba(28,26,20,0.5)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 'var(--z-modal)', padding: 24 },
  modal: { background: 'var(--color-surface)', borderRadius: 'var(--radius-xl)', padding: '40px 36px', maxWidth: 400, width: '100%', boxShadow: 'var(--shadow-lg)', position: 'relative', textAlign: 'center' },
  modalClose: { position: 'absolute', top: 16, right: 16, fontSize: 16, color: 'var(--color-text-tertiary)', cursor: 'pointer', padding: 4, background: 'none', border: 'none' },
  modalTitle: { fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 10 },
  modalBody: { fontSize: 14, lineHeight: 1.65, color: 'var(--color-text-secondary)', marginBottom: 24 },
  upgradeBtn: { display: 'block', padding: '12px 24px', borderRadius: 'var(--radius-md)', background: 'var(--color-yellow)', color: 'var(--color-text-primary)', fontSize: 15, fontWeight: 600, textDecoration: 'none', marginBottom: 12 },
  maybeLater: { fontSize: 13, color: 'var(--color-text-tertiary)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' },
};
