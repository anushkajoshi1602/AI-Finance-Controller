/**
 * KPICard – displays a single financial metric with icon, value, label, and optional trend/subtitle.
 */
export default function KPICard({
  label,
  value,
  icon,
  trend,
  trendDir = 'neutral',
  sub,
  iconBg = 'bg-accent-50',
  iconColor = 'text-accent-600',
  loading = false,
}) {
  const trendColors = {
    up:      'text-emerald-700 bg-emerald-50 ring-1 ring-inset ring-emerald-600/20',
    down:    'text-rose-700 bg-rose-50 ring-1 ring-inset ring-rose-600/20',
    warning: 'text-amber-700 bg-amber-50 ring-1 ring-inset ring-amber-600/20',
    neutral: 'text-slate-600 bg-slate-100 ring-1 ring-inset ring-slate-500/15',
  };

  if (loading) {
    return (
      <div className="card p-5 animate-fadeIn">
        <div className="flex items-start justify-between mb-3.5">
          <div className="skeleton w-10 h-10 rounded-xl" />
          <div className="skeleton w-14 h-5 rounded-full" />
        </div>
        <div className="skeleton w-28 h-7 rounded-lg mb-2" />
        <div className="skeleton w-20 h-4 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="card p-5 hover:shadow-card-hover transition-all duration-200 animate-fadeIn flex flex-col justify-between">
      <div>
        <div className="flex items-start justify-between gap-2 mb-3.5">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${iconBg}`}>
            <span className={iconColor}>{icon}</span>
          </div>
          {trend && (
            <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full tabular-nums ${trendColors[trendDir] ?? trendColors.neutral}`}>
              {trend}
            </span>
          )}
        </div>
        <p className="text-2xl font-bold text-slate-900 tracking-tight leading-none mb-1.5 tabular-nums">
          {value ?? '—'}
        </p>
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      </div>
      {sub && (
        <p className="text-xs text-slate-500 mt-2.5 pt-2.5 border-t border-slate-100">
          {sub}
        </p>
      )}
    </div>
  );
}
