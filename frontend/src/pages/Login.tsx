import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await authApi.login(username, password);
      login(data.access, data.refresh);
      navigate('/verify');
    } catch {
      setError('Identifiants incorrects.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-navy-900 flex flex-col items-center justify-center p-6">
      {/* Logo */}
      <div className="mb-8 text-center">
        <p className="font-mono text-teal-400 text-3xl font-bold tracking-widest">EmPrint-iD</p>
        <p className="text-white/40 text-xs font-mono mt-1">EYESHIELD PLATFORM · MODULE 01</p>
      </div>

      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4">
        <div>
          <label className="block text-white/50 text-xs font-mono mb-1 uppercase">
            Identifiant agent
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="w-full bg-navy-700 border border-white/10 rounded-lg px-4 py-3 text-white font-mono focus:outline-none focus:border-teal-400 transition-colors"
            placeholder="agent_001"
            autoComplete="username"
          />
        </div>
        <div>
          <label className="block text-white/50 text-xs font-mono mb-1 uppercase">
            Mot de passe
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full bg-navy-700 border border-white/10 rounded-lg px-4 py-3 text-white font-mono focus:outline-none focus:border-teal-400 transition-colors"
            autoComplete="current-password"
          />
        </div>

        {error && (
          <p className="text-red-400 text-sm font-mono text-center">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-4 bg-teal-400 hover:bg-teal-500 disabled:opacity-50 text-navy-900 font-mono font-bold rounded-xl transition-colors"
        >
          {loading ? 'CONNEXION…' : 'CONNEXION SÉCURISÉE'}
        </button>
      </form>

      <p className="mt-8 text-white/20 text-xs font-mono">
        Accès restreint · Système gouvernemental · RDC
      </p>
    </div>
  );
}
