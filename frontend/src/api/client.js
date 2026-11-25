import axios from 'axios';

export const API_BASE_URL = `${import.meta.env.VITE_API_BASE_URL || ''}/api`;

// Django URL routes require a trailing slash; normalize every outgoing path.
function ensureTrailingSlash(url) {
  if (!url) return url;
  const [path, query = ''] = url.split('?');
  if (!path.endsWith('/')) {
    return query ? `${path}/?${query}` : `${path}/`;
  }
  return query ? `${path}?${query}` : path;
}

const api = axios.create({ baseURL: API_BASE_URL });

// Attach the bearer token to every outgoing request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ap_access');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.url = ensureTrailingSlash(config.url);
  return config;
});

// Plain client for the refresh call so the interceptor below is not re-applied.
const refreshClient = axios.create({ baseURL: API_BASE_URL });
refreshClient.interceptors.request.use((config) => {
  config.url = ensureTrailingSlash(config.url);
  return config;
});

let refreshPromise = null;

function clearSession() {
  localStorage.removeItem('ap_access');
  localStorage.removeItem('ap_refresh');
  localStorage.removeItem('ap_user');
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error || {};
    const isAuthCall = config?.url?.includes('/auth/login') || config?.url?.includes('/auth/refresh');
    if (response?.status !== 401 || !config || config._retry || isAuthCall) {
      return Promise.reject(error);
    }

    config._retry = true;
    const refresh = localStorage.getItem('ap_refresh');
    if (!refresh) {
      clearSession();
      window.location.assign('/login');
      return Promise.reject(error);
    }

    try {
      // Single-flight: concurrent 401s share one refresh call.
      if (!refreshPromise) {
        refreshPromise = refreshClient
          .post('/auth/refresh', { refresh })
          .finally(() => {
            refreshPromise = null;
          });
      }
      const { data } = await refreshPromise;
      localStorage.setItem('ap_access', data.access);
      if (data.refresh) localStorage.setItem('ap_refresh', data.refresh);
      config.headers = { ...config.headers, Authorization: `Bearer ${data.access}` };
      return api(config); // retry the original request once
    } catch (refreshError) {
      clearSession();
      if (!window.location.pathname.startsWith('/login')) {
        window.location.assign('/login');
      }
      return Promise.reject(refreshError);
    }
  }
);

export default api;
