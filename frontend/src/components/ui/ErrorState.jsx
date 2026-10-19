import { AlertTriangle, RefreshCw, ServerCrash } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * ErrorState – humanized error message with troubleshooting tips and retry button.
 */
export default function ErrorState({ message, onRetry, title = 'Unable to load financial data' }) {
  const isConnectionError =
    !message ||
    message.toLowerCase().includes('network') ||
    message.toLowerCase().includes('reach backend') ||
    message.toLowerCase().includes('failed to fetch');

  return (
    <div className="card p-10 max-w-lg mx-auto my-8 text-center animate-fadeIn">
      <div className="w-12 h-12 bg-rose-50 border border-rose-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
        {isConnectionError ? (
          <ServerCrash size={22} className="text-rose-600" />
        ) : (
          <AlertTriangle size={22} className="text-rose-600" />
        )}
      </div>
      <h3 className="text-base font-bold text-slate-800 mb-1.5">{title}</h3>
      <p className="text-sm text-slate-500 leading-relaxed mb-4">
        {message || 'The request could not be completed. Please check your backend server and try again.'}
      </p>

      {isConnectionError && (
        <div className="bg-surface-50 border border-slate-200/80 rounded-xl p-3.5 text-left text-xs text-slate-600 mb-5 space-y-1">
          <p className="font-semibold text-slate-700">Quick verification:</p>
          <p>1. Ensure the FastAPI backend is running at <code className="font-mono text-slate-800 bg-white px-1.5 py-0.5 rounded border">{API_BASE_URL}</code></p>
          <p>2. Verify the CSV datasets exist inside the project <code className="font-mono text-slate-800 bg-white px-1.5 py-0.5 rounded border">data/</code> directory.</p>
        </div>
      )}

      {onRetry && (
        <button onClick={onRetry} className="btn-primary mx-auto">
          <RefreshCw size={14} />
          Retry Connection
        </button>
      )}
    </div>
  );
}
