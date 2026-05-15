/**
 * SearchInput.jsx
 *
 * Listing URL / VIN Input with Validation
 * -----------------------------------------
 * The primary input component for LemonCheck. Two input modes:
 *   - URL mode: accepts CarGurus or AutoTrader listing URLs
 *   - VIN mode: accepts a 17-character Vehicle Identification Number
 *
 * Validation rules:
 *   URL: must start with https://www.cargurus.com or https://www.autotrader.com
 *   VIN: must be exactly 17 alphanumeric characters (no I, O, Q per VIN standard)
 *
 * Props:
 *   onSubmit(value, mode) — called with validated input when user submits
 *   isLoading             — boolean, disables form while analysis runs
 *   className             — additional CSS classes
 */

import { useState, useRef, useId } from 'react';

const VALID_URL_PREFIXES = [
  'https://www.cargurus.com',
  'https://www.autotrader.com',
];

const VIN_REGEX = /^[A-HJ-NPR-Z0-9]{17}$/i;

function validateUrl(value) {
  if (!value.trim()) return 'Paste a CarGurus or AutoTrader listing URL';
  const isValid = VALID_URL_PREFIXES.some(prefix => value.startsWith(prefix));
  if (!isValid) return 'URL must be from CarGurus or AutoTrader';
  return null;
}

function validateVin(value) {
  if (!value.trim()) return 'Enter a 17-character VIN';
  if (!VIN_REGEX.test(value.trim())) return 'VIN must be 17 letters and numbers (no I, O, or Q)';
  return null;
}

export function SearchInput({ onSubmit, isLoading = false, className = '' }) {
  const [mode, setMode] = useState('url');
  const [value, setValue] = useState('');
  const [error, setError] = useState(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);

  const inputRef = useRef(null);
  const inputId = useId();
  const errorId = useId();

  const validate = (val) => mode === 'url' ? validateUrl(val) : validateVin(val);

  const handleChange = (e) => {
    const newVal = e.target.value;
    setValue(newVal);
    if (hasSubmitted) setError(validate(newVal));
  };

  const handleModeSwitch = (newMode) => {
    if (newMode === mode) return;
    setMode(newMode);
    setValue('');
    setError(null);
    setHasSubmitted(false);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setHasSubmitted(true);
    const err = validate(value);
    if (err) { setError(err); inputRef.current?.focus(); return; }
    setError(null);
    onSubmit?.(value.trim(), mode);
  };

  const placeholder = mode === 'url'
    ? 'https://www.cargurus.com/Cars/...'
    : 'e.g. 2HGFC2F59KH504164';

  return (
    <div className={`lc-search-input ${className}`} style={styles.wrapper}>
      {/* Mode tabs */}
      <div style={styles.tabs} role="tablist" aria-label="Input mode">
        {['url', 'vin'].map(m => (
          <button
            key={m}
            role="tab"
            aria-selected={mode === m}
            onClick={() => handleModeSwitch(m)}
            style={{ ...styles.tab, ...(mode === m ? styles.tabActive : styles.tabInactive) }}
          >
            {m === 'url' ? 'Listing URL' : 'VIN Number'}
          </button>
        ))}
      </div>

      {/* Input form */}
      <form onSubmit={handleSubmit} noValidate style={styles.form}>
        <div style={styles.inputRow}>
          <div style={styles.inputWrapper}>
            <label htmlFor={inputId} className="sr-only">
              {mode === 'url' ? 'CarGurus or AutoTrader listing URL' : '17-character VIN'}
            </label>
            <input
              ref={inputRef}
              id={inputId}
              type={mode === 'url' ? 'url' : 'text'}
              value={value}
              onChange={handleChange}
              placeholder={placeholder}
              disabled={isLoading}
              aria-describedby={error ? errorId : undefined}
              aria-invalid={!!error}
              autoComplete="off"
              spellCheck={false}
              style={{
                ...styles.input,
                ...(error ? styles.inputError : {}),
                ...(isLoading ? styles.inputDisabled : {}),
              }}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{ ...styles.submitBtn, ...(isLoading ? styles.submitBtnLoading : {}) }}
            aria-label={isLoading ? 'Analyzing...' : 'Analyze this deal'}
          >
            {isLoading ? <LoadingSpinner /> : <><span>Analyze</span><ArrowIcon /></>}
          </button>
        </div>

        {error && (
          <p id={errorId} role="alert" style={styles.errorText}>
            <ErrorIcon /> {error}
          </p>
        )}
        {!error && (
          <p style={styles.helperText}>
            {mode === 'url'
              ? 'Paste the full listing URL from CarGurus or AutoTrader'
              : 'Find the VIN on the dashboard, door jamb, or listing page'}
          </p>
        )}
      </form>
    </div>
  );
}

const styles = {
  wrapper: { width: '100%', maxWidth: 680 },
  tabs: { display: 'flex', gap: 4, marginBottom: 8 },
  tab: {
    padding: '6px 16px', borderRadius: 'var(--radius-sm)', fontSize: 13,
    fontWeight: 500, border: '1.5px solid transparent', transition: 'all 150ms ease', cursor: 'pointer',
  },
  tabActive:   { background: 'var(--color-yellow)', color: 'var(--color-text-primary)', borderColor: 'var(--color-yellow)' },
  tabInactive: { background: 'transparent', color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)' },
  form:        { display: 'flex', flexDirection: 'column', gap: 8 },
  inputRow:    { display: 'flex', gap: 8, width: '100%' },
  inputWrapper:{ flex: 1, minWidth: 0 },
  input: {
    width: '100%', height: 48, padding: '0 16px',
    borderRadius: 'var(--radius-md)', border: '1.5px solid var(--color-border)',
    background: 'var(--color-surface)', color: 'var(--color-text-primary)',
    fontSize: 15, outline: 'none', transition: 'border-color 150ms ease, box-shadow 150ms ease',
  },
  inputError:   { borderColor: 'var(--color-grade-f)' },
  inputDisabled:{ opacity: 0.6, cursor: 'not-allowed' },
  submitBtn: {
    display: 'flex', alignItems: 'center', gap: 6, height: 48, padding: '0 24px',
    borderRadius: 'var(--radius-md)', background: 'var(--color-text-primary)',
    color: 'var(--color-bg)', fontSize: 15, fontWeight: 600, border: 'none',
    cursor: 'pointer', flexShrink: 0, transition: 'opacity 150ms ease', whiteSpace: 'nowrap',
  },
  submitBtnLoading: { opacity: 0.7, cursor: 'wait' },
  errorText:   { display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-grade-f)', fontSize: 13, fontWeight: 500 },
  helperText:  { color: 'var(--color-text-tertiary)', fontSize: 12, paddingLeft: 4 },
};

function ArrowIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function LoadingSpinner() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"
         stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
         style={{ animation: 'lc-spin 800ms linear infinite' }}>
      <style>{`@keyframes lc-spin { to { transform: rotate(360deg); } }`}</style>
      <path d="M12 2a10 10 0 0 1 10 10" opacity="0.25" /><path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
  );
}

export default SearchInput;
