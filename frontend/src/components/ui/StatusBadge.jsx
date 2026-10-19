/**
 * StatusBadge – colored pill for transaction/anomaly/match statuses.
 *
 * @param {string} status  – e.g. 'Success', 'Pending', 'Failed', 'Matched', 'Mismatch', 'Missing Settlement', 'Amount Mismatch', 'Missing Bank Transaction', 'High', 'Medium', 'Low'
 * @param {string} [label] – custom label (defaults to status)
 */
export default function StatusBadge({ status, label }) {
  const raw = status != null ? String(status).trim() : '';
  const s = raw.toLowerCase();

  const styles = {
    // Positive / Matched / Healthy
    success:                    'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    completed:                  'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    matched:                    'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    settled:                    'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    resolved:                   'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    normal:                     'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    credit:                     'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    healthy:                    'bg-emerald-50 text-emerald-700 ring-emerald-600/20',

    // Warning / Pending / Missing
    pending:                    'bg-amber-50 text-amber-700 ring-amber-600/20',
    processing:                 'bg-amber-50 text-amber-700 ring-amber-600/20',
    open:                       'bg-amber-50 text-amber-700 ring-amber-600/20',
    medium:                     'bg-amber-50 text-amber-700 ring-amber-600/20',
    'missing settlement':       'bg-amber-50 text-amber-800 ring-amber-600/25',
    'missing bank transaction': 'bg-amber-50 text-amber-800 ring-amber-600/25',
    'unmatched bank transaction': 'bg-amber-50 text-amber-800 ring-amber-600/25',
    missing:                    'bg-amber-50 text-amber-700 ring-amber-600/20',

    // Danger / Mismatch / High Severity / Failed
    failed:                     'bg-rose-50 text-rose-700 ring-rose-600/20',
    unmatched:                  'bg-rose-50 text-rose-700 ring-rose-600/20',
    mismatch:                   'bg-rose-50 text-rose-700 ring-rose-600/20',
    'amount mismatch':          'bg-rose-50 text-rose-700 ring-rose-600/20',
    error:                      'bg-rose-50 text-rose-700 ring-rose-600/20',
    high:                       'bg-rose-50 text-rose-700 ring-rose-600/20',
    critical:                   'bg-rose-100 text-rose-800 ring-rose-600/30',

    // Neutral / Informational
    refunded:                   'bg-purple-50 text-purple-700 ring-purple-600/20',
    low:                        'bg-slate-100 text-slate-600 ring-slate-500/20',
    info:                       'bg-sky-50 text-sky-700 ring-sky-600/20',
  };

  const dotColors = {
    success: 'bg-emerald-500',
    completed: 'bg-emerald-500',
    matched: 'bg-emerald-500',
    settled: 'bg-emerald-500',
    resolved: 'bg-emerald-500',
    normal: 'bg-emerald-500',
    credit: 'bg-emerald-500',
    healthy: 'bg-emerald-500',

    pending: 'bg-amber-500',
    processing: 'bg-amber-500',
    open: 'bg-amber-500',
    medium: 'bg-amber-500',
    'missing settlement': 'bg-amber-500',
    'missing bank transaction': 'bg-amber-500',
    'unmatched bank transaction': 'bg-amber-500',
    missing: 'bg-amber-500',

    failed: 'bg-rose-500',
    unmatched: 'bg-rose-500',
    mismatch: 'bg-rose-500',
    'amount mismatch': 'bg-rose-500',
    error: 'bg-rose-500',
    high: 'bg-rose-500',
    critical: 'bg-rose-600',

    refunded: 'bg-purple-500',
    low: 'bg-slate-400',
    info: 'bg-sky-500',
  };

  const cls = styles[s] ?? 'bg-slate-100 text-slate-600 ring-slate-500/20';
  const dot = dotColors[s] ?? 'bg-slate-400';
  const text = label ?? (raw ? raw.charAt(0).toUpperCase() + raw.slice(1) : '—');

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset whitespace-nowrap ${cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
      {text}
    </span>
  );
}
