import { useCallback, useEffect, useRef, useState } from 'react';

interface CameraProps {
  onCapture: (base64: string) => void;
  scanning: boolean;
}

export default function Camera({ onCapture, scanning }: CameraProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let stream: MediaStream;

    async function startCamera() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',   // caméra frontale
            width: { ideal: 640 },
            height: { ideal: 480 },
          },
          audio: false,
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          setReady(true);
        }
      } catch (err) {
        setError('Caméra inaccessible. Vérifiez les permissions du navigateur.');
        console.error(err);
      }
    }

    startCamera();

    return () => {
      stream?.getTracks().forEach((t) => t.stop());
      setReady(false);
    };
  }, []);

  const capture = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !ready) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Miroir horizontal pour que le selfie soit naturel
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);

    // Extrait seulement la partie base64 (sans le prefix data:image/jpeg;base64,)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    const base64 = dataUrl.split(',')[1];
    onCapture(base64);
  }, [ready, onCapture]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 bg-navy-800 rounded-xl border border-red-500/40 text-red-400 text-sm p-4 text-center">
        {error}
      </div>
    );
  }

  return (
    <div className="relative">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full rounded-xl bg-navy-800"
        style={{ transform: 'scaleX(-1)' }}
      />
      {/* Viseur biométrique */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div
          className={`w-48 h-60 border-2 rounded-full transition-colors ${
            scanning ? 'border-teal-400 shadow-lg shadow-teal-400/30 animate-pulse' : 'border-white/30'
          }`}
        />
      </div>
      {/* Canvas caché pour la capture */}
      <canvas ref={canvasRef} className="hidden" />
      <button
        onClick={capture}
        disabled={!ready || scanning}
        className={`mt-4 w-full py-4 rounded-xl font-mono font-bold text-navy-900 transition-all ${
          ready && !scanning
            ? 'bg-teal-400 hover:bg-teal-500 active:scale-95'
            : 'bg-teal-400/30 cursor-not-allowed text-teal-400/50'
        }`}
      >
        {scanning ? 'ANALYSE EN COURS…' : 'SCANNER LE VISAGE'}
      </button>
    </div>
  );
}
