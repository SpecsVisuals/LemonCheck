/**
 * api.js
 *
 * LemonCheck Backend API Client
 * --------------------------------
 * Typed wrappers around all FastAPI backend calls.
 * Centralizes base URL config, auth header injection, and error handling.
 *
 * All functions are async and throw an ApiError on non-2xx responses.
 * The error includes { status, message, code } so the UI can handle
 * specific cases (e.g. 402 usage_limit_exceeded → show upgrade modal).
 *
 * Usage:
 *   import { analyzeListingUrl, getDemoResult } from '@/lib/api'
 *   const report = await analyzeListingUrl(url, session.access_token)
 */

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// Real analyses run the Claude agent + MCP tools — allow up to 120 seconds.
// Railway free tier cold-starts add 30-45s before the agent even begins;
// the analysis itself takes ~20-40s on top of that.
const ANALYSIS_TIMEOUT_MS = 120_000;

/**
 * Fetch with a timeout. Throws a named error if the request exceeds the limit.
 */
async function _fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError(504, 'The analysis took too long to respond. Railway may be waking up — wait 15 seconds and try again.', 'timeout');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// ── Error class ───────────────────────────────────────────────────────────────

/**
 * Structured error thrown by all API functions on non-2xx responses.
 * Callers can check error.status (e.g. 402) and error.code (e.g. 'usage_limit_exceeded').
 */
export class ApiError extends Error {
  constructor(status, message, code = null, detail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}


// ── Internal helpers ──────────────────────────────────────────────────────────

/**
 * Build standard headers for authenticated requests.
 * @param {string|null} token - Supabase JWT access token
 */
function _authHeaders(token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Parse a non-2xx response into a thrown ApiError.
 * Handles both JSON error bodies (FastAPI) and plain text.
 */
async function _handleError(response) {
  let message = `Request failed (${response.status})`;
  let code = null;
  let detail = null;

  try {
    const body = await response.json();
    // FastAPI HTTPException detail can be a string or an object
    if (typeof body.detail === 'string') {
      message = body.detail;
    } else if (typeof body.detail === 'object' && body.detail !== null) {
      message = body.detail.message ?? message;
      code = body.detail.error ?? null;
      detail = body.detail;
    }
  } catch {
    // Response body wasn't JSON — use the status text
    message = response.statusText || message;
  }

  throw new ApiError(response.status, message, code, detail);
}


// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Fetch the pre-computed demo DealReport (no auth required).
 * Used for ?demo=true mode and recruiter portfolio views.
 *
 * @returns {Promise<Object>} DealReport JSON
 */
export async function getDemoResult() {
  const response = await fetch(`${API_BASE}/demo`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!response.ok) {
    await _handleError(response);
  }

  return response.json();
}


/**
 * Submit a listing URL for analysis.
 *
 * @param {string} url - CarGurus or AutoTrader listing URL
 * @param {string} token - Supabase JWT access token
 * @returns {Promise<Object>} DealReport JSON
 * @throws {ApiError} 401 if token invalid, 402 if usage limit exceeded
 */
export async function analyzeListingUrl(url, token) {
  const response = await _fetchWithTimeout(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: _authHeaders(token),
    body: JSON.stringify({ listing_url: url, vin: null }),
  }, ANALYSIS_TIMEOUT_MS);

  if (!response.ok) {
    await _handleError(response);
  }

  return response.json();
}


/**
 * Submit a VIN for analysis.
 *
 * @param {string} vin - 17-character Vehicle Identification Number
 * @param {string} token - Supabase JWT access token
 * @returns {Promise<Object>} DealReport JSON
 * @throws {ApiError} 401 if token invalid, 402 if usage limit exceeded
 */
export async function analyzeVin(vin, token) {
  const response = await _fetchWithTimeout(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: _authHeaders(token),
    body: JSON.stringify({ listing_url: null, vin }),
  }, ANALYSIS_TIMEOUT_MS);

  if (!response.ok) {
    await _handleError(response);
  }

  return response.json();
}


/**
 * Submit both a listing URL and VIN for analysis (maximum data).
 *
 * @param {string} url - CarGurus or AutoTrader listing URL
 * @param {string} vin - 17-character VIN
 * @param {string} token - Supabase JWT access token
 * @returns {Promise<Object>} DealReport JSON
 */
export async function analyzeUrlAndVin(url, vin, token) {
  const response = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: _authHeaders(token),
    body: JSON.stringify({ listing_url: url, vin }),
  });

  if (!response.ok) {
    await _handleError(response);
  }

  return response.json();
}
