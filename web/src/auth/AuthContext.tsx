import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, setUnauthorizedHandler, tokenStore } from '../api/client';
import { WRITE_ROLES, type LoginOut, type UserOut } from '../api/types';

export type AuthState = {
  user: UserOut | null;
  token: string | null;
  loading: boolean;
  canWrite: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** Đọc lại `/auth/me` (vai trò đổi giữa chừng; F18 R12, WS 4403). */
  reloadUser: () => void;
};

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => tokenStore.get());
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState<boolean>(() => tokenStore.get() !== null);

  const logout = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    setUser(null);
  }, []);

  const reloadUser = useCallback(() => {
    setLoading(true);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (!token || user) return;
    let cancelled = false;
    api<UserOut>('/auth/me')
      .then((me) => !cancelled && setUser(me))
      .catch(() => !cancelled && logout())
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [token, user, logout]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api<LoginOut>('/auth/login', {
      method: 'POST',
      body: { username, password },
    });
    tokenStore.set(res.access_token);
    setToken(res.access_token);
    setUser(res.user);
    setLoading(false);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      token,
      loading,
      canWrite: user !== null && WRITE_ROLES.includes(user.role),
      login,
      logout,
      reloadUser,
    }),
    [user, token, loading, login, logout, reloadUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
