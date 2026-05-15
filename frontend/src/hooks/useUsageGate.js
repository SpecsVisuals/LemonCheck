/**
 * useUsageGate.js
 *
 * Free-Tier Usage Gate Hook
 * --------------------------
 * Enforces the 5 analyses/month free tier and drives the auth/upgrade modal flow.
 *
 * Gate logic (in order):
 *   1. isLoading → wait (don't flash modals before session restores)
 *   2. user is null → showAuthModal: true (prompt sign-in before analyzing)
 *   3. usageCount >= FREE_TIER_LIMIT → showUpgradeModal: true
 *   4. Otherwise → canAnalyze: true
 *
 * Usage count is read from the backend's 402 response on the first over-limit
 * attempt. We don't pre-fetch usage on load to avoid unnecessary DB calls —
 * most users won't be at the limit most of the time.
 *
 * Usage:
 *   const { canAnalyze, showAuthModal, showUpgradeModal, usageCount, onLimitHit } = useUsageGate()
 *
 *   // In your submit handler:
 *   if (!canAnalyze) return  // gate is already showing a modal
 *   try {
 *     const report = await analyzeListingUrl(url, session.access_token)
 *   } catch (err) {
 *     if (err.status === 402) onLimitHit(err.detail)
 *   }
 */

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';

const FREE_TIER_LIMIT = 5;

export function useUsageGate() {
  const { user, isLoading } = useAuth();

  // usageCount is set reactively when the backend returns a 402
  const [usageCount, setUsageCount] = useState(0);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  // Derive gate state from auth + usage
  const showAuthModal = !isLoading && !user;
  const isOverLimit = usageCount >= FREE_TIER_LIMIT;
  const canAnalyze = !isLoading && !!user && !isOverLimit;

  /**
   * Call this when the backend returns a 402 Payment Required.
   * Extracts the usage count from the error detail and triggers the upgrade modal.
   *
   * @param {Object|null} detail - The error.detail object from ApiError
   */
  const onLimitHit = (detail) => {
    const count = detail?.usage_count ?? FREE_TIER_LIMIT;
    setUsageCount(count);
    setShowUpgradeModal(true);
  };

  /**
   * Dismiss the upgrade modal (e.g. user clicks "Maybe Later").
   */
  const dismissUpgradeModal = () => setShowUpgradeModal(false);

  return {
    canAnalyze,           // true if user is authed and under the limit
    showAuthModal,        // true if user needs to sign in before analyzing
    showUpgradeModal,     // true if user has hit the monthly limit
    usageCount,           // current month's analysis count (set after 402)
    limit: FREE_TIER_LIMIT,
    isLoading,            // true during session restore (prevents flash)
    onLimitHit,           // call with err.detail when backend returns 402
    dismissUpgradeModal,  // close the upgrade modal
  };
}
