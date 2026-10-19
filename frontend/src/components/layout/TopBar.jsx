import { Link } from 'react-router-dom';
import { Sparkles, ShieldCheck } from 'lucide-react';
import { useHealth } from '../../hooks/useApi';

export default function TopBar({ title, subtitle }) {
  const { status } = useHealth(30_000);

  const now = new Date().toLocaleDateString('en-IN', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <header className="flex-shrink-0 flex items-center justify-between px-6 py-3.5 bg-white/90 backdrop-blur-md border-b border-slate-200/75 z-10">
      <div className="min-w-0">
        <div className="flex items-center gap-2.5">
          <h1 className="text-lg font-bold text-slate-900 leading-tight truncate">{title}</h1>
          <span className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-surface-100 text-slate-600">
            {now}
          </span>
        </div>
        {subtitle && (
          <p className="text-xs text-slate-500 mt-0.5 truncate hidden sm:block">{subtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        <Link
          to="/ai-investigator"
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200/60 transition-colors"
        >
          <Sparkles size={13} className="text-emerald-600" />
          AI status (not connected)
        </Link>

        <Link
          to="/settings"
          className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-surface-100 hover:bg-surface-200/70 text-xs font-medium text-slate-700 transition-colors"
          title="Backend connection & settings"
        >
          <span
            className={`w-2 h-2 rounded-full ${
              status === 'online'
                ? 'bg-emerald-500'
                : status === 'offline'
                ? 'bg-rose-500'
                : 'bg-amber-500 animate-pulse'
            }`}
          />
          <ShieldCheck size={14} className="text-navy-800" />
          <span className="hidden md:inline">Controller</span>
        </Link>
      </div>
    </header>
  );
}
