import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { biometricApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useWebSocket } from '../hooks/useWebSocket';
import AlertBanner from '../components/AlertBanner';
import Camera from '../components/Camera';
import ScanResult from '../components/ScanResult';
import type { VerifyResponse } from '../types';
import { ROLE_LABELS } from '../types';

export default function VerifyPage() {
  const { role, username, logout } = useAuth();
  const navigate = useNavigate();
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<VerifyResponse | null>(null);

  // WebSocket actif seulement pour ADMIN (dashboard sécurité)
  const isAdmin = role === 'ROLE_ADMIN';
  const { lastAlert, clearAlert } = useWebSocket(isAdmin);

  async function handleCapture(base64: string) {
    setScanning(true);
    setResult(null);
    try {
      const { data } = await biometricApi.verify(base64);
      setResult(data);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: VerifyResponse } };
      if (axiosErr.response?.data) {
        setResult(axiosErr.response.data);
      } else {
        setResult({
          status: 'ERROR',
          message: 'Erreur réseau. Réessayez.',
          hmac: '',
        });
      }
    } finally {
      setScanning(false);
    }
  }

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
      {/* Alerte temps réel (ADMIN seulement) */}
      {lastAlert && <AlertBanner alert={lastAlert} onDismiss={clearAlert} />}

      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <div>
          <p className="font-mono text-teal-400 font-bold text-sm">EmPrint-iD</p>
          <p className="text-white/40 text-xs font-mono">{ROLE_LABELS[role]}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-white/40 text-xs font-mono hidden sm:block">{username}</span>
          <button
            onClick={handleLogout}
            className="text-white/40 hover:text-white text-xs font-mono border border-white/10 px-3 py-1 rounded transition-colors"
          >
            DÉCO
          </button>
        </div>
      </header>

      {/* Contenu principal */}
      <main className="max-w-md mx-auto p-4 pt-6 space-y-6">
        <div className="text-center">
          <h1 className="font-mono font-bold text-white text-lg">VÉRIFICATION BIOMÉTRIQUE</h1>
          <p className="text-white/40 text-xs font-mono mt-1">
            Placez le visage dans le cadre et appuyez sur scanner
          </p>
        </div>

        {result ? (
          <ScanResult result={result} role={role} onReset={() => setResult(null)} />
        ) : (
          <Camera onCapture={handleCapture} scanning={scanning} />
        )}
      </main>
    </div>
  );
}
