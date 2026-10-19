import { useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  CreditCard, CheckCircle2, RotateCcw, Building2,
  AlertTriangle, PlayCircle, TrendingUp, DollarSign,
  ArrowUpRight, ShieldAlert, Sparkles, RefreshCw,
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import {
  getDashboard,
  getPayments,
  getSettlements,
  getAnomalies,
  runFullAnalysis,
} from '../services/api';
import { useFetch } from '../hooks/useApi';
import KPICard from '../components/ui/KPICard';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import StatusBadge from '../components/ui/StatusBadge';
import ErrorState from '../components/ui/ErrorState';
import { formatCompactCurrency, formatCurrency, formatDateTime, formatNumber, safe } from '../utils/format';

// Custom Recharts tooltip
function ChartTooltip({ active, payload, label, currency = false }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-navy-900 text-white border border-slate-700 shadow-card-hover rounded-xl px-3.5 py-2.5 text-xs">
      <p className="font-semibold text-slate-300 mb-1.5">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center justify-between gap-4 py-0.5">
          <span className="text-slate-300">{p.name}:</span>
          <span className="font-semibold text-emerald-400 tabular-nums">
            {currency ? formatCurrency(p.value) : formatNumber(p.value)}
          </span>
        </p>
      ))}
    </div>
  );
}

const METHOD_COLORS = [
  'rgb(var(--mocha-success))',
  'rgb(var(--mocha-primary))',
  'rgb(var(--mocha-error))',
  'rgb(var(--mocha-muted))',
];

