/**
 * ThemeToggle.jsx
 *
 * Dark / Light Mode Toggle with Wash Animation
 * ---------------------------------------------
 * Toggles the site between light and dark mode by setting [data-theme="dark"]
 * on the <html> element. Persists preference to localStorage.
 *
 * Animation:
 *   When toggled, a full-viewport overlay div (.lc-theme-wash) is injected
 *   into the body, plays a 600ms fade-in/fade-out "wash" animation in citrus
 *   yellow, then removes itself. The theme actually flips at the animation's
 *   midpoint (300ms) so the color change is hidden beneath the wash.
 *
 * Accessibility:
 *   - Button has aria-label that updates with current mode
 *   - Respects prefers-color-scheme on first load
 *   - Keyboard accessible (it's a real <button>)
 *
 * Usage:
 *   <ThemeToggle />   — renders a toggle button, self-contained
 *
 * Plain English:
 *   Click the button, the page does a little lemon-yellow shimmer,
 *   and when it clears you're in dark (or light) mode.
 *
 * Technical:
 *   Uses the data-theme attribute pattern rather than a CSS class so the
 *   toggle logic stays in JS and CSS variables do the theming heavy lifting.
 *   The wash overlay is DOM-injected rather than always-rendered to keep
 *   the component tree clean.
 */

import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'lc-theme';
const WASH_DURATION = 600; // ms — must match CSS animation duration

function getInitialTheme() {
  // 1. Respect stored preference
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'dark' || stored === 'light') return stored;

  // 2. Fall back to system preference
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';

  // 3. Default: light
  return 'light';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_KEY, theme);
}

export function ThemeToggle({ className = '' }) {
  const [theme, setTheme] = useState('light'); // initialised in useEffect to avoid SSR mismatch
  const [isAnimating, setIsAnimating] = useState(false);

  // Set initial theme on mount
  useEffect(() => {
    const initial = getInitialTheme();
    setTheme(initial);
    applyTheme(initial);
  }, []);

  const toggle = useCallback(() => {
    if (isAnimating) return;

    const next = theme === 'light' ? 'dark' : 'light';
    setIsAnimating(true);

    // Inject wash overlay
    const wash = document.createElement('div');
    wash.className = 'lc-theme-wash';
    document.body.appendChild(wash);

    // Flip theme at midpoint of animation
    setTimeout(() => {
      setTheme(next);
      applyTheme(next);
    }, WASH_DURATION / 2);

    // Remove overlay after animation completes
    setTimeout(() => {
      wash.remove();
      setIsAnimating(false);
    }, WASH_DURATION + 50);
  }, [theme, isAnimating]);

  const isDark = theme === 'dark';

  return (
    <button
      onClick={toggle}
      disabled={isAnimating}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={`lc-theme-toggle ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 40,
        height: 40,
        borderRadius: '50%',
        border: '1.5px solid var(--color-border)',
        background: 'var(--color-surface)',
        color: 'var(--color-text-secondary)',
        fontSize: 18,
        transition: 'border-color 200ms ease, color 200ms ease, background 200ms ease',
        cursor: isAnimating ? 'default' : 'pointer',
        opacity: isAnimating ? 0.7 : 1,
      }}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}


/* ── Icon components ──────────────────────────────────────────────────────── */

function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

export default ThemeToggle;
