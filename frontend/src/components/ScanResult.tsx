import type { AgentRole, VerifyResponse } from '../types';
import { ROLE_LABELS } from '../types';

interface ScanResultProps {
  result: VerifyResponse;
  role: AgentRole;
  onReset: () => void;
}

export default function ScanResult({ result, role, onReset }: ScanResultProps) {
  const isVerified = result.status === 'VERIFIED';
  const isWatchlist = result.status === 'WATCHLIST_HIT';

  return (
    <div className="space-y-4">
      {/* Bandeau statut */}
      <div
        className={`p-4 rounded-xl text-center font-mono font-bold text-lg ${
          isVerified
            ? 'bg-teal-400/20 border border-teal-400 text-teal-400'
            : isWatchlist
            ? 'bg-red-600/20 border border-red-500 text-red-400'
            : 'bg-red-900/30 border border-red-800 text-red-400'
        }`}
      >
        {isVerified ? '✓ IDENTITÉ CONFIRMÉE' : isWatchlist ? '⚠ ALERTE WATCHLIST' : '✗ ' + result.status}
      </div>

      {isVerified && (
        <div className="bg-navy-700 rounded-xl p-4 space-y-2 font-mono text-sm">
          <Field label="NATIONAL ID" value={result.national_id} />
          <Field label="NOM COMPLET" value={result.full_name} bold />
          <Field label="DATE DE NAISSANCE" value={result.dob} />
          <Field label="PROVINCE" value={result.province} />
          <Field label="COMMUNE" value={result.commune} />
          <Field
            label="CONFIANCE"
            value={result.confidence ? `${(result.confidence * 100).toFixed(1)}%` : undefined}
            highlight
          />
          <div className="border-t border-white/10 pt-2 text-white/40 text-xs">
            Rôle agent : {ROLE_LABELS[role]} · {new Date().toLocaleTimeString('fr-CD')}
          </div>
        </div>
      )}

      {isWatchlist && (
        <div className="bg-red-900/20 rounded-xl p-4 space-y-2 font-mono text-sm border border-red-500/30">
          <Field label="NIVEAU ALERTE" value={result.alert_level} />
          <Field label="MOTIF" value={result.reason} />
          <p className="text-red-400/60 text-xs mt-2">
            Une alerte silencieuse a été transmise au centre de contrôle.
          </p>
        </div>
      )}

      {!isVerified && !isWatchlist && (
        <div className="bg-navy-700 rounded-xl p-4 font-mono text-sm text-white/60">
          {result.reason ?? result.message ?? 'Vérification échouée.'}
        </div>
      )}

      <button
        onClick={onReset}
        className="w-full py-3 border border-white/20 rounded-xl text-white/60 font-mono text-sm hover:bg-white/5 transition-colors"
      >
        NOUVELLE VÉRIFICATION
      </button>
    </div>
  );
}

function Field({
  label,
  value,
  bold = false,
  highlight = false,
}: {
  label: string;
  value?: string | null;
  bold?: boolean;
  highlight?: boolean;
}) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-2">
      <span className="text-white/40 uppercase text-xs">{label}</span>
      <span
        className={`text-right ${bold ? 'text-white font-bold' : ''} ${
          highlight ? 'text-teal-400' : 'text-white/80'
        }`}
      >
        {value}
      </span>
    </div>
  );
}
