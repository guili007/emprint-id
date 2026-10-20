import type { WatchlistAlert } from '../types';
import { ALERT_COLORS } from '../types';

interface AlertBannerProps {
  alert: WatchlistAlert;
  onDismiss: () => void;
}

export default function AlertBanner({ alert, onDismiss }: AlertBannerProps) {
  return (
    <div
      className={`fixed top-0 left-0 right-0 z-50 p-4 shadow-2xl ${ALERT_COLORS[alert.alert_level]}`}
      role="alert"
    >
      <div className="flex items-start justify-between gap-3 max-w-md mx-auto">
        <div>
          <p className="font-mono font-bold text-sm">
            ⚠ ALERTE {alert.alert_level} — {alert.national_id}
          </p>
          <p className="text-xs opacity-80 mt-1">{alert.reason}</p>
        </div>
        <button
          onClick={onDismiss}
          className="text-xl leading-none opacity-70 hover:opacity-100 shrink-0"
          aria-label="Fermer"
        >
          ×
        </button>
      </div>
    </div>
  );
}
