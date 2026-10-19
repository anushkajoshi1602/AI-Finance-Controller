import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';

/**
 * @param {'online'|'offline'|'checking'} status
 * @param {Date|null} lastChecked
 * @param {boolean} compact – shows dark-sidebar friendly pill
 */
export default function ConnectionBadge({ status, lastChecked, compact = false }) {
  const configs = {
    online: {
      dot: 'bg-emerald-400',
      text: compact ? 'text-emerald-300' : 'text-emerald-700',
      bg: compact ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-emerald-50/70 border-emerald-200',
      label: 'API Connected',
      icon: <CheckCircle2 size={13} className="text-emerald-500" />,
    },
    offline: {
      dot: 'bg-rose-400',
      text: compact ? 'text-rose-300' : 'text-rose-700',
      bg: compact ? 'bg-rose-500/10 border-rose-500/20' : 'bg-rose-50/70 border-rose-200',
      label: 'API Offline',
      icon: <XCircle size={13} className="text-rose-500" />,
    },
    checking: {
      dot: 'bg-amber-400 animate-pulse',
      text: compact ? 'text-amber-300' : 'text-amber-700',
      bg: compact ? 'bg-amber-500/10 border-amber-500/20' : 'bg-amber-50/70 border-amber-200',
      label: 'Checking API…',
      icon: <Loader2 size={13} className="text-amber-500 animate-spin" />,
    },
  };

  const cfg = configs[status] ?? configs.checking;

  if (compact) {
    return (
      <div className={`flex items-center justify-between gap-2 px-3 py-2 rounded-xl border ${cfg.bg}`}>
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
          <span className={`text-xs font-medium truncate ${cfg.text}`}>{cfg.label}</span>
        </div>
        {lastChecked && (
          <span className="text-[10px] text-slate-400 tabular-nums flex-shrink-0">
            {lastChecked.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border ${cfg.bg}`}>
      {cfg.icon}
      <span className={`text-xs font-semibold ${cfg.text}`}>{cfg.label}</span>
      {lastChecked && (
        <span className="text-xs text-slate-500 tabular-nums">
          · {lastChecked.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      )}
    </div>
  );
}
