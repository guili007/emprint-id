import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { intelApi } from '../api/client';
import type { ThreatZone } from '../types';

const SEVERITY_COLORS: Record<string, string> = {
  LOW: 'text-white/50',
  MEDIUM: 'text-yellow-400',
  HIGH: 'text-orange-400',
  CRITICAL: 'text-red-400',
};

const THREAT_TYPE_LABELS: Record<string, string> = {
  BANDITRY: 'Banditisme',
  ARMED_GROUP: 'Groupe armé',
  TRAFFICKING: 'Trafic',
  FRAUD: 'Fraude',
  TERRORISM: 'Terrorisme',
  OTHER: 'Autre',
};

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: 'text-red-400',
  MONITORING: 'text-yellow-400',
  RESOLVED: 'text-white/30',
};

export default function ThreatZonesPage() {
  const navigate = useNavigate();
  const [zones, setZones] = useState<ThreatZone[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ThreatZone | null>(null);

  useEffect(() => {
    intelApi
      .listThreatZones()
      .then(r => setZones(r.data.results))
      .finally(() => setLoading(false));
  }, []);

  if (selected) {
    return <ZoneDetail zone={selected} onBack={() => setSelected(null)} />;
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
        <p className="font-mono text-teal-400 font-bold text-sm tracking-widest">ZONES DE MENACE</p>
      </header>

      <div className="max-w-md mx-auto p-4 space-y-3">
        {loading && (
          <p className="text-white/30 font-mono text-xs text-center py-8">Chargement...</p>
        )}

        {!loading && zones.length === 0 && (
          <p className="text-white/30 font-mono text-xs text-center py-8">
            Aucune zone déclarée
          </p>
        )}

        {zones.map(zone => (
          <button
            key={zone.id}
            onClick={() => setSelected(zone)}
            className="w-full text-left bg-navy-700 hover:bg-navy-600 rounded-xl p-4 border border-white/5 space-y-1 transition-colors"
          >
            <div className="flex items-center justify-between">
              <span
                className={`text-xs font-mono font-bold ${
                  SEVERITY_COLORS[zone.severity] ?? 'text-white'
                }`}
              >
                {zone.severity}
              </span>
              <span
                className={`text-xs font-mono ${STATUS_COLORS[zone.status] ?? 'text-white/30'}`}
              >
                {zone.status}
              </span>
            </div>
            <p className="text-white font-mono text-sm">{zone.name}</p>
            <p className="text-white/40 font-mono text-xs">
              {zone.province}
              {zone.territoire ? ` · ${zone.territoire}` : ''}
            </p>
            <p className="text-white/30 font-mono text-xs">
              {THREAT_TYPE_LABELS[zone.threat_type] ?? zone.threat_type}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Détail d'une zone ────────────────────────────────────────────────────────

function ZoneDetail({ zone, onBack }: { zone: ThreatZone; onBack: () => void }) {
  return (
    <div className="min-h-screen bg-navy-900 text-white">
      <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10">
        <button onClick={onBack} className="text-white/40 hover:text-white font-mono text-sm">
          ‹ RETOUR
        </button>
        <p className="font-mono text-teal-400 font-bold text-sm tracking-widest">ZONE DÉTAIL</p>
      </header>

      <div className="max-w-md mx-auto p-4 space-y-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={`text-xs font-mono font-bold ${
                SEVERITY_COLORS[zone.severity] ?? 'text-white'
              }`}
            >
              {zone.severity}
            </span>
            <span className="text-white/40 font-mono text-xs">
              {THREAT_TYPE_LABELS[zone.threat_type] ?? zone.threat_type}
            </span>
          </div>
          <h2 className="font-mono font-bold text-white">{zone.name}</h2>
          <p className="text-white/40 font-mono text-xs">
            {zone.province}
            {zone.territoire ? ` · ${zone.territoire}` : ''}
          </p>
        </div>

        {zone.description && (
          <p className="text-white/60 font-mono text-sm">{zone.description}</p>
        )}

        <div className="bg-navy-700 rounded-xl p-4 border border-white/5 space-y-2">
          <div className="flex justify-between">
            <span className="text-white/40 font-mono text-xs">Statut</span>
            <span
              className={`font-mono text-xs ${STATUS_COLORS[zone.status] ?? 'text-white/70'}`}
            >
              {zone.status}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/40 font-mono text-xs">Points géographiques</span>
            <span className="text-white/70 font-mono text-xs">{zone.coordinates.length}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/40 font-mono text-xs">Déclarée le</span>
            <span className="text-white/70 font-mono text-xs">
              {new Date(zone.created_at).toLocaleDateString('fr-FR')}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/40 font-mono text-xs">Mise à jour</span>
            <span className="text-white/70 font-mono text-xs">
              {new Date(zone.updated_at).toLocaleDateString('fr-FR')}
            </span>
          </div>
        </div>

        {/* Coordonnées brutes — utiles pour export cartographique */}
        {zone.coordinates.length > 0 && (
          <div className="bg-navy-800 rounded-xl p-4 border border-white/5 space-y-1">
            <p className="text-white/30 text-xs font-mono uppercase">Périmètre (lat, lon)</p>
            {zone.coordinates.slice(0, 5).map(([lat, lon], i) => (
              <p key={i} className="text-white/40 font-mono text-xs">
                {lat.toFixed(4)}, {lon.toFixed(4)}
              </p>
            ))}
            {zone.coordinates.length > 5 && (
              <p className="text-white/20 font-mono text-xs">
                + {zone.coordinates.length - 5} points supplémentaires
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
