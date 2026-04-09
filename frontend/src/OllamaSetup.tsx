import React, { useState, useEffect } from 'react';

interface OllamaStatus {
  installed: boolean;
  running: boolean;
  model_downloaded: boolean;
}

interface OllamaSetupProps {
  onStatusChange?: (status: OllamaStatus) => void;
  standalone?: boolean;
  onClose?: () => void;
}

export const OllamaSetup: React.FC<OllamaSetupProps> = ({ onStatusChange, standalone = false, onClose }) => {
  const [status, setStatus] = useState<OllamaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const checkStatus = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/ollama/status');
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        if (onStatusChange) onStatusChange(data);
      }
    } catch (err) {
      console.error('Error checking Ollama status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkStatus();
    // Polling cada 5 segundos si estamos instalando
    let interval: number;
    if (installing || pulling) {
      interval = setInterval(checkStatus, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [installing, pulling]);

  const handleInstall = async () => {
    setInstalling(true);
    setError(null);
    setMessage('Iniciando instalación silenciosa. Por favor, acepta los permisos de Administrador si Windows te los pide. Esto tomará un par de minutos...');
    try {
      const res = await fetch('http://127.0.0.1:8000/api/ollama/install', { method: 'POST' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Error instalando Ollama');
      }
    } catch (err: any) {
      setError(err.message);
      setInstalling(false);
    }
  };

  const handlePull = async () => {
    setPulling(true);
    setError(null);
    setMessage('Descargando el modelo Gemma 4 (varía según tu conexión a internet)...');
    try {
      const res = await fetch('http://127.0.0.1:8000/api/ollama/pull', { method: 'POST' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Error descargando el modelo');
      }
      // Cuando termina el pull (la request puede tardar mucho o simplemente empezar)
      await checkStatus();
      setPulling(false);
      setMessage('✅ Modelo descargado exitosamente.');
    } catch (err: any) {
      setError(err.message);
      setPulling(false);
    }
  };

  if (loading && !status) return <div className="text-sm text-gray-500 animate-pulse">Verificando estado de IA Local...</div>;

  const isReady = status?.installed && status?.model_downloaded;

  const content = (
    <div className={`space-y-4 ${standalone ? 'p-6 bg-white dark:bg-gray-900 rounded-3xl shadow-2xl border border-gray-100 dark:border-gray-800 max-w-lg w-full' : ''}`}>
      {standalone && (
        <div className="text-center mb-6">
          <div className="text-4xl mb-4">🧠</div>
          <h2 className="text-2xl font-bold">Motor de IA Local</h2>
          <p className="text-sm text-gray-500 mt-2">Configura Datix para ejecutarse 100% local sin costo ni límites.</p>
        </div>
      )}

      {/* Estado Actual */}
      <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <span>⚙️</span> Estado del Sistema
        </h3>
        <ul className="text-sm space-y-2">
          <li className="flex justify-between items-center">
            <span className="text-gray-600 dark:text-gray-400">Ollama (Motor):</span>
            <span className={status?.installed ? "text-green-600 font-medium" : "text-red-500 font-medium"}>
              {status?.installed ? "Instalado" : "No Instalado"}
            </span>
          </li>
          {status?.installed && (
            <li className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Modelo Base (Gemma 4):</span>
              <span className={status?.model_downloaded ? "text-green-600 font-medium" : "text-yellow-600 font-medium"}>
                {status?.model_downloaded ? "Listo para usar" : "Pendiente de descarga"}
              </span>
            </li>
          )}
        </ul>
      </div>

      {/* Mensajes de Feedback */}
      {error && <div className="p-3 bg-red-100 text-red-700 rounded-lg text-sm">{error}</div>}
      {message && <div className="p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">{message}</div>}

      {/* Controles */}
      <div className="space-y-3 pt-2">
        {!status?.installed && (
          <button
            onClick={handleInstall}
            disabled={installing}
            className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
          >
            {installing ? '⏳ Instalando en segundo plano...' : '⬇️ Instalar Motor Local (Ollama)'}
          </button>
        )}

        {status?.installed && !status?.model_downloaded && (
          <button
            onClick={handlePull}
            disabled={pulling || installing}
            className="w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
          >
            {pulling ? '⏳ Descargando Modelo (puede tardar bastante)...' : '🧠 Descargar Modelo Gemma 4'}
          </button>
        )}

        {isReady && standalone && (
          <button
            onClick={onClose}
            className="w-full py-3 px-4 bg-green-600 hover:bg-green-700 text-white rounded-xl font-medium transition-colors"
          >
            Continuar a la App
          </button>
        )}
      </div>
      
      {standalone && onClose && !isReady && (
         <button onClick={onClose} className="w-full text-center text-sm text-gray-500 mt-4 hover:underline">
           Omitir por ahora (Usar IA en la Nube)
         </button>
      )}
    </div>
  );

  return content;
};
