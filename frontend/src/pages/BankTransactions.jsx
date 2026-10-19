import { useState, useMemo } from 'react';
import {
  Building2, CheckCircle2, XCircle, TrendingDown, Filter, RefreshCw, PlayCircle,
} from 'lucide-react';
import { getBankReconciliation, runBankReconciliation } from '../services/api';
import { useFetch } from '../hooks/useApi';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import KPICard from '../components/ui/KPICard';
import ErrorState from '../components/ui/ErrorState';
import { formatCurrency, formatNumber, safe } from '../utils/format';

const STATUS_FILTERS = [
  'All',
  'Discrepancies Only',
  'Matched',
  'Amount Mismatch',
  'Missing Bank Transaction',
];

export default function BankTransactions() {
  const { data, loading, error, refetch } = useFetch(getBankReconciliation);
  const [statusFilter, setStatusFilter] = useState('All');
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState('');

  async function runMatching() {
    setRunning(true);
    setRunError('');
    try { await runBankReconciliation(); await refetch(); }
    catch (err) { setRunError(err.message || 'Bank reconciliation failed.'); }
    finally { setRunning(false); }
  }

  const records = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.results)) return data.results;
    if (Array.isArray(data.records)) return data.records;
    if (Array.isArray(data.bank_reconciliation)) return data.bank_reconciliation;
    return [];
  }, [data]);
  const hasRun = Boolean(data?.run_id);

  const summary = useMemo(() => {
    const matched = records.filter((r) => (r.status ?? '').toLowerCase() === 'matched').length;
    const unmatched = records.length - matched;
    const totalDiff = records.reduce((sum, r) => {
      const d = parseFloat(r.difference);
      return sum + (isNaN(d) ? 0 : Math.abs(d));
    }, 0);
    return { matched, unmatched, total: records.length, totalDiff };
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
      key: 'settlement_id',
      label: 'Settlement ID',
      render: (v) => (
        <span className="font-mono text-xs font-semibold text-slate-800 bg-surface-100 px-2 py-0.5 rounded">
          {safe(v)}
        </span>
      ),
    },
    {
      key: 'settlement_amount',
      label: 'Expected Settlement Amt',
      align: 'right',
      render: (v) => (
        <span className="font-medium text-slate-800 tabular-nums">
          {formatCurrency(v)}
        </span>
      ),
    },
    {
      key: 'bank_amount',
      label: 'Bank Credit Amt',
      align: 'right',
      render: (v) => {
        if (v === null || v === undefined || v === '') {
          return (
            <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded">
              Missing in Bank
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
      label: 'Variance',
      align: 'right',
      render: (v) => {
        if (v === null || v === undefined || String(v).toUpperCase() === 'N/A' || v === '') {
          return <span className="text-xs font-medium text-amber-700">Unmatched</span>;
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
      label: 'Reconciliation Status',
      render: (v) => <StatusBadge status={v} />,
    },
  ];

  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Bank Reconciliation</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Match gateway settlement payouts against actual bank statement credits to identify short-credits or missing deposits
          </p>
        </div>
        <div className="flex gap-2"><button onClick={refetch} disabled={loading} className="btn-secondary"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} />Refresh</button><button onClick={runMatching} disabled={running} className="btn-primary"><PlayCircle size={14} />{running ? 'Matching…' : 'Run bank reconciliation'}</button></div>
      </div>
      {runError && <p role="alert" className="text-sm text-rose-700">{runError}</p>}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Settlements Checked"
          value={hasRun ? formatNumber(summary.total) : '—'}
          icon={<Building2 size={18} />}
          iconBg="bg-slate-100"
          iconColor="text-navy-800"
          sub="Cross-checked with bank statement"
          loading={loading}
        />
        <KPICard
          label="Verified in Bank"
          value={hasRun ? formatNumber(summary.matched) : '—'}
          icon={<CheckCircle2 size={18} />}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
          sub="Exact credit match"
          loading={loading}
        />
        <KPICard
          label="Bank Exceptions"
          value={hasRun ? formatNumber(summary.unmatched) : '—'}
          icon={<XCircle size={18} />}
          iconBg="bg-rose-50"
          iconColor="text-rose-600"
          sub="Short-credited or missing deposit"
          loading={loading}
        />
        <KPICard
          label="Known Bank Variance"
          value={hasRun ? formatCurrency(summary.totalDiff) : '—'}
          icon={<TrendingDown size={18} />}
          iconBg="bg-amber-50"
          iconColor="text-amber-600"
          sub="Quantified credit shortfall"
          loading={loading}
        />
      </div>

      {/* Filter Bar */}
      <div className="card p-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 px-2">
            <Filter size={13} />
            Filter:
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
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        loading={loading}
        emptyMessage={hasRun ? 'No bank reconciliation records match the current filter' : 'No bank reconciliation run yet. Import settlements and bank transactions, then run matching.'}
        searchPlaceholder="Search settlement ID or status…"
        searchFilter={(row, q) =>
          String(row.settlement_id ?? '').toLowerCase().includes(q) ||
          String(row.status ?? '').toLowerCase().includes(q)
        }
        caption="Settlement-to-Bank Matching"
      />
    </div>
  );
}
