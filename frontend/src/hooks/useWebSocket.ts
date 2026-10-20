import { useEffect, useRef, useState } from 'react';
import type { WatchlistAlert } from '../types';

const WS_BASE = import.meta.env.VITE_WS_URL ?? `ws://${window.location.host}`;

export function useWebSocket(enabled: boolean) {
  const [lastAlert, setLastAlert] = useState<WatchlistAlert | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const token = localStorage.getItem('access_token');
    if (!token) return;

    // Le backend Django Channels lit le token via query param
    const ws = new WebSocket(`${WS_BASE}/ws/alerts/?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WatchlistAlert;
        if (data.type === 'WATCHLIST_HIT') {
          setLastAlert(data);
        }
      } catch {
        // message malformé — ignoré
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [enabled]);

  function clearAlert() {
    setLastAlert(null);
  }

  return { lastAlert, connected, clearAlert };
}
