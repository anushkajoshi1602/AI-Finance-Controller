import { useMemo } from 'react';
import { RotateCcw, DollarSign, Calculator, TrendingUp, RefreshCw } from 'lucide-react';
import { getRefunds } from '../services/api';
import { useFetch } from '../hooks/useApi';
import DataTable from '../components/ui/DataTable';
import KPICard from '../components/ui/KPICard';
import ErrorState from '../components/ui/ErrorState';
import { formatCurrency, formatDateTime, formatNumber, safe } from '../utils/format';

export default function Refunds() {
  const { data, loading, error, refetch } = useFetch(getRefunds);

  const refunds = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.refunds)) return data.refunds;
    return [];
  }, [data]);

  const summary = useMemo(() => {
    const count = refunds.length;
    const totalAmount = refunds.reduce((s, r) => s + (parseFloat(r.refund_amount) || 0), 0);
    const avgAmount = count > 0 ? totalAmount / count : 0;
    const maxAmount = count > 0
      ? Math.max(...refunds.map((r) => parseFloat(r.refund_amount) || 0))
      : 0;
    return { count, totalAmount, avgAmount, maxAmount };
  }, [refunds]);

  const columns = [
    {
      key: 'refund_id',
      label: 'Refund ID',
      render: (v) => (
        <span className="font-mono text-xs font-semibold text-slate-800 bg-surface-100 px-2 py-0.5 rounded">
          {safe(v)}
        </span>
      ),
    },
    {
      key: 'payment_id',
      label: 'Original Payment ID',
      render: (v) => (
        <span className="font-mono text-xs text-slate-600">
          {safe(v)}
        </span>
      ),
    },
    {
      key: 'refund_amount',
      label: 'Refund Amount',
      align: 'right',
      render: (v) => (
        <span className="font-semibold text-purple-700 tabular-nums">
          {formatCurrency(v)}
        </span>
      ),
    },
    {
      key: 'refund_date',
      label: 'Refund Date',
      render: (v) => (
        <span className="text-slate-500 text-xs tabular-nums">
          {formatDateTime(v)}
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
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Customer Refunds</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Processed customer reversals and partial/full payment refunds deducted from gateway settlements
          </p>
        </div>
        <button onClick={refetch} disabled={loading} className="btn-secondary self-start sm:self-auto">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Refunds Issued"
          value={formatNumber(summary.count)}
          icon={<RotateCcw size={18} />}
          iconBg="bg-purple-50"
          iconColor="text-purple-600"
          sub="Completed reversals"
          loading={loading}
        />
        <KPICard
          label="Total Refund Volume"
          value={formatCurrency(summary.totalAmount)}
          icon={<DollarSign size={18} />}
          iconBg="bg-rose-50"
          iconColor="text-rose-600"
          sub="Deducted from gross settlements"
          loading={loading}
        />
        <KPICard
          label="Average Refund"
          value={formatCurrency(summary.avgAmount)}
          icon={<Calculator size={18} />}
          iconBg="bg-slate-100"
          iconColor="text-navy-800"
          sub="Mean reversal value"
          loading={loading}
        />
        <KPICard
          label="Largest Single Refund"
          value={formatCurrency(summary.maxAmount)}
          icon={<TrendingUp size={18} />}
          iconBg="bg-amber-50"
          iconColor="text-amber-600"
          sub="Highest individual reversal"
          loading={loading}
        />
      </div>

      <DataTable
        columns={columns}
        data={refunds}
        loading={loading}
        emptyMessage="No refund records found"
        searchPlaceholder="Search refund ID, payment ID, or date…"
        searchFilter={(row, q) =>
          String(row.refund_id ?? '').toLowerCase().includes(q) ||
          String(row.payment_id ?? '').toLowerCase().includes(q) ||
          String(row.refund_date ?? '').toLowerCase().includes(q)
        }
        caption="Refund Records"
      />
    </div>
  );
}
