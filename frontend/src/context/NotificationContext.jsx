import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import api from '../api/client';
import { useAuth } from './AuthContext';

const NotificationContext = createContext(null);

/**
 * Polls unread notification count every 30 seconds while a user is signed in,
 * and exposes helpers for the bell dropdown (list fetch, mark read, mark all read).
 */
export function NotificationProvider({ children }) {
  const { user } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const [items, setItems] = useState([]);

  const refreshUnread = useCallback(async () => {
    try {
      const { data } = await api.get('/notifications/unread-count');
      setUnreadCount(data?.count ?? 0);
    } catch {
      // Background polling — failures must not spam the UI; the bell simply stays stale.
    }
  }, []);

  const fetchList = useCallback(async () => {
    try {
      const { data } = await api.get('/notifications', { params: { unread: true, pageSize: 20 } });
      setItems(data?.results || []);
    } catch {
      // Silent: dropdown refresh failure is non-critical.
    }
  }, []);

  useEffect(() => {
    if (!user) {
      setUnreadCount(0);
      setItems([]);
      return undefined;
    }
    refreshUnread();
    const timer = setInterval(refreshUnread, 30000);
    return () => clearInterval(timer);
  }, [user, refreshUnread]);

  const markRead = useCallback(async (id) => {
    try {
      await api.post(`/notifications/${id}/read`);
      setItems((prev) => prev.filter((n) => n.id !== id));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // Silent.
    }
  }, []);

  const markAllRead = useCallback(async () => {
    try {
      await api.post('/notifications/read-all');
      setItems([]);
      setUnreadCount(0);
    } catch {
      // Silent.
    }
  }, []);

  const value = useMemo(
    () => ({ unreadCount, items, refreshUnread, fetchList, markRead, markAllRead }),
    [unreadCount, items, refreshUnread, fetchList, markRead, markAllRead]
  );

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotifications must be used within a NotificationProvider');
  return ctx;
}
