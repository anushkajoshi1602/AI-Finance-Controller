import { Loader2 } from 'lucide-react';

export function LoadingSpinner({ size = 24, className = '' }) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <Loader2 size={size} className="animate-spin text-accent-500" />
    </div>
  );
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center py-24">
      <div className="text-center">
        <Loader2 size={32} className="animate-spin text-accent-500 mx-auto mb-3" />
        <p className="text-sm text-slate-400">Loading…</p>
      </div>
    </div>
  );
}

export function SkeletonCard({ className = '' }) {
  return (
    <div className={`card p-5 ${className}`}>
      <div className="skeleton w-10 h-10 rounded-xl mb-3" />
      <div className="skeleton w-28 h-7 rounded-lg mb-2" />
      <div className="skeleton w-20 h-4 rounded-lg" />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }) {
  return (
    <div className="card overflow-hidden">
      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              {Array.from({ length: cols }).map((_, i) => (
                <th key={i}><div className="skeleton h-3 w-20 rounded" /></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rows }).map((_, i) => (
              <tr key={i}>
                {Array.from({ length: cols }).map((_, j) => (
                  <td key={j}><div className="skeleton h-4 rounded" /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
