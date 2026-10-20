import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { intelApi } from '../api/client';
import type { IntelAlert, AlertSeverity, AlertStatus } from '../types';
import { useAuth } from '../contexts/AuthContext';

// Couleurs selon sévérité — du plus discret au plus urgent
const SEVERITY_COLOR: Record<AlertSeverity, string> = {
  LOW: 'text-white/50',
  MEDIUM: 'text-yellow-400',
  HIGH: 'text-orange-400',
  CRITICAL: 'text-red-400',
};

const STATUS_LABELS: Record<AlertStatus, string> = {
  OPEN: 'OUVERT',
  INVESTIGATING: 'EN COURS',
  CLOSED: 'CLÔTURÉ',
  FALSE_POSITIVE: 'FAUX POSITIF',
};

export default function IntelAlertsPage() {
  const navigate = useNavigate();
  const { role } = useAuth();
  const [alerts, setAlerts] = useState<IntelAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<IntelAlert | null>(null);
  const [filterSeverity, setFilterSeverity] = useState('');
  const canWrite = role === 'ROLE_INTEL' || role === 'ROLE_ADMIN';

  useEffect(() => {
    const params: Record<string, string> = {};
    if (filterSeverity) params.severity = filterSeverity;
    setLoading(true);
    intelApi
      .listAlerts(params)
      .then(r => setAlerts(r.data.results))
      .finally(() => setLoading(false));
  }, [filterSeverity]);

  async function handlePatchStatus(alertId: number, status: string) {
    try {
      const r = await intelApi.patchStatus(alertId, status);
      setAlerts(prev => prev.map(a => (a.id === alertId ? r.data : a)));
      if (selected?.id === alertId) setSelected(r.data);
    } catch {
      // Erreur silencieuse — l'UI reste dans l'état précédent
    }
  }

  if (selected) {
    return (
      <AlertDetail
        alert={selected}
        canWrite={canWrite}
        onPatch={handlePatchStatus}
        onBack={() => setSelected(null)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-navy-900 text-white">
      <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-white/40 hover:text-white font-mono text-sm"
        >
          ‹ RETOUR
        </button>
        <p className="font-mono text-teal-400 font-bold text-sm tracking-widest">ALERTES INTEL</p>
      </header>

      <div className="max-w-md mx-auto p-4 space-y-3">
        {/* Filtres sévérité */}
        <div className="flex gap-2 flex-wrap">
          {(['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map(s => (
            <button
              key={s}
              onClick={() => setFilterSeverity(s)}
              className={`text-xs font-mono px-3 py-1 rounded-full border transition-colors ${
                filterSeverity === s
                  ? 'border-teal-400 text-teal-400 bg-teal-400/10'
                  : 'border-white/20 text-white/40 hover:text-white/60'
              }`}
            >
              {s || 'TOUT'}
            </button>
          ))}
        </div>

        {loading && (
          <p className="text-white/30 font-mono text-xs text-center py-8">Chargement...</p>
        )}

        {!loading && alerts.length === 0 && (
          <p className="text-white/30 font-mono text-xs text-center py-8">Aucune alerte</p>
        )}

        {alerts.map(alert => (
          <button
            key={alert.id}
            onClick={() => setSelected(alert)}
            className="w-full text-left bg-navy-700 hover:bg-navy-600 rounded-xl p-4 border border-white/5 space-y-1 transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className={`text-xs font-mono font-bold ${SEVERITY_COLOR[alert.severity]}`}>
                {alert.severity}
              </span>
              <span className="text-white/30 text-xs font-mono">
                {STATUS_LABELS[alert.status]}
              </span>
            </div>
            <p className="text-white font-mono text-sm">{alert.title}</p>
            {alert.national_id && (
              <p className="text-white/40 font-mono text-xs">{alert.national_id}</p>
            )}
            <p className="text-white/30 font-mono text-xs">
              {new Date(alert.created_at).toLocaleDateString('fr-FR')}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Détail d'une alerte ──────────────────────────────────────────────────────

function AlertDetail({
  alert,
  canWrite,
  onPatch,
  onBack,
}: {
  alert: IntelAlert;
  canWrite: boolean;
  onPatch: (id: number, status: string) => void;
  onBack: () => void;
}) {
  return (
    <div className="min-h-screen bg-navy-900 text-white">
      <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10">
        <button onClick={onBack} className="text-white/40 hover:text-white font-mono text-sm">
          ‹ RETOUR
        </button>
        <p className="font-mono text-teal-400 font-bold text-sm tracking-widest">DÉTAIL ALERTE</p>
      </header>

      <div className="max-w-md mx-auto p-4 space-y-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-mono font-bold ${SEVERITY_COLOR[alert.severity]}`}>
              {alert.severity}
            </span>
            <span className="text-white/40 font-mono text-xs">{alert.alert_type}</span>
          </div>
          <h2 className="font-mono font-bold text-white">{alert.title}</h2>
          {alert.national_id && (
            <p className="text-teal-400 font-mono text-xs">ID: {alert.national_id}</p>
          )}
        </div>

        {alert.description && (
          <p className="text-white/60 font-mono text-sm">{alert.description}</p>
        )}

        {/* Preuves — JSONField brut exposé uniquement aux analystes */}
        {Object.keys(alert.evidence).length > 0 && (
          <div className="bg-navy-800 rounded-xl p-4 border border-white/5 space-y-2">
            <p className="text-white/30 text-xs font-mono uppercase">Preuves</p>
            {Object.entries(alert.evidence).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2">
                <span className="text-white/40 font-mono text-xs">{k}</span>
                <span className="text-white/70 font-mono text-xs text-right">{String(v)}</span>
              </div>
            ))}
          </div>
        )}

        <div className="bg-navy-700 rounded-xl p-4 border border-white/5 space-y-2">
          <div className="flex justify-between">
            <span className="text-white/40 font-mono text-xs">Statut</span>
            <span className="text-white/70 font-mono text-xs">{STATUS_LABELS[alert.status]}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/40 font-mono text-xs">Module source</span>
            <span className="text-white/70 font-mono text-xs">{alert.source_module || '—'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/40 font-mono text-xs">Créée le</span>
            <span className="text-white/70 font-mono text-xs">
              {new Date(alert.created_at).toLocaleString('fr-FR')}
            </span>
          </div>
          {alert.resolved_at && (
            <div className="flex justify-between">
              <span className="text-white/40 font-mono text-xs">Résolue le</span>
              <span className="text-white/70 font-mono text-xs">
                {new Date(alert.resolved_at).toLocaleString('fr-FR')}
              </span>
            </div>
          )}
        </div>

        {/* Actions de changement de statut — ROLE_INTEL et ROLE_ADMIN seulement */}
        {canWrite && alert.status === 'OPEN' && (
          <div className="flex gap-2">
            <button
              onClick={() => onPatch(alert.id, 'INVESTIGATING')}
              className="flex-1 py-2 font-mono text-xs border border-teal-400/40 text-teal-400 hover:bg-teal-400/10 rounded-lg transition-colors"
            >
              EN COURS
            </button>
            <button
              onClick={() => onPatch(alert.id, 'FALSE_POSITIVE')}
              className="flex-1 py-2 font-mono text-xs border border-white/20 text-white/40 hover:text-white hover:border-white/40 rounded-lg transition-colors"
            >
              FAUX POSITIF
            </button>
            <button
              onClick={() => onPatch(alert.id, 'CLOSED')}
              className="flex-1 py-2 font-mono text-xs border border-red-400/40 text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
            >
              CLÔTURER
            </button>
          </div>
        )}

        {canWrite && alert.status === 'INVESTIGATING' && (
          <div className="flex gap-2">
            <button
              onClick={() => onPatch(alert.id, 'CLOSED')}
              className="flex-1 py-2 font-mono text-xs border border-red-400/40 text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
            >
              CLÔTURER
            </button>
            <button
              onClick={() => onPatch(alert.id, 'FALSE_POSITIVE')}
              className="flex-1 py-2 font-mono text-xs border border-white/20 text-white/40 hover:text-white hover:border-white/40 rounded-lg transition-colors"
            >
              FAUX POSITIF
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
