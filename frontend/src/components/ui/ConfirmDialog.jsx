import { useEffect, useRef } from 'react';
import { X, AlertTriangle } from 'lucide-react';

/**
 * ConfirmDialog – modal confirmation for expensive/destructive actions.
 *
 * @param {boolean}  open
 * @param {Function} onConfirm
 * @param {Function} onCancel
 * @param {string}   title
 * @param {string}   description
 * @param {string}   confirmLabel
 * @param {boolean}  loading
 * @param {'danger'|'warning'|'info'} variant
 */
export default function ConfirmDialog({
  open,
  onConfirm,
  onCancel,
  title = 'Are you sure?',
  description = 'This action cannot be undone.',
  confirmLabel = 'Confirm',
  loading = false,
  variant = 'warning',
}) {
  const dialogRef = useRef(null);

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape' && open) onCancel(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  // Focus trap
  useEffect(() => {
    if (open) dialogRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const iconColors = {
    danger:  'bg-danger-50 text-danger-500',
    warning: 'bg-warning-50 text-warning-500',
    info:    'bg-accent-50 text-accent-500',
  };

  const btnColors = {
    danger:  'btn-danger',
    warning: 'btn bg-warning-500 text-white hover:bg-warning-600',
    info:    'btn-primary',
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      aria-modal="true"
      role="dialog"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 animate-fadeIn outline-none"
      >
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 transition-colors"
        >
          <X size={18} />
        </button>

        <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${iconColors[variant]}`}>
          <AlertTriangle size={22} />
        </div>

        <h2 className="text-lg font-bold text-slate-900 mb-2">{title}</h2>
        <p className="text-sm text-slate-500 mb-6 leading-relaxed">{description}</p>

        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} disabled={loading} className="btn-secondary">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`${btnColors[variant]} min-w-[110px] justify-center`}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Running…
              </span>
            ) : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
