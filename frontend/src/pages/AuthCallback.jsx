/**
 * AuthCallback.jsx
 *
 * Magic Link Auth Callback Handler
 * ----------------------------------
 * Landing page for Supabase magic link redirects.
 *
 * When a user clicks a magic link in their email, Supabase redirects them to
 * /auth/callback with the session token embedded in the URL hash or query params.
 * The Supabase client automatically detects and exchanges this token on load.
 * Once onAuthStateChange fires with a valid session, we redirect home.
 *
 * If something goes wrong (expired link, already used), we redirect to /?auth=error.
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { Logo } from '@/components/Logo';

export default function AuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    // Supabase automatically picks up the token from the URL on client init.
    // We just need to listen for the session to be established.
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' && session) {
        // Session established — send user home
        navigate('/', { replace: true });
      } else if (event === 'TOKEN_REFRESHED') {
        navigate('/', { replace: true });
      }
    });

    // Fallback: if no auth event fires within 5s, something went wrong
    const timeout = setTimeout(() => {
      navigate('/?auth=error', { replace: true });
    }, 5000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, [navigate]);

  return (
    <div style={styles.page}>
      <Logo size="md" />
      <div style={styles.content}>
        <div style={styles.spinner} />
        <p style={styles.text}>Signing you in...</p>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    background: 'var(--color-bg)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 48,
  },
  content: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 16,
  },
  spinner: {
    width: 32,
    height: 32,
    border: '3px solid var(--color-border)',
    borderTopColor: 'var(--color-yellow)',
    borderRadius: '50%',
    animation: 'lc-spin 700ms linear infinite',
  },
  text: {
    fontSize: 15,
    color: 'var(--color-text-secondary)',
  },
};
