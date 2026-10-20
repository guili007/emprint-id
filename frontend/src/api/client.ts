import axios from 'axios';
import type {
  AuthTokens,
  VerifyResponse,
  PaginatedResponse,
  IntelAlert,
  NetworkGraph,
  ThreatZone,
  IntelStats,
  CitizenProfile,
} from '../types';

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

// ── Module 04 Intel — /api/v4/intel/ ─────────────────────────────────────────

export const intelApi = {
  // Alertes
  listAlerts: (params?: Record<string, string>) =>
    api.get<PaginatedResponse<IntelAlert>>('/api/v4/intel/alerts/', { params }),
  createAlert: (data: Partial<IntelAlert>) =>
    api.post<IntelAlert>('/api/v4/intel/alerts/', data),
  getAlert: (id: number) =>
    api.get<IntelAlert>(`/api/v4/intel/alerts/${id}/`),
  patchStatus: (id: number, status: string) =>
    api.patch<IntelAlert>(`/api/v4/intel/alerts/${id}/status/`, { status }),

  // Graphe réseau
  getNetworkGraph: (nationalId: string, params?: { min_strength?: string }) =>
    api.get<NetworkGraph>(`/api/v4/intel/network/${nationalId}/`, { params }),
  createNetworkLink: (data: object) =>
    api.post('/api/v4/intel/network/links/', data),

  // Zones de menace
  listThreatZones: (params?: Record<string, string>) =>
    api.get<PaginatedResponse<ThreatZone>>('/api/v4/intel/threats/', { params }),
  createThreatZone: (data: object) =>
    api.post('/api/v4/intel/threats/', data),

  // Statistiques dashboard
  getStats: () =>
    api.get<IntelStats>('/api/v4/intel/stats/'),
};

// ── Module 02 Data Ontologie — /api/v3/data/ ──────────────────────────────────

export const dataOntologyApi = {
  listSources: () =>
    api.get('/api/v3/data/sources/'),
  getCitizenProfile: (nationalId: string) =>
    api.get<CitizenProfile>(`/api/v3/data/citizens/${nationalId}/profile/`),
  getOntologyStats: () =>
    api.get('/api/v3/data/ontology/stats/'),
};

export default api;
