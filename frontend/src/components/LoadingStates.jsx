/**
 * LoadingStates.jsx
 *
 * Animated Loading State — Analysis in Progress
 * -----------------------------------------------
 * Shows while the backend is running the 20-30 second analysis.
 * Designed to make the wait feel purposeful, not abandoned.
 *
 * Animation sequence:
 *   "Fetching listing data..."       (0–3s)
 *   "Searching comparable listings..." (3–8s)
 *   "Decoding vehicle history..."    (8–14s)
 *   "Running deal analysis..."       (14–22s)
 *   "Almost there..."                (22s+)
 *
 * Also shows a progress bar that fills over ~25 seconds.
 * The progress bar doesn't track real backend progress — it's a
 * comfort animation that slows near 90% to avoid finishing before the response.
 *
 * Props:
 *   className — additional CSS classes
 *
 * Plain English:
 *   We're talking to three different data sources plus running an AI analysis.
 *   This screen tells the user we're working hard, not frozen.
 */

import { useState, useEffect, useRef } from 'react';

const STEPS = [
  { message: 'Fetching listing data...', duration: 3500 },
  { message: 'Searching comparable listings nearby...', duration: 5000 },
  { message: 'Decoding vehicle history...', duration: 6000 },
  { message: 'Running deal analysis...', duration: 8000 },
  { message: 'Almost there...', duration: Infinity },
];

// Progress bar fills to ~90% over 25s, slows near the end
function easeProgress(elapsed, total = 25000) {
  const t = Math.min(elapsed / total, 1);
  // Ease out — fast start, slow finish, caps at 0.9
  return Math.min(0.9, 1 - Math.pow(1 - t, 2.5));
}

export function LoadingStates({ className = '' }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const startTime = useRef(Date.now());
  const rafRef = useRef(null);

  // Step cycling
  useEffect(() => {
    let idx = 0;
    const advance = () => {
      if (idx >= STEPS.length - 1) return;
      const delay = STEPS[idx].duration;
      return setTimeout(() => {
        idx += 1;
        setStepIndex(idx);
        timeoutRef.current = advance();
      }, delay);
    };
    const timeoutRef = { current: advance() };
    return () => clearTimeout(timeoutRef.current);
  }, []);

  // Progress bar via rAF
  useEffect(() => {
    const tick = () => {
      const elapsed = Date.now() - startTime.current;
      setProgress(easeProgress(elapsed));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const currentStep = STEPS[Math.min(stepIndex, STEPS.length - 1)];

  return (
    <div className={`lc-loading ${className}`} style={styles.wrapper} role="status" aria-live="polite">
      {/* Lemon animation */}
      <div style={styles.iconWrapper} aria-hidden="true">
        <span style={styles.lemonEmoji}>🍋</span>
      </div>

      {/* Step message */}
      <p key={stepIndex} style={styles.message} aria-label={currentStep.message}>
        {currentStep.message}
      </p>

      {/* Step dots */}
      <div style={styles.dots} aria-hidden="true">
        {STEPS.slice(0, -1).map((_, i) => (
          <span
            key={i}
            style={{
              ...styles.dot,
              background: i <= stepIndex ? 'var(--color-yellow)' : 'var(--color-border)',
              transform: i === stepIndex ? 'scale(1.3)' : 'scale(1)',
            }}
          />
        ))}
      </div>

      {/* Progress bar */}
      <div style={styles.progressTrack} aria-hidden="true">
        <div
          style={{
            ...styles.progressFill,
            width: `${(progress * 100).toFixed(1)}%`,
          }}
        />
      </div>

      <p style={styles.hint}>
        Checking {Math.round(progress * 100)}% — this takes about 30 seconds
      </p>
    </div>
  );
}

const styles = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 20,
    padding: '64px 32px',
    textAlign: 'center',
    maxWidth: 400,
    margin: '0 auto',
  },
  iconWrapper: {
    animation: 'lc-bob 1.8s ease-in-out infinite',
  },
  lemonEmoji: {
    fontSize: 56,
    display: 'block',
  },
  message: {
    fontSize: 18,
    fontWeight: 600,
    color: 'var(--color-text-primary)',
    minHeight: 28,
    animation: 'lc-fadein 400ms ease',
  },
  dots: {
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    transition: 'background 400ms ease, transform 400ms ease',
  },
  progressTrack: {
    width: '100%',
    height: 4,
    borderRadius: 2,
    background: 'var(--color-border)',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
    background: 'var(--color-yellow)',
    transition: 'width 300ms linear',
  },
  hint: {
    fontSize: 13,
    color: 'var(--color-text-tertiary)',
  },
};

// Inject keyframes once (avoids styled-components dep)
if (typeof document !== 'undefined' && !document.getElementById('lc-loading-kf')) {
  const style = document.createElement('style');
  style.id = 'lc-loading-kf';
  style.textContent = `
    @keyframes lc-bob {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-8px); }
    }
    @keyframes lc-fadein {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `;
  document.head.appendChild(style);
}

export default LoadingStates;
