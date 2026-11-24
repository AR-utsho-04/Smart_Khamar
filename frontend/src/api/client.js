import axios from 'axios';
import { useCallback, useEffect, useState } from 'react';

const api = axios.create({ baseURL: '/api/v1' });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    const isLogin = e.config?.url?.includes('/auth/login');
    if (e.response?.status === 401 && !isLogin && !location.pathname.startsWith('/login')) {
      localStorage.removeItem('token');
      location.href = '/login';
    }
    return Promise.reject(e);
  }
);

/** Human-readable error text. Uses translated messages for known error codes. */
export function errText(e, t) {
  const d = e?.response?.data;
  if (t && !e?.response) return t('errors.network');  // no answer at all: backend not running
  if (t && e.response.status >= 500 && typeof d?.detail !== 'string') return t('errors.server_down');  // proxy could not reach the backend
  if (d?.errors?.length) return d.errors.map((x) => (x.row ? `Row ${x.row}: ` : '') + (x.field ? `${x.field}: ` : '') + x.message).join('; ');
  const code = typeof d?.detail === 'string' ? d.detail : null;
  if (code && t) {
    const tr = t(`errors.${code}`, { defaultValue: '' });
    if (tr) return tr;
  }
  return code || e?.message || 'Error';
}

/** Fetch a URL and keep loading/error state. Pass url=null to skip. */
export function useFetch(url, params, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!!url);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);
  const key = JSON.stringify(params || {});
  useEffect(() => {
    if (!url) { setLoading(false); return; }
    let live = true;
    setLoading(true);
    api.get(url, { params }).then((r) => { if (live) { setData(r.data); setError(null); } })
      .catch((e) => { if (live) setError(e); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, key, tick, ...deps]);
  const reload = useCallback(() => setTick((x) => x + 1), []);
  return { data, loading, error, reload };
}

/** Download a file (PDF/CSV) with the auth header. */
export async function download(url, params, fallbackName) {
  const r = await api.get(url, { params, responseType: 'blob' });
  const cd = r.headers['content-disposition'] || '';
  const m = /filename="?([^"]+)"?/.exec(cd);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(r.data);
  a.download = m ? m[1] : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export default api;
