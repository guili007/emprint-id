import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { intelApi } from '../api/client';
import type { NetworkGraph } from '../types';

const LINK_TYPE_LABELS: Record<string, string> = {
  FINANCIAL: 'Financier',
  FAMILY: 'Familial',
  GEOGRAPHIC: 'Géographique',
  TELECOM: 'Télécom',
  COWORKER: 'Collègue',
  ASSOCIATE: 'Associé',
};

// Couleur de badge selon la force du lien
function strengthColor(strength: number): string {
  if (strength >= 0.8) return 'text-red-400';
  if (strength >= 0.5) return 'text-orange-400';
  return 'text-white/40';
}

export default function NetworkGraphPage() {
  const navigate = useNavigate();
  const [nationalId, setNationalId] = useState('');
  const [graph, setGraph] = useState<NetworkGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSearch() {
    const id = nationalId.trim();
    if (!id) return;
    setLoading(true);
    setError('');
    setGraph(null);
    try {
      const r = await intelApi.getNetworkGraph(id);
      setGraph(r.data);
    } catch {
      setError('ID introuvable ou erreur de connexion.');
    } finally {
      setLoading(false);
    }
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
        <p className="font-mono text-teal-400 font-bold text-sm tracking-widest">GRAPHE RÉSEAU</p>
      </header>

      <div className="max-w-md mx-auto p-4 space-y-4">
        <div className="flex gap-2">
          <input
            value={nationalId}
            onChange={e => setNationalId(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="ID national (ex: CD-001-KIN)"
            className="flex-1 bg-navy-700 border border-white/10 rounded-lg px-3 py-2 font-mono text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal-400/50"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-4 py-2 bg-teal-400/10 border border-teal-400/40 hover:border-teal-400 text-teal-400 font-mono text-sm rounded-lg transition-colors disabled:opacity-40"
          >
            {loading ? '...' : 'ANALYSER'}
          </button>
        </div>

        {error && <p className="text-red-400 font-mono text-xs">{error}</p>}

        {graph && (
          <div className="space-y-4">
            {/* Métriques du sous-graphe 1-hop */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-navy-700 rounded-xl p-3 border border-white/5 text-center">
                <p className="font-mono font-bold text-white text-xl">{graph.total_nodes}</p>
                <p className="text-white/40 font-mono text-xs">nœuds</p>
              </div>
              <div className="bg-navy-700 rounded-xl p-3 border border-white/5 text-center">
                <p className="font-mono font-bold text-teal-400 text-xl">{graph.total_edges}</p>
                <p className="text-white/40 font-mono text-xs">liens</p>
              </div>
              <div className="bg-navy-700 rounded-xl p-3 border border-white/5 text-center">
                <p className="font-mono font-bold text-white text-xl">{graph.total_nodes - 1}</p>
                <p className="text-white/40 font-mono text-xs">voisins</p>
              </div>
            </div>

            {/* Sujet central */}
            <div className="bg-teal-400/10 border border-teal-400/30 rounded-xl p-3 text-center">
              <p className="font-mono text-teal-400 font-bold text-sm">SUJET</p>
              <p className="font-mono text-white text-xs">{graph.national_id}</p>
            </div>

            <div className="space-y-2">
              <p className="text-white/30 text-xs font-mono uppercase">Connexions directes</p>

              {graph.edges.length === 0 && (
                <p className="text-white/20 font-mono text-xs py-4 text-center">Aucun lien connu</p>
              )}

              {graph.edges.map((edge, i) => {
                // Le graphe est non-orienté logiquement — on récupère l'autre extrémité
                const neighborId =
                  edge.source === graph.national_id ? edge.target : edge.source;
                const neighborNode = graph.nodes.find(n => n.national_id === neighborId);

                return (
                  <div
                    key={i}
                    className="bg-navy-700 rounded-xl p-3 border border-white/5 flex items-center gap-3"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-mono text-sm text-white truncate">
                        {neighborNode?.name ?? neighborId}
                      </p>
                      {neighborNode?.name && (
                        <p className="font-mono text-xs text-white/40 truncate">{neighborId}</p>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-mono text-xs text-teal-400">
                        {LINK_TYPE_LABELS[edge.link_type] ?? edge.link_type}
                      </p>
                      <p className={`font-mono text-xs ${strengthColor(edge.strength)}`}>
                        {Math.round(edge.strength * 100)}%
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
