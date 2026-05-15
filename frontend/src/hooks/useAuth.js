/**
 * useAuth.js
 *
 * Supabase Magic Link Authentication Hook
 * -----------------------------------------
 * Manages the full auth lifecycle for LemonCheck:
 *   - Session persistence across page loads (Supabase handles this via localStorage)
 *   - Magic link sign-in (no password — user gets an email link)
 *   - Sign-out
 *   - Real-time session updates via onAuthStateChange
 *
 * How magic link auth works:
 *   1. User enters email → signIn(email) calls supabase.auth.signInWithOtp()
 *   2. Supabase sends an email with a magic link
 *   3. User clicks link → redirected to VITE_SITE_URL/auth/callback
 *   4. Supabase extracts the token from the URL and sets the session
 *   5. onAuthStateChange fires → user and session state update
 *   6. All subsequent API calls use session.access_token as the Bearer token
 *
 * Usage:
 *   const { user, session, signIn, signOut, isLoading } = useAuth()
 *   if (!user) return <AuthModal onSubmit={signIn} />
 *   await analyzeListingUrl(url, session.access_token)
 */

import { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';

export function useAuth() {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [isLoading, setIsLoading] = useState(true); // true until initial session check completes

  useEffect(() => {
    // ── On mount: restore session from localStorage ──────────────────────────
    // Supabase persists the session automatically; getSession() reads it back.
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setIsLoading(false);
    });

    // ── Subscribe to auth state changes ──────────────────────────────────────
    // Fires on: sign-in (magic link callback), sign-out, token refresh, expiry
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
        setIsLoading(false);
      }
    );

    // Cleanup subscription when component unmounts
    return () => subscription.unsubscribe();
  }, []);

  /**
   * Send a magic link to the given email address.
   * The user will receive an email and clicking the link completes sign-in.
   *
   * @param {string} email - User's email address
   * @returns {Promise<{ error: Error|null }>}
   */
  const signIn = async (email) => {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        // After clicking the magic link, redirect here so Supabase can
        // extract the token from the URL and set the session
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    return { error };
  };

  /**
   * Sign out the current user and clear the local session.
   *
   * @returns {Promise<{ error: Error|null }>}
   */
  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    return { error };
  };

  return {
    user,       // Supabase User object (null if not signed in)
    session,    // Supabase Session object — use session.access_token for API calls
    signIn,     // (email: string) => Promise<{ error }>
    signOut,    // () => Promise<{ error }>
    isLoading,  // true during initial session restore (prevents flash of auth modal)
  };
}
