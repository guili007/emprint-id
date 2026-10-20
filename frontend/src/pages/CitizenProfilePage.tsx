import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dataOntologyApi } from '../api/client';
import type { CitizenProfile } from '../types';

// TODO(human): Implémenter sectorColor(sector: string) → string (classe Tailwind).
// Chaque secteur de données mérite une couleur distincte pour faciliter
// la lecture rapide de l'ontologie. Exemple de secteurs :
// BANKING, HEALTH, JUSTICE, IDENTITY, FISCAL, EDUCATION, CIVIL, LAND, TELECOM, PUBLIC_SVC
// Contrainte : les couleurs doivent être lisibles sur fond navy-700.
function sectorColor(_sector: string): string {
  // TODO(human) — remplace ce placeholder par ton mapping secteur → couleur
  return 'text-white/50';
}

export default function CitizenProfilePage() {
  const navigate = useNavigate();
  const [nationalId, setNationalId] = useState('');
  const [profile, setProfile] = useState<CitizenProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSearch() {
    const id = nationalId.trim();
    if (!id) return;
    setLoading(true);
    setError('');
    setProfile(null);
    try {
      const r = await dataOntologyApi.getCitizenProfile(id);
      setProfile(r.data);
    } catch {
      setError('Citoyen introuvable ou accès refusé.');
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
        <p className="font-mono text-teal-400 font-bold text-sm tracking-widest">PROFIL CITOYEN</p>
      </header>

      <div className="max-w-md mx-auto p-4 space-y-4">
        <div className="flex gap-2">
          <input
            value={nationalId}
            onChange={e => setNationalId(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="Numéro national (ex: CD-001-KIN)"
            className="flex-1 bg-navy-700 border border-white/10 rounded-lg px-3 py-2 font-mono text-sm text-white placeholder-white/20 focus:outline-none focus:border-teal-400/50"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-4 py-2 bg-teal-400/10 border border-teal-400/40 hover:border-teal-400 text-teal-400 font-mono text-sm rounded-lg transition-colors disabled:opacity-40"
          >
            {loading ? '...' : 'CHERCHER'}
          </button>
        </div>

        {error && <p className="text-red-400 font-mono text-xs">{error}</p>}

        {profile && (
          <div className="space-y-4">
            {/* En-tête du profil */}
            <div className="bg-navy-700 rounded-xl p-4 border border-white/5 space-y-1">
              <p className="text-white/30 font-mono text-xs uppercase">Identifiant national</p>
              <p className="font-mono font-bold text-teal-400">{profile.national_id}</p>
              <p className="text-white/40 font-mono text-xs">
                {profile.total_sources} source(s) liée(s)
              </p>
            </div>

            {/* Liste des liens vers les sources externes */}
            <div className="space-y-2">
              <p className="text-white/30 font-mono text-xs uppercase">Sources connectées</p>

              {profile.links.length === 0 && (
                <p className="text-white/20 font-mono text-xs py-4 text-center">
                  Aucun lien enregistré
                </p>
              )}

              {profile.links.map(link => (
                <div
                  key={link.id}
                  className="bg-navy-700 rounded-xl p-3 border border-white/5 flex items-center gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-sm text-white">{link.source.name}</p>
                    <p className="font-mono text-xs text-white/40 truncate">
                      {link.label || link.external_id}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    {/* Couleur dépend de sectorColor() — TODO(human) ci-dessus */}
                    <span className={`font-mono text-xs font-bold ${sectorColor(link.source.sector)}`}>
                      {link.source.sector}
                    </span>
                    {link.verified_at && (
                      <p className="font-mono text-xs text-white/20">
                        ✓ {new Date(link.verified_at).toLocaleDateString('fr-FR')}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
