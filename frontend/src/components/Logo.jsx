/**
 * Logo.jsx
 *
 * LemonCheck Wordmark + Logo Mark
 * ---------------------------------
 * Renders the LemonCheck brand identity as an inline SVG component.
 *
 * Structure:
 *   - Wordmark: "LEM[lemon-O]N" in bold display weight + "CHECK" lighter below
 *   - Logo mark: SVG lemon silhouette replacing the "O" in "LEMON"
 *     The lemon is subtle — reads as an O at a glance, reveals itself on closer look.
 *
 * Props:
 *   size     — "sm" | "md" | "lg" | "xl"  (default: "md")
 *   compact  — boolean, shows mark only (no text) at small sizes
 *   className — additional CSS classes
 *
 * Plain English:
 *   The logo is the brand's handshake. LEMON in bold, CHECK underneath lighter.
 *   The O in LEMON is actually a tiny lemon shape — a little hidden detail.
 *
 * Technical:
 *   SVG viewBox approach lets the logo scale perfectly at any size.
 *   The lemon-O is drawn as two overlapping ellipses with a slight rotation,
 *   classic lemon silhouette that also reads as the letter O.
 */

import React from 'react';

const SIZES = {
  sm: { wordmarkH: 20, checkH: 11, gap: 2 },
  md: { wordmarkH: 28, checkH: 14, gap: 3 },
  lg: { wordmarkH: 40, checkH: 20, gap: 4 },
  xl: { wordmarkH: 56, checkH: 28, gap: 6 },
};

export function Logo({ size = 'md', compact = false, className = '' }) {
  const dims = SIZES[size] || SIZES.md;

  if (compact) {
    return <LemonMark size={dims.wordmarkH} className={className} />;
  }

  return (
    <div
      className={`lc-logo ${className}`}
      style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: dims.gap }}
      aria-label="LemonCheck"
    >
      <WordmarkRow height={dims.wordmarkH} />
      <CheckRow height={dims.checkH} />
    </div>
  );
}


/* ── Wordmark Row: "LEM[O]N" ──────────────────────────────────────────────── */

function WordmarkRow({ height }) {
  // Each character rendered as text spans with the lemon-O as SVG in the middle
  const fontSize = height;
  const letterSpacing = fontSize * 0.04;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, lineHeight: 1 }}>
      <span style={{
        fontFamily: "'BadenDisplay', Georgia, serif",
        fontWeight: 700,
        fontSize: fontSize,
        color: 'var(--color-text-primary)',
        letterSpacing: letterSpacing,
        lineHeight: 1,
      }}>
        LEM
      </span>

      {/* Lemon-O: sits in-line with the text, sized to match cap height */}
      <LemonMark size={fontSize * 0.88} style={{ marginTop: fontSize * 0.02 }} />

      <span style={{
        fontFamily: "'BadenDisplay', Georgia, serif",
        fontWeight: 700,
        fontSize: fontSize,
        color: 'var(--color-text-primary)',
        letterSpacing: letterSpacing,
        lineHeight: 1,
      }}>
        N
      </span>
    </div>
  );
}


/* ── CHECK Row ────────────────────────────────────────────────────────────── */

function CheckRow({ height }) {
  return (
    <span style={{
      fontFamily: "'Inter', system-ui, sans-serif",
      fontWeight: 300,
      fontSize: height,
      color: 'var(--color-text-secondary)',
      letterSpacing: height * 0.25,
      textTransform: 'uppercase',
      lineHeight: 1,
    }}>
      CHECK
    </span>
  );
}


/* ── Lemon Mark SVG ───────────────────────────────────────────────────────── */
/*
 * The lemon-O: a yellow ellipse (lemon body) with a slight taper at each end
 * created by two overlapping paths. Reads as "O" at a glance.
 * Color: --color-yellow (#F0C000) with a subtle darker stroke.
 */

export function LemonMark({ size = 28, style = {}, className = '' }) {
  const w = size;
  const h = size * 0.85; // lemons are slightly taller than wide when used as O

  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 40 34"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0, transform: 'rotate(25deg)', ...style }}
      className={className}
    >
      {/* Lemon body — rotated ellipse */}
      <ellipse
        cx="20"
        cy="17"
        rx="17"
        ry="13"
        fill="var(--color-yellow)"
        transform="rotate(-8 20 17)"
      />

      {/* Inner oval cutout — makes it look like a thick O, not a filled circle */}
      <ellipse
        cx="20"
        cy="17"
        rx="10"
        ry="7"
        fill="var(--color-bg)"
        transform="rotate(-8 20 17)"
      />

      {/* Left tip — subtle point suggesting lemon tip */}
      <ellipse
        cx="3.5"
        cy="17"
        rx="3"
        ry="2"
        fill="var(--color-yellow)"
        transform="rotate(-15 3.5 17)"
      />

      {/* Right tip */}
      <ellipse
        cx="36.5"
        cy="17"
        rx="3"
        ry="2"
        fill="var(--color-yellow)"
        transform="rotate(15 36.5 17)"
      />
    </svg>
  );
}

export default Logo;
