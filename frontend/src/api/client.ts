import axios from 'axios';
import type { AuthTokens, VerifyResponse } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL ?? '';

const api = axios.create({ baseURL: BASE_URL });

// Injecte le JWT à chaque requête
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Rafraîchit le token si 401
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        try {
          const { data } = await axios.post<{ access: string }>(
            `${BASE_URL}/api/token/refresh/`,
            { refresh }
          );
          localStorage.setItem('access_token', data.access);
          err.config.headers.Authorization = `Bearer ${data.access}`;
          return api.request(err.config);
        } catch {
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(err);
  }
);

export const authApi = {
  login: (username: string, password: string) =>
    api.post<AuthTokens>('/api/token/', { username, password }),
};

export const biometricApi = {
  verify: (imageBase64: string) =>
    api.post<VerifyResponse>('/api/v2/verify/', { image: imageBase64 }),
};

export default api;
