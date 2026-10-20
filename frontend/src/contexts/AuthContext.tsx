import React, { createContext, useContext, useEffect, useState } from 'react';
import { jwtDecode } from 'jwt-decode';
import type { AgentRole, JwtClaims } from '../types';

interface AuthState {
  accessToken: string | null;
  role: AgentRole | null;
  username: string | null;
  isAuthenticated: boolean;
  login: (access: string, refresh: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(
    () => localStorage.getItem('access_token')
  );
  const [role, setRole] = useState<AgentRole | null>(null);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setRole(null);
      setUsername(null);
      return;
    }
    try {
      const claims = jwtDecode<JwtClaims>(accessToken);
      // Vérifie expiration
      if (claims.exp * 1000 < Date.now()) {
        logout();
        return;
      }
      setRole(claims.role);
      setUsername(claims.username);
    } catch {
      logout();
    }
  }, [accessToken]);

  function login(access: string, refresh: string) {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    setAccessToken(access);
  }

  function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setAccessToken(null);
    setRole(null);
    setUsername(null);
  }

  return (
    <AuthContext.Provider
      value={{ accessToken, role, username, isAuthenticated: !!accessToken, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
