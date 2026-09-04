'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../lib/auth';

export default function LoginPage() {
  const { login, user } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (busy) {
      return;
    }

    setError('');
    setBusy(true);

    try {
      await login(email.trim().toLowerCase(), password);

      /*
       * IMPORTANT:
       * Use Next.js client-side navigation.
       *
       * Do NOT use window.location.replace().
       *
       * The authentication token is held in the existing
       * in-memory AuthProvider/API state. A full browser reload
       * would destroy that state.
       */
      router.replace('/');
    } catch (error: unknown) {
      setError(
        error instanceof Error
          ? error.message
          : 'Unable to sign in. Please check your credentials.',
      );
    } finally {
      setBusy(false);
    }
  }

  /*
   * AuthProvider will render the authenticated application
   * after successful login. Avoid rendering the login form
   * while an authenticated user already exists.
   */
  if (user) {
    return null;
  }

  return (
    <main className="login">
      <form className="login-card" onSubmit={submit}>
        <div className="brandmark">R</div>

        <h1>Sign in to RCAA</h1>

        <p>
          Payment operations and reconciliation console.
        </p>

        {error ? (
          <div className="notice error" role="alert">
            {error}
          </div>
        ) : null}

        <label className="field">
          Email

          <input
            required
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            disabled={busy}
          />
        </label>

        <label className="field">
          Password

          <input
            required
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            disabled={busy}
          />
        </label>

        <button
          className="btn primary full"
          type="submit"
          disabled={busy}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="muted">
          Need initial setup?{' '}
          <Link className="link" href="/register">
            Create administrator
          </Link>
        </p>

        <p className="muted">
          Authentication is handled by the RCAA backend.
        </p>
      </form>
    </main>
  );
}