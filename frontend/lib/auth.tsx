'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react';

import {
  api,
  clearToken,
  getToken,
  setToken,
} from './api';

import type { User } from '../types';

type AuthContext = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const Auth = createContext<AuthContext>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    function handleAuthExpired() {
      clearToken();
      if (active) {
        setUser(null);
        setLoading(false);
      }
      if (typeof window !== 'undefined' && window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.replace('/login');
      }
    }

    window.addEventListener('rcaa:auth-expired', handleAuthExpired);

    async function restoreSession() {
      const existingToken = getToken();

      if (!existingToken) {
        if (active) {
          setLoading(false);
        }
        return;
      }

      try {
        const currentUser = await api<User>('/auth/me');

        if (active) {
          setUser(currentUser);
        }
      } catch {
        clearToken();

        if (active) {
          setUser(null);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void restoreSession();

    return () => {
      active = false;
      window.removeEventListener('rcaa:auth-expired', handleAuthExpired);
    };
  }, []);

  async function login(email: string, password: string) {
    setLoading(true);

    try {
      const response = await api<{
        access_token: string;
      }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
        }),
      });

      if (!response?.access_token) {
        throw new Error('Login succeeded but no access token was returned.');
      }

      setToken(response.access_token);

      const currentUser = await api<User>('/auth/me');

      setUser(currentUser);
    } catch (error) {
      clearToken();
      setUser(null);
      throw error;
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    clearToken();
    setUser(null);
    window.location.replace('/login');
  }

  return (
    <Auth.Provider
      value={{
        user,
        loading,
        login,
        logout,
      }}
    >
      {children}
    </Auth.Provider>
  );
}

export function useAuth() {
  return useContext(Auth);
}