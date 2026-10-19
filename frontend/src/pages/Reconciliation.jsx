import { useState, useMemo, useCallback } from 'react';
import {
  GitMerge, CheckCircle2, XCircle, AlertTriangle,
  PlayCircle, RefreshCw, Filter, Info,
} from 'lucide-react';
import { getReconciliation, runReconciliation } from '../services/api';
import { useFetch } from '../hooks/useApi';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import KPICard from '../components/ui/KPICard';
import ErrorState from '../components/ui/ErrorState';
import { formatCurrency, formatNumber, safe } from '../utils/format';

const STATUS_FILTERS = ['All', 'Discrepancies Only', 'Matched', 'Mismatch', 'Missing Settlement'];

export default function Reconciliation() {
  const { data, loading, error, refetch } = useFetch(getReconciliation);
  const [statusFilter, setStatusFilter] = useState('All');
  const [running, setRunning] = useState(false);
  const [runMsg, setRunMsg] = useState(null);

  const records = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.results)) return data.results;
    if (Array.isArray(data.records)) return data.records;
    if (Array.isArray(data.reconciliation)) return data.reconciliation;
    return [];
  }, [data]);
  const hasRun = Boolean(data?.run_id);

  const handleRunReconciliation = useCallback(async () => {
    setRunning(true);
    setRunMsg(null);
    try {
      const res = await runReconciliation();
      await refetch();
      setRunMsg({
        type: 'success',
        text: `Reconciliation run completed with ${formatNumber(res?.result_count ?? 0)} results.`,
      });
    } catch (err) {
      setRunMsg({ type: 'error', text: err.message });
    } finally {
      setRunning(false);
    }
  }, [refetch]);

  const summary = useMemo(() => {
    const matched = records.filter((r) => (r.status ?? '').toLowerCase() === 'matched').length;
    const unmatched = records.length - matched;
    const totalDiscrepancy = records.reduce((sum, r) => {
      const diff = parseFloat(r.difference);
      return sum + (isNaN(diff) ? 0 : Math.abs(diff));
    }, 0);
    return { matched, unmatched, total: records.length, totalDiscrepancy };
  }, [records]);

  const filtered = useMemo(() => {
    if (statusFilter === 'All') return records;
    if (statusFilter === 'Discrepancies Only') {
      return records.filter((r) => (r.status ?? '').toLowerCase() !== 'matched');
    }
    return records.filter(
      (r) => (r.status ?? '').toLowerCase() === statusFilter.toLowerCase()
    );
  }, [records, statusFilter]);

  const columns = [
    {
      key: 'payment_id',
      label: 'Payment ID',
      render: (v) => (
        <span className="font-mono text-xs font-semibold text-slate-800 bg-surface-100 px-2 py-0.5 rounded">
          {safe(v)}
        </span>
      ),
    },
    {
      key: 'payment_amount',
      label: 'Payment Amount',
      align: 'right',
      render: (v) => (
        <span className="font-medium text-slate-800 tabular-nums">
          {formatCurrency(v)}
        </span>
      ),
    },
    {
      key: 'refund_amount',
      label: 'Refund Deducted',
      align: 'right',
      render: (v) => {
        const val = parseFloat(v) || 0;
        return val > 0 ? (
          <span className="text-xs font-medium text-purple-700 bg-purple-50 px-2 py-0.5 rounded tabular-nums">
            -{formatCurrency(val)}
          </span>
        ) : (
          <span className="text-slate-400 tabular-nums text-xs">{formatCurrency(0)}</span>
        );
      },
    },
    {
      key: 'expected_settlement',
      label: 'Expected Settlement',
      align: 'right',
      render: (v) => {
        if (String(v).toLowerCase() === 'missing') {
          return (
            <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded">
              Missing
            </span>
          );
        }
        return (
          <span className="font-medium text-slate-700 tabular-nums">
            {formatCurrency(v)}
          </span>
        );
      },
    },
    {
      key: 'actual_settlement',
      label: 'Actual Settlement',
      align: 'right',
      render: (v) => {
        if (String(v).toLowerCase() === 'missing') {
          return (
            <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded">
              Missing
            </span>
          );
        }
        return (
          <span className="font-semibold text-slate-900 tabular-nums">
            {formatCurrency(v)}
          </span>
        );
      },
    },
    {
      key: 'difference',
      label: 'Discrepancy',
      align: 'right',
      render: (v) => {
        if (v === null || v === undefined || String(v).toUpperCase() === 'N/A' || v === '') {
          return <span className="text-xs font-medium text-amber-700">Unsettled</span>;
        }
        const val = parseFloat(v);
        if (isNaN(val)) return <span className="text-slate-400">—</span>;
        const isMismatch = Math.abs(val) >= 0.01;
        return (
          <span
            className={`tabular-nums font-semibold ${
              isMismatch ? 'text-rose-600' : 'text-emerald-600'
            }`}
          >
            {formatCurrency(val)}
          </span>
        );
      },
    },
    {
      key: 'status',
      label: 'Status',
      render: (v) => <StatusBadge status={v} />,
    },
  ];

  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Payment Reconciliation</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Verify expected gateway settlements against actual net payouts for every captured payment
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button onClick={refetch} disabled={loading || running} className="btn-secondary">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={handleRunReconciliation}
            disabled={running}
            className="btn-primary"
          >
            <PlayCircle size={15} className="text-emerald-400" />
            {running ? 'Reconciling…' : 'Run Reconciliation'}
          </button>
        </div>
      </div>

      {/* Run message */}
      {runMsg && (
        <div
          className={`flex items-center justify-between px-4 py-3 rounded-xl text-sm font-medium animate-fadeIn ${
            runMsg.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          <span>{runMsg.text}</span>
          <button
            onClick={() => setRunMsg(null)}
            className="ml-3 opacity-60 hover:opacity-100 text-lg leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Audited"
          value={hasRun ? formatNumber(summary.total) : '—'}
          icon={<GitMerge size={18} />}
          iconBg="bg-slate-100"
          iconColor="text-navy-800"
          sub="Successful payments verified"
          loading={loading}
        />
        <KPICard
          label="Matched"
          value={hasRun ? formatNumber(summary.matched) : '—'}
          icon={<CheckCircle2 size={18} />}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
          sub="Zero settlement variance"
          loading={loading}
        />
        <KPICard
          label="Exceptions Found"
          value={hasRun ? formatNumber(summary.unmatched) : '—'}
          icon={<XCircle size={18} />}
          iconBg="bg-rose-50"
          iconColor="text-rose-600"
          sub="Mismatches or missing settlements"
          loading={loading}
        />
        <KPICard
          label="Known Variance"
          value={hasRun ? formatCurrency(summary.totalDiscrepancy) : '—'}
          icon={<AlertTriangle size={18} />}
          iconBg="bg-amber-50"
          iconColor="text-amber-600"
          sub="Cumulative dollar discrepancy"
          loading={loading}
        />
      </div>

      {/* Filter Bar */}
      <div className="card p-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 px-2">
            <Filter size={13} />
            Status Filter:
          </span>
          <div className="flex flex-wrap items-center gap-1 bg-surface-100 rounded-xl p-1">
            {STATUS_FILTERS.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  statusFilter === s
                    ? 'bg-navy-900 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500 px-2">
          <Info size={13} className="text-accent-600" />
          <span>Expected payout uses payment amount minus refunds, imported fee, and imported tax.</span>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        loading={loading}
        emptyMessage={hasRun ? 'No reconciliation records match the selected filter' : 'No payment reconciliation run yet. Run reconciliation after importing data.'}
        searchPlaceholder="Search payment ID or status…"
        searchFilter={(row, q) =>
          String(row.payment_id ?? '').toLowerCase().includes(q) ||
          String(row.status ?? '').toLowerCase().includes(q)
        }
        caption="Payment-to-Settlement Reconciliation"
      />
    </div>
  );
}