export default function Dashboard() {
  const fetchDashboardBundle = useCallback(async () => {
    const [summary, payments, settlements, anomalyResponse] = await Promise.all([
      getDashboard(),
      getPayments(),
      getSettlements(),
      getAnomalies(),
    ]);
    return {
      summary: summary || {},
      payments: Array.isArray(payments) ? payments : [],
      settlements: Array.isArray(settlements) ? settlements : [],
      anomalies: Array.isArray(anomalyResponse?.results) ? anomalyResponse.results : [],
      anomalyRunId: anomalyResponse?.run_id || null,
    };
  }, []);

  const { data, loading, error, refetch } = useFetch(fetchDashboardBundle);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [analysisMsg, setAnalysisMsg] = useState(null);

  const handleRunAnalysis = useCallback(async () => {
    setAnalysisRunning(true);
    try {
      const result = await runFullAnalysis();
      setAnalysisMsg({
        type: 'success',
        text: result?.message || 'Full financial analysis completed and datasets updated.',
      });
      refetch();
    } catch (err) {
      setAnalysisMsg({ type: 'error', text: err.message });
    } finally {
      setAnalysisRunning(false);
      setConfirmOpen(false);
    }
  }, [refetch]);

  const summary = useMemo(() => data?.summary || {}, [data]);
  const payments = useMemo(() => data?.payments || [], [data]);
  const settlements = useMemo(() => data?.settlements || [], [data]);
  const anomalies = useMemo(() => data?.anomalies || [], [data]);

  // Calculate derived metrics grounded in real API data
  const metrics = useMemo(() => {
    const totalCount = summary.total_payments ?? payments.length;
    const successCount =
      summary.successful_payments ??
      payments.filter((p) => (p.status ?? '').toLowerCase() === 'success').length;
    const failedCount = payments.filter((p) => (p.status ?? '').toLowerCase() === 'failed').length;
    const pendingCount = payments.filter((p) => (p.status ?? '').toLowerCase() === 'pending').length;

    const successRate = totalCount > 0 ? ((successCount / totalCount) * 100).toFixed(1) : null;

    const totalPaymentVolume =
      summary.total_payment_amount ??
      payments
        .filter((p) => (p.status ?? '').toLowerCase() === 'success')
        .reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);

    const totalSettlements =
      summary.total_settlements ??
      settlements.reduce((s, st) => s + (parseFloat(st.net_amount) || 0), 0);

    const totalRefunds = summary.total_refunds ?? 0;
    const totalAnomalies = summary.total_anomalies ?? anomalies.length;

    const totalFeesAndTax = settlements.reduce(
      (s, st) => s + (parseFloat(st.fee) || 0) + (parseFloat(st.tax) || 0),
      0
    );

    return {
      totalCount,
      successCount,
      failedCount,
      pendingCount,
      successRate,
      totalPaymentVolume,
      totalSettlements,
      totalRefunds,
      totalAnomalies,
      totalFeesAndTax,
      settlementCount: settlements.length,
    };
  }, [summary, payments, settlements, anomalies]);

  // Aggregate monthly payment volume from real payment.csv records
  const monthlyTrend = useMemo(() => {
    if (!payments.length) return [];
    const byMonth = new Map();

    payments.forEach((p) => {
      if (!p.payment_date) return;
      const d = new Date(p.payment_date);
      if (isNaN(d.getTime())) return;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      const label = d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
      const prev = byMonth.get(key) || { key, month: label, volume: 0, count: 0 };
      const amt = parseFloat(p.amount) || 0;
      if ((p.status ?? '').toLowerCase() === 'success') {
        prev.volume = Math.round((prev.volume + amt) * 100) / 100;
      }
      prev.count += 1;
      byMonth.set(key, prev);
    });

    return Array.from(byMonth.values()).sort((a, b) => a.key.localeCompare(b.key));
  }, [payments]);

  // Aggregate payment method distribution from real payment.csv records
  const methodBreakdown = useMemo(() => {
    if (!payments.length) return [];
    const map = new Map();
    payments.forEach((p) => {
      const method = p.payment_method || 'Other';
      const prev = map.get(method) || { method, volume: 0, count: 0 };
      const amt = parseFloat(p.amount) || 0;
      prev.volume = Math.round((prev.volume + amt) * 100) / 100;
      prev.count += 1;
      map.set(method, prev);
    });
    return Array.from(map.values()).sort((a, b) => b.volume - a.volume);
  }, [payments]);

  // Recent payments sorted by actual payment_date descending
  const recentPayments = useMemo(() => {
    if (!payments.length) return [];
    return [...payments]
      .sort((a, b) => String(b.payment_date ?? '').localeCompare(String(a.payment_date ?? '')))
      .slice(0, 7);
  }, [payments]);

  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const kpis = [
    {
      label: 'Successful Volume',
      value: formatCurrency(metrics.totalPaymentVolume),
      icon: <DollarSign size={18} />,
      iconBg: 'bg-emerald-50',
      iconColor: 'text-emerald-600',
      trend: metrics.successRate === null ? 'No payments' : `${metrics.successRate}% rate`,
      trendDir: metrics.successRate === null ? 'neutral' : 'up',
      sub: metrics.totalCount > 0
        ? `${formatNumber(metrics.successCount)} of ${formatNumber(metrics.totalCount)} payments succeeded`
        : 'Import payment records to calculate success rate',
    },
    {
      label: 'Total Transactions',
      value: formatNumber(metrics.totalCount),
      icon: <CreditCard size={18} />,
      iconBg: 'bg-slate-100',
      iconColor: 'text-navy-800',
      sub: `${formatNumber(metrics.failedCount)} failed · ${formatNumber(metrics.pendingCount)} pending`,
    },
    {
      label: 'Net Settlements',
      value: formatCurrency(metrics.totalSettlements),
      icon: <Building2 size={18} />,
      iconBg: 'bg-sky-50',
      iconColor: 'text-sky-600',
      sub: `${formatNumber(metrics.settlementCount)} settled (${formatCurrency(metrics.totalFeesAndTax)} fees/tax)`,
    },
    {
      label: 'Total Refunds',
      value: formatCurrency(metrics.totalRefunds),
      icon: <RotateCcw size={18} />,
      iconBg: 'bg-purple-50',
      iconColor: 'text-purple-600',
      sub: 'Deducted prior to net settlement',
    },
    {
      label: 'Latest Run Alerts',
      value: data?.anomalyRunId ? formatNumber(metrics.totalAnomalies) : '—',
      icon: <AlertTriangle size={18} />,
      iconBg: metrics.totalAnomalies > 0 ? 'bg-rose-50' : 'bg-emerald-50',
      iconColor: metrics.totalAnomalies > 0 ? 'text-rose-600' : 'text-emerald-600',
      trend: !data?.anomalyRunId ? 'Not run' : metrics.totalAnomalies > 0 ? 'Action needed' : 'No alerts',
      trendDir: !data?.anomalyRunId ? 'warning' : metrics.totalAnomalies > 0 ? 'down' : 'up',
      sub: data?.anomalyRunId ? 'Results from the latest anomaly run' : 'Run analysis to check for anomalies',
    },
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Executive Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Financial Control Center</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Business-scoped payment, settlement, bank reconciliation, and anomaly results
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={refetch}
            disabled={loading}
            className="btn-secondary"
            title="Refresh live metrics"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={() => setConfirmOpen(true)}
            className="btn-primary"
          >
            <PlayCircle size={16} className="text-emerald-400" />
            Run Core Analysis
          </button>
        </div>
      </div>

      {/* Analysis status notification */}
      {analysisMsg && (
        <div
          className={`flex items-center justify-between px-4 py-3 rounded-xl text-sm font-medium animate-fadeIn ${
            analysisMsg.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          <span>{analysisMsg.text}</span>
          <button
            onClick={() => setAnalysisMsg(null)}
            className="ml-3 opacity-60 hover:opacity-100 text-lg leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {kpis.map((kpi) => (
          <KPICard key={kpi.label} {...kpi} loading={loading} />
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Monthly Cleared Volume Trend */}
        <div className="card p-5 lg:col-span-2 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Monthly Successful Payment Volume</h3>
              <p className="text-xs text-slate-500">Cleared gross transaction value aggregated by month</p>
            </div>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full">
              {formatCurrency(metrics.totalPaymentVolume)} total
            </span>
          </div>
          {loading ? (
            <div className="skeleton h-56 rounded-xl" />
          ) : monthlyTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={230}>
              <AreaChart data={monthlyTrend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradEmerald" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="rgb(var(--mocha-success))" stopOpacity={0.22} />
                    <stop offset="95%" stopColor="rgb(var(--mocha-success))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--mocha-line))" vertical={false} />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: 'rgb(var(--mocha-muted))' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: 'rgb(var(--mocha-muted))' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => formatCompactCurrency(v)}
                />
                <Tooltip content={<ChartTooltip currency />} />
                <Area
                  type="monotone"
                  dataKey="volume"
                  name="Cleared Volume"
                  stroke="rgb(var(--mocha-success))"
                  strokeWidth={2.5}
                  fill="url(#gradEmerald)"
                  dot={{ r: 3, fill: 'rgb(var(--mocha-success))', strokeWidth: 0 }}
                  activeDot={{ r: 5, fill: 'rgb(var(--mocha-success))' }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-56 flex items-center justify-center text-slate-400 text-sm">
              No payment volume data available
            </div>
          )}
        </div>

        {/* Payment Method Breakdown */}
        <div className="card p-5 flex flex-col justify-between">
          <div className="mb-4">
            <h3 className="text-sm font-bold text-slate-800">Volume by Payment Method</h3>
            <p className="text-xs text-slate-500">Distribution across UPI, Netbanking & Card</p>
          </div>
          {loading ? (
            <div className="skeleton h-56 rounded-xl" />
          ) : methodBreakdown.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={165}>
                <BarChart data={methodBreakdown} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--mocha-line))" vertical={false} />
                  <XAxis
                    dataKey="method"
                    tick={{ fontSize: 11, fill: 'rgb(var(--mocha-muted))', fontWeight: 500 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: 'rgb(var(--mocha-muted))' }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => formatCompactCurrency(v)}
                  />
                  <Tooltip content={<ChartTooltip currency />} />
                  <Bar dataKey="volume" name="Gross Volume" radius={[6, 6, 0, 0]} barSize={38}>
                    {methodBreakdown.map((entry, idx) => (
                      <Cell key={entry.method} fill={METHOD_COLORS[idx % METHOD_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 pt-3 border-t border-slate-100 space-y-1.5">
                {methodBreakdown.map((m, idx) => (
                  <div key={m.method} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                        style={{ backgroundColor: METHOD_COLORS[idx % METHOD_COLORS.length] }}
                      />
                      <span className="font-medium text-slate-700">{m.method}</span>
                    </div>
                    <span className="text-slate-500 tabular-nums">
                      {formatCurrency(m.volume)} · {m.count} txns
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-56 flex items-center justify-center text-slate-400 text-sm">
              No method breakdown available
            </div>
          )}
        </div>
      </div>

      {/* Bottom Row: Latest Run Anomalies + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Active Anomalies Watchlist */}
        <div className="card overflow-hidden lg:col-span-2 flex flex-col">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert size={16} className="text-rose-600" />
              <h3 className="text-sm font-bold text-slate-800">Latest Run Anomalies</h3>
            </div>
            <Link
              to="/ai-investigator"
              className="inline-flex items-center gap-1 text-xs font-semibold text-accent-600 hover:text-accent-700"
            >
              <Sparkles size={13} />
              AI status
              <ArrowUpRight size={13} />
            </Link>
          </div>

          {loading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="skeleton h-14 rounded-xl" />
              ))}
            </div>
          ) : anomalies.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
              <CheckCircle2 size={28} className={`mb-2 ${data?.anomalyRunId ? 'text-emerald-500' : 'text-slate-300'}`} />
              <p className="text-sm font-semibold text-slate-700">{data?.anomalyRunId ? 'No Alerts in Latest Run' : 'Anomaly Detection Not Run'}</p>
              <p className="text-xs text-slate-400 mt-1">
                {data?.anomalyRunId ? 'The latest anomaly run found no reconciliation exceptions.' : 'Run core analysis to check payment and bank reconciliation results.'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 flex-1">
              {anomalies.map((a, i) => {
                const diff = parseFloat(a.amount_difference);
                const hasDiff = !isNaN(diff);
                return (
                  <div
                    key={`${a.transaction_id}-${i}`}
                    className="px-5 py-3.5 hover:bg-surface-50 transition-colors flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-slate-800 bg-surface-100 px-2 py-0.5 rounded">
                          {safe(a.transaction_id)}
                        </span>
                        <span className="text-xs font-semibold text-slate-700 truncate">
                          {safe(a.anomaly_type)}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">{safe(a.source)}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className="text-xs font-bold text-rose-600 tabular-nums">
                        {hasDiff ? `${formatCurrency(diff)} diff` : 'Missing record'}
                      </span>
                      <StatusBadge status={a.severity} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent Payment Transactions */}
        <div className="card overflow-hidden lg:col-span-3">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Recent Payment Activity</h3>
              <p className="text-xs text-slate-400">Latest customer transactions recorded in the ledger</p>
            </div>
            <Link
              to="/payments"
              className="inline-flex items-center gap-1 text-xs font-semibold text-accent-600 hover:text-accent-700"
            >
              View all {formatNumber(payments.length)}
              <ArrowUpRight size={13} />
            </Link>
          </div>

          {loading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton h-11 rounded-xl" />
              ))}
            </div>
          ) : recentPayments.length === 0 ? (
            <div className="py-12 text-center text-slate-400 text-sm">No recent transactions</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {recentPayments.map((tx, i) => (
                <div
                  key={tx.payment_id ?? i}
                  className="flex items-center justify-between px-5 py-3 hover:bg-surface-50 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-surface-100 flex items-center justify-center flex-shrink-0">
                      <CreditCard size={14} className="text-navy-800" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-slate-800">
                          {safe(tx.payment_id)}
                        </span>
                        <span className="text-xs text-slate-500 bg-surface-100 px-2 py-0.5 rounded-md">
                          {safe(tx.payment_method)}
                        </span>
                        {tx.customer_id && (
                          <span className="text-xs text-slate-400 hidden sm:inline">
                            Customer #{tx.customer_id}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {formatDateTime(tx.payment_date)}
                        {tx.failure_reason ? ` · ${tx.failure_reason}` : ''}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-sm font-semibold text-slate-800 tabular-nums">
                      {formatCurrency(tx.amount)}
                    </span>
                    <StatusBadge status={tx.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Confirm dialog */}
      <ConfirmDialog
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleRunAnalysis}
        loading={analysisRunning}
        title="Run Business Financial Analysis?"
        description="This runs payment reconciliation, bank settlement matching, anomaly detection, and the seven-day cash-flow forecast for the selected business. AI investigation is not included."
        confirmLabel="Run Core Analysis"
        variant="warning"
      />
    </div>
  );
}
