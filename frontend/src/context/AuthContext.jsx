import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('ap_user') || 'null');
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser);

  const login = useCallback(async (username, password) => {
    const { data } = await api.post('/auth/login', { username, password });
    localStorage.setItem('ap_access', data.access);
    localStorage.setItem('ap_refresh', data.refresh);
    localStorage.setItem('ap_user', JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('ap_access');
    localStorage.removeItem('ap_refresh');
    localStorage.removeItem('ap_user');
    setUser(null);
  }, []);

  const hasRole = useCallback((...roles) => Boolean(user) && roles.includes(user.role), [user]);

  const value = useMemo(
    () => ({
      user,
      login,
      logout,
      hasRole,
      isAdmin: user?.role === 'ADMIN',
      isClerk: user?.role === 'AP_CLERK',
      isApprover: user?.role === 'APPROVER',
      isFinance: user?.role === 'FINANCE',
    }),
    [user, login, logout, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
