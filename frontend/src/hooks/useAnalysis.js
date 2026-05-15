/**
 * useAnalysis.js
 *
 * Custom React hook that manages the full analysis request lifecycle.
 * Calls POST /analyze on the FastAPI backend with the listing URL or VIN.
 * Returns: { result, isLoading, error, runAnalysis }.
 * Handles ?demo=true by calling GET /demo instead of POST /analyze.
 */

export function useAnalysis() {
  // TODO: implement
  return { result: null, isLoading: false, error: null, runAnalysis: () => {} };
}
