import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import i18n from './i18n';
import api from './api/client';

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!localStorage.getItem('token'));

  const applyUser = (u) => {
    setUser(u);
    if (u?.language) { i18n.changeLanguage(u.language); localStorage.setItem('lang', u.language); }
  };

  useEffect(() => {
    if (!localStorage.getItem('token')) return;
    api.get('/auth/me').then((r) => applyUser(r.data)).catch(() => localStorage.removeItem('token')).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const r = await api.post('/auth/login', { email, password });
    localStorage.setItem('token', r.data.access_token);
    applyUser(r.data.user);
    return r.data.user;
  }, []);

  const logout = useCallback(() => { localStorage.removeItem('token'); setUser(null); }, []);

  const setLang = useCallback(async (lng) => {
    i18n.changeLanguage(lng);
    localStorage.setItem('lang', lng);
    if (localStorage.getItem('token')) {
      try { const r = await api.patch('/auth/me', { language: lng }); setUser(r.data); } catch { /* ignore */ }
    }
  }, []);

  const refresh = useCallback(() => api.get('/auth/me').then((r) => setUser(r.data)), []);

  return <Ctx.Provider value={{ user, loading, login, logout, setLang, refresh }}>{children}</Ctx.Provider>;
}
