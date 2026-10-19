import { useMemo, useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import {
  TrendingUp, Calendar, DollarSign, RefreshCw, Info, Layers, PlayCircle,
} from 'lucide-react';
import { getCashFlowForecast, runCashFlowForecast } from '../services/api';
import { useFetch } from '../hooks/useApi';
import KPICard from '../components/ui/KPICard';
import ErrorState from '../components/ui/ErrorState';
import { PageLoader } from '../components/ui/LoadingStates';
import { formatCompactCurrency, formatCurrency } from '../utils/format';

function formatForecastDate(value, options) {
  if (!value) return '—';
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const date = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString('en-IN', options);
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-navy-900 text-white border border-slate-700 shadow-card-hover rounded-xl px-3.5 py-2.5 text-xs">
      <p className="font-semibold text-slate-300 mb-1.5">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center justify-between gap-4 py-0.5">
          <span className="text-slate-300">{p.name}:</span>
          <span className="font-semibold text-emerald-400 tabular-nums">
            {formatCurrency(p.value)}
          </span>
        </p>
      ))}
    </div>
  );
}

export default function CashFlow() {
  const { data, loading, error, refetch } = useFetch(getCashFlowForecast);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState('');

  async function runForecast() {
    setRunning(true);
    setRunError('');
    try { await runCashFlowForecast(); await refetch(); }
    catch (err) { setRunError(err.message || 'Forecast failed.'); }
    finally { setRunning(false); }
  }

  const forecastData = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.results)) return data.results;
    if (Array.isArray(data.forecast)) return data.forecast;
    if (Array.isArray(data.data)) return data.data;
    return [];
  }, [data]);
  const hasRun = Boolean(data?.run_id);

  // Normalize data keys for Recharts and table
  const chartData = useMemo(() => {
    let runningTotal = 0;
    return forecastData.map((d, idx) => {
      const rawDate = d.date ?? d.period ?? d.timestamp;
      const inflow =
        parseFloat(
          d.predicted_cash_inflow ??
          d.forecasted_amount ??
          d.predicted ??
          d.forecast ??
          0
        ) || 0;
      runningTotal = Math.round((runningTotal + inflow) * 100) / 100;
      return {
        dayNumber: idx + 1,
        rawDate,
        date: formatForecastDate(rawDate, { year: 'numeric', month: 'short', day: 'numeric' }),
        shortDate: formatForecastDate(rawDate, { month: 'short', day: 'numeric' }),
        predictedInflow: inflow,
        cumulativeInflow: runningTotal,
      };
    });
  }, [forecastData]);

  const summary = useMemo(() => {
    if (!chartData.length) {
      return { totalProjected: 0, avgDaily: 0, days: 0, dateRange: '—' };
    }
    const totalProjected = chartData.reduce((s, d) => s + d.predictedInflow, 0);
    const avgDaily = totalProjected / chartData.length;
    const firstDate = chartData[0]?.shortDate;
    const lastDate = chartData[chartData.length - 1]?.shortDate;
    return {
      totalProjected,
      avgDaily,
      days: chartData.length,
      dateRange: firstDate && lastDate ? `${firstDate} – ${lastDate}` : '7-day horizon',
    };
  }, [chartData]);
  const hasForecast = chartData.length > 0;

  if (loading) return <PageLoader />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Cash Flow Forecast</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            7-day projected net settlement cash inflows modeled from historical cleared payments
          </p>
        </div>
        <div className="flex gap-2"><button onClick={refetch} className="btn-secondary"><RefreshCw size={14} />Refresh</button><button onClick={runForecast} disabled={running} className="btn-primary"><PlayCircle size={14} />{running ? 'Forecasting…' : 'Run forecast'}</button></div>
      </div>
      {runError && <p role="alert" className="text-sm text-rose-700">{runError}</p>}

      {/* Methodology Note */}
      <div className="card px-4 py-3 bg-surface-50/70 flex items-center gap-3 text-xs text-slate-600">
        <Info size={15} className="text-accent-600 flex-shrink-0" />
        <span>
          <strong>Forecast Methodology:</strong> Calculated by aggregating historical daily net settlement amounts (Gross − Refunds − Fees − Tax) from successful payments and projecting the daily mean across the upcoming {summary.days || 7}-day horizon.
        </span>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KPICard
          label="7-Day Projected Inflow"
          value={hasForecast ? formatCurrency(summary.totalProjected) : '—'}
          icon={<DollarSign size={18} />}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
          trend="Cumulative"
          trendDir="up"
          sub={hasForecast ? `Expected across ${summary.days} forecast days` : 'No forecast values available'}
        />
        <KPICard
          label="Daily Average Inflow"
          value={hasForecast ? formatCurrency(summary.avgDaily) : '—'}
          icon={<TrendingUp size={18} />}
          iconBg="bg-slate-100"
          iconColor="text-navy-800"
          sub="Historical daily net settlement mean"
        />
        <KPICard
          label="Forecast Horizon"
          value={hasForecast ? `${summary.days} Days` : '—'}
          icon={<Calendar size={18} />}
          iconBg="bg-sky-50"
          iconColor="text-sky-600"
          sub={summary.dateRange}
        />
      </div>

      {chartData.length === 0 ? (
        <div className="card p-12 text-center">
          <TrendingUp size={32} className="text-slate-300 mx-auto mb-3" />
          <p className="text-slate-700 font-semibold">No cash flow forecast data available</p>
          <p className="text-slate-400 text-sm mt-1">
            {hasRun
              ? 'No forecast rows were produced. Import successful payments with payment dates and linked settlements, then run the forecast again.'
              : 'Import successful payments with payment dates and linked settlements, then run the forecast here.'}
          </p>
        </div>
      ) : (
        <>
          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Daily Predicted Inflow Bar Chart */}
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold text-slate-800">Daily Predicted Cash Inflow</h3>
                  <p className="text-xs text-slate-500">Expected daily net settlement credit</p>
                </div>
                <span className="text-xs font-semibold text-slate-600 bg-surface-100 px-2.5 py-1 rounded-full tabular-nums">
                  {formatCurrency(summary.avgDaily)} / day
                </span>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--mocha-line))" vertical={false} />
                  <XAxis
                    dataKey="shortDate"
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
                  <Tooltip content={<ChartTooltip />} />
                  <ReferenceLine
                    y={summary.avgDaily}
                    stroke="rgb(var(--mocha-success))"
                    strokeDasharray="4 4"
                  />
                  <Bar
                    dataKey="predictedInflow"
                    name="Predicted Daily Inflow"
                    fill="rgb(var(--mocha-success))"
                    radius={[6, 6, 0, 0]}
                    barSize={32}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Cumulative 7-Day Cash Trajectory */}
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold text-slate-800">Cumulative Cash Inflow Trajectory</h3>
                  <p className="text-xs text-slate-500">Running liquidity accumulation over forecast window</p>
                </div>
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full tabular-nums">
                  <Layers size={12} />
                  {formatCurrency(summary.totalProjected)}
                </span>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gradCumulative" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="rgb(var(--mocha-primary))" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="rgb(var(--mocha-primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--mocha-line))" vertical={false} />
                  <XAxis
                    dataKey="shortDate"
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
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="cumulativeInflow"
                    name="Cumulative Inflow"
                    stroke="rgb(var(--mocha-primary))"
                    strokeWidth={2.5}
                    fill="url(#gradCumulative)"
                    dot={{ r: 3.5, fill: 'rgb(var(--mocha-primary))' }}
                    activeDot={{ r: 5 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Forecast Schedule Table */}
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-800">Daily Forecast Schedule</h3>
                <p className="text-xs text-slate-400">Day-by-day projected settlement inflows</p>
              </div>
              <span className="text-xs font-medium text-slate-500 bg-surface-100 px-2.5 py-1 rounded-full">
                {chartData.length} forecast periods
              </span>
            </div>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Horizon Day</th>
                    <th>Forecast Date</th>
                    <th className="text-right">Predicted Daily Inflow</th>
                    <th className="text-right">Cumulative Projected Inflow</th>
                    <th className="text-right">% of 7-Day Total</th>
                  </tr>
                </thead>
                <tbody>
                  {chartData.map((row) => {
                    const share =
                      summary.totalProjected > 0
                        ? ((row.predictedInflow / summary.totalProjected) * 100).toFixed(1)
                        : '0.0';
                    return (
                      <tr key={row.rawDate ?? row.dayNumber}>
                        <td>
                          <span className="font-mono text-xs font-semibold text-slate-600 bg-surface-100 px-2 py-0.5 rounded">
                            Day +{row.dayNumber}
                          </span>
                        </td>
                        <td className="font-medium text-slate-800">{row.date}</td>
                        <td className="text-right font-semibold text-emerald-700 tabular-nums">
                          {formatCurrency(row.predictedInflow)}
                        </td>
                        <td className="text-right font-semibold text-slate-800 tabular-nums">
                          {formatCurrency(row.cumulativeInflow)}
                        </td>
                        <td className="text-right text-xs text-slate-500 tabular-nums">
                          {share}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
