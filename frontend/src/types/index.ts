export type AgentRole =
  | 'ROLE_POLICE'
  | 'ROLE_BANK'
  | 'ROLE_BORDER'
  | 'ROLE_HEALTH'
  | 'ROLE_ADMIN'
  | 'ROLE_INTEL'
  | 'ROLE_EDU';

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface JwtClaims {
  user_id: number;
  role: AgentRole;
  exp: number;
  username: string;
}

// Réponse POST /api/v2/verify/
export interface VerifyResponse {
  status: 'VERIFIED' | 'REJECTED' | 'LIVENESS_FAILED' | 'WATCHLIST_HIT' | 'ERROR';
  // VERIFIED
  national_id?: string;
  full_name?: string;
  dob?: string;
  province?: string;
  commune?: string;
  confidence?: number;
  issued_at?: string;
  timestamp?: string;
  // Erreur / rejet
  reason?: string;
  message?: string;
  // Watchlist
  alert_level?: AlertLevel;
  // Signature HMAC de chaque réponse
  hmac: string;
}

export type AlertLevel = 'ROUGE' | 'ORANGE' | 'JAUNE';

// Message WebSocket depuis le dashboard sécurité
export interface WatchlistAlert {
  type: 'WATCHLIST_HIT';
  alert_level: AlertLevel;
  national_id: string;
  reason: string;
}

export const ROLE_LABELS: Record<AgentRole, string> = {
  ROLE_POLICE: 'Police Nationale',
  ROLE_BANK: 'Agent Bancaire',
  ROLE_BORDER: 'Contrôle Frontière',
  ROLE_HEALTH: 'Personnel Santé',
  ROLE_ADMIN: 'Administrateur',
  ROLE_INTEL: 'Analyste Intel',
  ROLE_EDU: 'Agent Éducation',
};

export const ALERT_COLORS: Record<AlertLevel, string> = {
  ROUGE: 'bg-red-600 text-white',
  ORANGE: 'bg-orange-500 text-white',
  JAUNE: 'bg-yellow-400 text-navy-900',
};

// Réponse paginée standard Django REST Framework
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ── Module 04 Eyeshield Intel ─────────────────────────────────────────────────

export type AlertType =
  | 'STRUCTURING'
  | 'NETWORK'
  | 'FREQUENCY'
  | 'GEOGRAPHIC'
  | 'BIOMETRIC'
  | 'WATCHLIST_CROSS'
  | 'MANUAL';

export type AlertSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type AlertStatus = 'OPEN' | 'INVESTIGATING' | 'CLOSED' | 'FALSE_POSITIVE';

export interface IntelAlert {
  id: number;
  national_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  title: string;
  description: string;
  status: AlertStatus;
  evidence: Record<string, unknown>;
  source_module: string;
  created_at: string;
  resolved_at: string | null;
}

export interface NetworkNode {
  national_id: string;
  name?: string;
  is_subject: boolean;
}

export interface NetworkEdge {
  source: string;
  target: string;
  link_type: string;
  strength: number;
}

export interface NetworkGraph {
  national_id: string;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface ThreatZone {
  id: number;
  name: string;
  province: string;
  territoire?: string;
  threat_type: string;
  severity: string;
  status: string;
  description?: string;
  coordinates: [number, number][];
  created_at: string;
  updated_at: string;
}

export interface IntelStats {
  total_alerts: number;
  open_alerts: number;
  critical_alerts: number;
  active_threat_zones: number;
  total_network_links: number;
}

// ── Module 02 Eyeshield Data — Ontologie ──────────────────────────────────────

export interface DataSource {
  id: number;
  code: string;
  name: string;
  sector: string;
  description?: string;
  is_active: boolean;
}

export interface CitizenDataLink {
  id: number;
  national_id: string;
  source: DataSource;
  external_id: string;
  label: string;
  verified_at: string | null;
}

export interface CitizenProfile {
  national_id: string;
  sources: DataSource[];
  links: CitizenDataLink[];
  total_sources: number;
}
