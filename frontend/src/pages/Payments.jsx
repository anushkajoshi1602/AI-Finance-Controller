import { useState, useMemo } from 'react';
import {
  CreditCard, CheckCircle2, XCircle, Clock, Filter, RefreshCw,
} from 'lucide-react';
import { getPayments } from '../services/api';
import { useFetch } from '../hooks/useApi';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import KPICard from '../components/ui/KPICard';
import ErrorState from '../components/ui/ErrorState';
import { formatCurrency, formatDateTime, formatNumber, safe } from '../utils/format';

const STATUS_OPTIONS = ['All', 'Success', 'Failed', 'Pending'];
const METHOD_OPTIONS = ['All', 'UPI', 'Netbanking', 'Card'];

export default function Payments() {
  const { data, loading, error, refetch } = useFetch(getPayments);
  const [statusFilter, setStatusFilter] = useState('All');
  const [methodFilter, setMethodFilter] = useState('All');

  const payments = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.payments)) return data.payments;
    return [];
  }, [data]);

  const summary = useMemo(() => {
    const total = payments.length;
    const success = payments.filter((p) => (p.status ?? '').toLowerCase() === 'success');
    const failed = payments.filter((p) => (p.status ?? '').toLowerCase() === 'failed');
    const pending = payments.filter((p) => (p.status ?? '').toLowerCase() === 'pending');

    const grossVolume = payments.reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);
    const successVolume = success.reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);

    return {
      total,
      successCount: success.length,
      failedCount: failed.length,
      pendingCount: pending.length,
      grossVolume,
      successVolume,
    };
  }, [payments]);

  const filtered = useMemo(() => {
    return payments.filter((p) => {
      const matchStatus =
        statusFilter === 'All' ||
        (p.status ?? '').toLowerCase() === statusFilter.toLowerCase();
      const matchMethod =
        methodFilter === 'All' ||
        (p.payment_method ?? '').toLowerCase() === methodFilter.toLowerCase();
      return matchStatus && matchMethod;
    });
  }, [payments, statusFilter, methodFilter]);

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
      key: 'customer_id',
      label: 'Customer ID',
      render: (v) => (
        <span className="text-xs font-medium text-slate-600 tabular-nums">
          {v != null ? v : '—'}
        </span>
      ),
    },
    {
      key: 'payment_method',
      label: 'Payment Method',
      render: (v) => (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-surface-100 text-slate-700">
          {safe(v)}
        </span>
      ),
    },
    {
      key: 'amount',
      label: 'Amount',
      align: 'right',
      render: (v) => (
        <span className="font-semibold text-slate-900 tabular-nums">
          {formatCurrency(v)}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (v) => <StatusBadge status={v} />,
    },
    {
      key: 'failure_reason',
      label: 'Failure Reason',
      render: (v, row) => {
        if (!v) {
          return (row.status ?? '').toLowerCase() === 'success' ? (
            <span className="text-xs text-slate-400">Cleared</span>
          ) : (
            <span className="text-xs text-slate-300">—</span>
          );
        }
        return (
          <span className="text-xs font-medium text-rose-600 bg-rose-50 px-2 py-0.5 rounded">
            {v}
          </span>
        );
      },
    },
    {
      key: 'payment_date',
      label: 'Payment Date',
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
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Payment Ledger</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Complete transaction log across UPI, Netbanking, and Card channels
          </p>
        </div>
        <button onClick={refetch} disabled={loading} className="btn-secondary self-start sm:self-auto">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* KPI Summary Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Gross Processed"
          value={formatCurrency(summary.grossVolume)}
          icon={<CreditCard size={18} />}
          iconBg="bg-slate-100"
          iconColor="text-navy-800"
          sub={`${formatNumber(summary.total)} total transactions`}
          loading={loading}
        />
        <KPICard
          label="Successful Payments"
          value={formatCurrency(summary.successVolume)}
          icon={<CheckCircle2 size={18} />}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
          sub={`${formatNumber(summary.successCount)} cleared`}
          loading={loading}
        />
        <KPICard
          label="Failed Payments"
          value={formatNumber(summary.failedCount)}
          icon={<XCircle size={18} />}
          iconBg="bg-rose-50"
          iconColor="text-rose-600"
          sub="Declined or gateway error"
          loading={loading}
        />
        <KPICard
          label="Pending Settlement"
          value={formatNumber(summary.pendingCount)}
          icon={<Clock size={18} />}
          iconBg="bg-amber-50"
          iconColor="text-amber-600"
          sub="Awaiting final confirmation"
          loading={loading}
        />
      </div>

      {/* Filter Bar */}
      <div className="card p-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 px-2">
            <Filter size={13} />
            Status:
          </span>
          <div className="flex items-center gap-1 bg-surface-100 rounded-xl p-1">
            {STATUS_OPTIONS.map((s) => (
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

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-500 px-2">Method:</span>
          <div className="flex items-center gap-1 bg-surface-100 rounded-xl p-1">
            {METHOD_OPTIONS.map((m) => (
              <button
                key={m}
                onClick={() => setMethodFilter(m)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  methodFilter === m
                    ? 'bg-accent-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        loading={loading}
        emptyMessage="No payments match the active filters"
        emptySubtext="Try switching status or payment method filters back to 'All'."
        searchPlaceholder="Search ID, method, reason, customer…"
        searchFilter={(row, q) =>
          String(row.payment_id ?? '').toLowerCase().includes(q) ||
          String(row.customer_id ?? '').toLowerCase().includes(q) ||
          String(row.payment_method ?? '').toLowerCase().includes(q) ||
          String(row.status ?? '').toLowerCase().includes(q) ||
          String(row.failure_reason ?? '').toLowerCase().includes(q) ||
          String(row.payment_date ?? '').toLowerCase().includes(q)
        }
        caption="Payment Transactions"
      />
    </div>
  );
}
