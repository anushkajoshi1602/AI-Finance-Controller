import { useState, useMemo } from 'react';
import {
  Landmark, DollarSign, Receipt, Percent, Filter, RefreshCw, Info,
} from 'lucide-react';
import { getSettlements } from '../services/api';
import { useFetch } from '../hooks/useApi';
import DataTable from '../components/ui/DataTable';
import KPICard from '../components/ui/KPICard';
import ErrorState from '../components/ui/ErrorState';
import { formatCurrency, formatNumber, safe } from '../utils/format';

const FILTER_OPTIONS = [
  { id: 'all', label: 'All Settlements' },
  { id: 'with_refund', label: 'With Refund Deduction' },
  { id: 'no_refund', label: 'Standard (No Refund)' },
];

export default function Settlements() {
  const { data, loading, error, refetch } = useFetch(getSettlements);
  const [filterMode, setFilterMode] = useState('all');

  const settlements = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.settlements)) return data.settlements;
    return [];
  }, [data]);

  const summary = useMemo(() => {
    const totalGross = settlements.reduce((s, r) => s + (parseFloat(r.gross_amount) || 0), 0);
    const totalRefunds = settlements.reduce((s, r) => s + (parseFloat(r.refund_amount) || 0), 0);
    const totalFees = settlements.reduce((s, r) => s + (parseFloat(r.fee) || 0), 0);
    const totalTax = settlements.reduce((s, r) => s + (parseFloat(r.tax) || 0), 0);
    const totalNet = settlements.reduce((s, r) => s + (parseFloat(r.net_amount) || 0), 0);
    return {
      count: settlements.length,
      totalGross,
      totalRefunds,
      totalFees,
      totalTax,
      totalFeesAndTax: totalFees + totalTax,
      totalNet,
    };
  }, [settlements]);

  const filtered = useMemo(() => {
    if (filterMode === 'with_refund') {
      return settlements.filter((r) => (parseFloat(r.refund_amount) || 0) > 0);
    }
    if (filterMode === 'no_refund') {
      return settlements.filter((r) => (parseFloat(r.refund_amount) || 0) === 0);
    }
    return settlements;
  }, [settlements, filterMode]);

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
      key: 'payment_id',
      label: 'Payment ID',
      render: (v) => (
        <span className="font-mono text-xs text-slate-600">
          {safe(v)}
        </span>
      ),
    },
    {
      key: 'gross_amount',
      label: 'Gross Amount',
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
          <span className="font-medium text-purple-700 bg-purple-50 px-2 py-0.5 rounded tabular-nums text-xs">
            -{formatCurrency(val)}
          </span>
        ) : (
          <span className="text-slate-400 tabular-nums text-xs">{formatCurrency(0)}</span>
        );
      },
    },
    {
      key: 'fee',
      label: 'Gateway Fee',
      align: 'right',
      render: (v) => (
        <span className="text-slate-600 tabular-nums text-xs">
          -{formatCurrency(v)}
        </span>
      ),
    },
    {
      key: 'tax',
      label: 'Tax',
      align: 'right',
      render: (v) => (
        <span className="text-slate-600 tabular-nums text-xs">
          -{formatCurrency(v)}
        </span>
      ),
    },
    {
      key: 'net_amount',
      label: 'Net Settled',
      align: 'right',
      render: (v) => (
        <span className="font-bold text-emerald-700 tabular-nums">
          {formatCurrency(v)}
        </span>
      ),
    },
  ];

  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Gateway Settlements</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Imported gateway settlement amounts, including reported refunds, fees, tax, and net payouts
          </p>
        </div>
        <button onClick={refetch} disabled={loading} className="btn-secondary self-start sm:self-auto">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Formula Context Banner */}
      <div className="card px-4 py-3 bg-surface-50/70 flex items-center gap-3 text-xs text-slate-600">
        <Info size={15} className="text-accent-600 flex-shrink-0" />
        <span>
          <strong>Settlement Formula:</strong>{' '}
          <code className="font-mono text-slate-800 bg-white px-1.5 py-0.5 rounded border border-slate-200">
            Net Settled = values from the imported settlement record
          </code>
        </span>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Gross Settled Volume"
          value={formatCurrency(summary.totalGross)}
          icon={<DollarSign size={18} />}
          iconBg="bg-slate-100"
          iconColor="text-navy-800"
          sub={`${formatNumber(summary.count)} settlement batches`}
          loading={loading}
        />
        <KPICard
          label="Net Payout Total"
          value={formatCurrency(summary.totalNet)}
          icon={<Landmark size={18} />}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
          sub="Transferred to bank account"
          loading={loading}
        />
        <KPICard
          label="Fees & Taxes Deducted"
          value={formatCurrency(summary.totalFeesAndTax)}
          icon={<Percent size={18} />}
          iconBg="bg-amber-50"
          iconColor="text-amber-600"
          sub={`${formatCurrency(summary.totalFees)} fee · ${formatCurrency(summary.totalTax)} tax`}
          loading={loading}
        />
        <KPICard
          label="Refund Adjustments"
          value={formatCurrency(summary.totalRefunds)}
          icon={<Receipt size={18} />}
          iconBg="bg-purple-50"
          iconColor="text-purple-600"
          sub="Offset before payout"
          loading={loading}
        />
      </div>

      {/* Filter Bar */}
      <div className="card p-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 px-2">
            <Filter size={13} />
            Filter:
          </span>
          <div className="flex items-center gap-1 bg-surface-100 rounded-xl p-1">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                onClick={() => setFilterMode(opt.id)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  filterMode === opt.id
                    ? 'bg-navy-900 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        loading={loading}
        emptyMessage="No settlement records match the selected filter"
        searchPlaceholder="Search settlement ID or payment ID…"
        searchFilter={(row, q) =>
          String(row.settlement_id ?? '').toLowerCase().includes(q) ||
          String(row.payment_id ?? '').toLowerCase().includes(q)
        }
        caption="Settlement Ledger"
      />
    </div>
  );
}
