export type AgentRole =
  | 'ROLE_POLICE'
  | 'ROLE_BANK'
  | 'ROLE_BORDER'
  | 'ROLE_HEALTH'
  | 'ROLE_ADMIN';

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
};

export const ALERT_COLORS: Record<AlertLevel, string> = {
  ROUGE: 'bg-red-600 text-white',
  ORANGE: 'bg-orange-500 text-white',
  JAUNE: 'bg-yellow-400 text-navy-900',
};
