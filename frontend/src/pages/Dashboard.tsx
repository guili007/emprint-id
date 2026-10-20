import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useWebSocket } from '../hooks/useWebSocket';
import AlertBanner from '../components/AlertBanner';
import type { AgentRole, IntelStats } from '../types';
import { ROLE_LABELS } from '../types';
import { intelApi } from '../api/client';

export default function Dashboard() {
  const { role, username, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = role === 'ROLE_ADMIN';
  const { lastAlert, connected, clearAlert } = useWebSocket(isAdmin);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  if (!role) {
    navigate('/login');
    return null;
  }

  return (
    <div className="min-h-screen bg-navy-900 text-white">
      {lastAlert && <AlertBanner alert={lastAlert} onDismiss={clearAlert} />}

      <header className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <div>
          <p className="font-mono text-teal-400 font-bold text-sm tracking-widest">EmPrint-iD</p>
          <p className="text-white/40 text-xs font-mono">{ROLE_LABELS[role]}</p>
        </div>
        <div className="flex items-center gap-3">
          {isAdmin && (
            <span
              className={`text-xs font-mono px-2 py-0.5 rounded-full ${
                connected ? 'bg-teal-400/20 text-teal-400' : 'bg-red-500/20 text-red-400'
              }`}
            >
              {connected ? '● LIVE' : '○ OFFLINE'}
            </span>
          )}
          <span className="text-white/40 text-xs font-mono hidden sm:block">{username}</span>
          <button
            onClick={handleLogout}
            className="text-white/40 hover:text-white text-xs font-mono border border-white/10 px-3 py-1 rounded transition-colors"
          >
            DÉCO
          </button>
        </div>
      </header>

      <main className="max-w-md mx-auto p-4 pt-6">
        <RoleDashboard role={role} onScan={() => navigate('/verify')} />
      </main>
    </div>
  );
}

function RoleDashboard({ role, onScan }: { role: AgentRole; onScan: () => void }) {
  switch (role) {
    case 'ROLE_POLICE':
      return <PoliceDashboard onScan={onScan} />;
    case 'ROLE_BANK':
      return <BankDashboard onScan={onScan} />;
    case 'ROLE_BORDER':
      return <BorderDashboard onScan={onScan} />;
    case 'ROLE_HEALTH':
      return <HealthDashboard onScan={onScan} />;
    case 'ROLE_ADMIN':
      return <AdminDashboard onScan={onScan} />;
    case 'ROLE_INTEL':
      return <IntelDashboard onScan={onScan} />;
    case 'ROLE_EDU':
      return <EduDashboard onScan={onScan} />;
  }
}

// ─── POLICE ───────────────────────────────────────────────────────────────────

function PoliceDashboard({ onScan }: { onScan: () => void }) {
  const navigate = useNavigate();
  return (
    <div className="space-y-4">
      <SectionTitle>TABLEAU DE BORD — POLICE</SectionTitle>

      <ScanButton onClick={onScan} label="IDENTIFIER UN INDIVIDU" />

      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Vérifications" value="—" sub="aujourd'hui" />
        <StatCard label="Alertes actives" value="—" sub="watchlist" color="red" />
      </div>

      <div className="space-y-2">
        <p className="text-white/30 text-xs font-mono uppercase">Accès rapide</p>
        <QuickAction icon="⚠" label="Signaler incident" />
        <QuickAction icon="📋" label="Consulter watchlist" />
        <QuickAction icon="🔍" label="Recherche par national ID" onClick={() => navigate('/citizen/profile')} />
      </div>

      <Note>
        Résultats ROUGE et ORANGE transmis automatiquement au centre de commandement.
      </Note>
    </div>
  );
}

// ─── BANK ─────────────────────────────────────────────────────────────────────
// Silent Flagging : l'agent bancaire ne voit jamais le niveau watchlist.
// Il reçoit uniquement CONFORME / NON CONFORME.

function BankDashboard({ onScan }: { onScan: () => void }) {
  return (
    <div className="space-y-4">
      <SectionTitle>KYC — VÉRIFICATION CLIENT</SectionTitle>

      <ScanButton onClick={onScan} label="VÉRIFIER UN CLIENT" />

      <div className="grid grid-cols-2 gap-3">
        <StatCard label="KYC conformes" value="—" sub="aujourd'hui" color="teal" />
        <StatCard label="Non conformes" value="—" sub="aujourd'hui" />
      </div>

      <div className="bg-navy-700 rounded-xl p-4 border border-white/5 space-y-1">
        <p className="text-white/40 text-xs font-mono uppercase">Résultats possibles</p>
        <ResultRow color="teal" label="CONFORME" desc="Identité vérifiée — procéder normalement" />
        <ResultRow color="red" label="NON CONFORME" desc="Identité non reconnue — ne pas ouvrir le compte" />
      </div>

      <Note>
        Conformément à la politique KYC Rawbank. Tout résultat est enregistré dans l'audit trail.
      </Note>
    </div>
  );
}

// ─── BORDER ───────────────────────────────────────────────────────────────────

function BorderDashboard({ onScan }: { onScan: () => void }) {
  const isOnline = navigator.onLine;

  return (
    <div className="space-y-4">
      <SectionTitle>CONTRÔLE FRONTIÈRE</SectionTitle>

      <div
        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-mono ${
          isOnline
            ? 'bg-teal-400/10 text-teal-400 border border-teal-400/20'
            : 'bg-red-500/10 text-red-400 border border-red-500/20'
        }`}
      >
        <span>{isOnline ? '● POSTE CONNECTÉ' : '○ MODE HORS-LIGNE'}</span>
        {!isOnline && <span className="text-white/40">· Vérification QR uniquement</span>}
      </div>

      <ScanButton onClick={onScan} label="SCANNER LE VOYAGEUR" />

      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Passagers" value="—" sub="traités aujourd'hui" />
        <StatCard label="Alertes" value="—" sub="interceptées" color="red" />
      </div>

      <div className="space-y-2">
        <p className="text-white/30 text-xs font-mono uppercase">Procédures</p>
        <QuickAction icon="🚨" label="Déclencher alerte frontière" />
        <QuickAction icon="🛂" label="Signaler document suspect" />
      </div>

      <Note>
        En cas de ROUGE : retenir le voyageur et contacter le centre de commandement immédiatement.
      </Note>
    </div>
  );
}

// ─── HEALTH ───────────────────────────────────────────────────────────────────
// Interface épurée — seules les données civiles pertinentes pour la santé.

function HealthDashboard({ onScan }: { onScan: () => void }) {
  return (
    <div className="space-y-4">
      <SectionTitle>IDENTIFICATION PATIENT</SectionTitle>

      <ScanButton onClick={onScan} label="IDENTIFIER LE PATIENT" />

      <div className="bg-navy-700 rounded-xl p-4 border border-white/5 space-y-2">
        <p className="text-white/40 text-xs font-mono uppercase">Données récupérées</p>
        <ul className="text-white/60 text-sm font-mono space-y-1">
          <li>✓ Nom complet</li>
          <li>✓ Date de naissance</li>
          <li>✓ Province / commune d'origine</li>
          <li>✓ Numéro national (pour dossier médical)</li>
        </ul>
      </div>

      <div className="bg-navy-700 rounded-xl p-4 border border-white/5 space-y-2">
        <p className="text-white/40 text-xs font-mono uppercase">Données non accessibles</p>
        <ul className="text-red-400/50 text-sm font-mono space-y-1">
          <li>✗ Statut watchlist (confidentiel)</li>
          <li>✗ Antécédents judiciaires</li>
          <li>✗ Données bancaires</li>
        </ul>
      </div>

      <Note>
        Accès limité aux données nécessaires à la prise en charge médicale.
      </Note>
    </div>
  );
}

// ─── ADMIN ────────────────────────────────────────────────────────────────────

function AdminDashboard({ onScan }: { onScan: () => void }) {
  const navigate = useNavigate();
  return (
    <div className="space-y-4">
      <SectionTitle>ADMINISTRATION EYESHIELD</SectionTitle>

      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Vérifications" value="—" sub="aujourd'hui" color="teal" />
        <StatCard label="Alertes watchlist" value="—" sub="en cours" color="red" />
        <StatCard label="Agents actifs" value="—" sub="connectés" />
        <StatCard label="Taux de match" value="—" sub="biométrique" />
      </div>

      <ScanButton onClick={onScan} label="VÉRIFICATION MANUELLE" />

      <div className="space-y-2">
        <p className="text-white/30 text-xs font-mono uppercase">Gestion</p>
        <QuickAction icon="📋" label="Gérer la watchlist" />
        <QuickAction icon="👥" label="Agents & permissions" />
        <QuickAction icon="📊" label="Rapports & audit trail" />
        <QuickAction icon="⚠" label="Alertes Intel" onClick={() => navigate('/intel/alerts')} />
        <QuickAction icon="🌍" label="Zones de menace" onClick={() => navigate('/intel/threats')} />
      </div>

      <Note>
        Les alertes temps réel arrivent via WebSocket sur ce tableau de bord.
      </Note>
    </div>
  );
}

// ─── INTEL ────────────────────────────────────────────────────────────────────

function IntelDashboard({ onScan }: { onScan: () => void }) {
  const navigate = useNavigate();
  const [stats, setStats] = useState<IntelStats | null>(null);

  // Charge les stats au montage — erreur silencieuse, les "—" restent affichés
  useEffect(() => {
    intelApi.getStats()
      .then(r => setStats(r.data))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-4">
      <SectionTitle>EYESHIELD INTEL</SectionTitle>

      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Alertes ouvertes" value={stats ? String(stats.open_alerts) : '—'} sub="en cours" color="red" />
        <StatCard label="Critiques" value={stats ? String(stats.critical_alerts) : '—'} sub="haute priorité" color="red" />
        <StatCard label="Zones actives" value={stats ? String(stats.active_threat_zones) : '—'} sub="menaces terrain" />
        <StatCard label="Liens réseau" value={stats ? String(stats.total_network_links) : '—'} sub="total graphe" color="teal" />
      </div>

      <ScanButton onClick={onScan} label="IDENTIFICATION BIOMÉTRIQUE" />

      <div className="space-y-2">
        <p className="text-white/30 text-xs font-mono uppercase">Renseignement</p>
        <QuickAction icon="⚠" label="Alertes Intel" onClick={() => navigate('/intel/alerts')} />
        <QuickAction icon="🌍" label="Zones de menace" onClick={() => navigate('/intel/threats')} />
        <QuickAction icon="🕸" label="Graphe réseau" onClick={() => navigate('/intel/network')} />
        <QuickAction icon="🔍" label="Profil citoyen" onClick={() => navigate('/citizen/profile')} />
      </div>

      <Note>
        Accès complet aux renseignements classifiés. Toute consultation est journalisée.
      </Note>
    </div>
  );
}

// ─── EDU ──────────────────────────────────────────────────────────────────────

function EduDashboard({ onScan }: { onScan: () => void }) {
  return (
    <div className="space-y-4">
      <SectionTitle>ÉDUCATION — VÉRIFICATION</SectionTitle>

      <ScanButton onClick={onScan} label="IDENTIFIER L'ÉLÈVE / ÉTUDIANT" />

      <div className="bg-navy-700 rounded-xl p-4 border border-white/5 space-y-2">
        <p className="text-white/40 text-xs font-mono uppercase">Données accessibles</p>
        <ul className="text-white/60 text-sm font-mono space-y-1">
          <li>✓ Nom complet</li>
          <li>✓ Date de naissance</li>
          <li>✓ Numéro national (pour inscription)</li>
          <li>✓ Données EduFirst (si synchronisées)</li>
        </ul>
      </div>

      <Note>
        Accès limité aux données éducatives. Aucune donnée judiciaire ou financière.
      </Note>
    </div>
  );
}

// ─── Composants partagés ──────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h1 className="font-mono font-bold text-white text-base tracking-widest border-b border-white/10 pb-2">
      {children}
    </h1>
  );
}

function ScanButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className="w-full py-5 bg-teal-400/10 border-2 border-teal-400/40 hover:border-teal-400 rounded-xl font-mono font-bold text-teal-400 text-base transition-all hover:bg-teal-400/20 active:scale-95"
    >
      ◉ {label}
    </button>
  );
}

function StatCard({
  label,
  value,
  sub,
  color = 'white',
}: {
  label: string;
  value: string;
  sub: string;
  color?: 'teal' | 'red' | 'white';
}) {
  const valueColor =
    color === 'teal' ? 'text-teal-400' : color === 'red' ? 'text-red-400' : 'text-white';
  return (
    <div className="bg-navy-700 rounded-xl p-3 border border-white/5">
      <p className={`font-mono font-bold text-xl ${valueColor}`}>{value}</p>
      <p className="text-white/60 text-xs font-mono">{label}</p>
      <p className="text-white/30 text-xs font-mono">{sub}</p>
    </div>
  );
}

// onClick optionnel — les actions sans navigation fonctionnent toujours
function QuickAction({ icon, label, onClick }: { icon: string; label: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-3 bg-navy-700 hover:bg-navy-600 rounded-xl border border-white/5 text-white/70 hover:text-white font-mono text-sm text-left transition-colors"
    >
      <span className="text-base">{icon}</span>
      <span>{label}</span>
      <span className="ml-auto text-white/20">›</span>
    </button>
  );
}

function ResultRow({ color, label, desc }: { color: 'teal' | 'red'; label: string; desc: string }) {
  return (
    <div className="flex items-start gap-2 py-1">
      <span
        className={`shrink-0 text-xs font-mono font-bold px-2 py-0.5 rounded ${
          color === 'teal' ? 'bg-teal-400/20 text-teal-400' : 'bg-red-500/20 text-red-400'
        }`}
      >
        {label}
      </span>
      <span className="text-white/50 text-xs font-mono">{desc}</span>
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-white/25 text-xs font-mono border-t border-white/5 pt-3">{children}</p>
  );
}
