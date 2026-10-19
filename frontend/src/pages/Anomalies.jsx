import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, AlertOctagon, Info, DollarSign,
  Sparkles, ArrowUpRight, RefreshCw, PlayCircle,
} from 'lucide-react';
import { getAnomalies, runAnomalyDetection } from '../services/api';
import { useFetch } from '../hooks/useApi';
import DataTable from '../components/ui/DataTable';
import StatusBadge from '../components/ui/StatusBadge';
import KPICard from '../components/ui/KPICard';
import ErrorState from '../components/ui/ErrorState';
import { formatCurrency, formatNumber, safe } from '../utils/format';
import { getActionGuidance } from '../utils/anomalyGuidance';

function SeverityIcon({ severity }) {
  const s = (severity ?? '').toLowerCase();
  if (s === 'critical' || s === 'high') {
    return <AlertOctagon size={15} className="text-rose-600 flex-shrink-0" />;
  }
  if (s === 'medium') {
    return <AlertTriangle size={15} className="text-amber-500 flex-shrink-0" />;
  }
  return <Info size={15} className="text-slate-400 flex-shrink-0" />;
}

export default function Anomalies() {
  const { data, loading, error, refetch } = useFetch(getAnomalies);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState('');

  async function runDetection() {
    setRunning(true);
    setRunError('');
    try { await runAnomalyDetection(); await refetch(); }
    catch (err) { setRunError(err.message || 'Anomaly detection failed.'); }
    finally { setRunning(false); }
  }

  const anomalies = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.results)) return data.results;
    if (Array.isArray(data.anomalies)) return data.anomalies;
    return [];
  }, [data]);
  const hasRun = Boolean(data?.run_id);

  const summary = useMemo(() => {
    const total = anomalies.length;
    const highCount = anomalies.filter((a) =>
      ['critical', 'high'].includes((a.severity ?? '').toLowerCase())
    ).length;
    const paymentSourceCount = anomalies.filter((a) =>
      (a.source ?? '').toLowerCase().includes('payment')
    ).length;
    const bankSourceCount = anomalies.filter((a) =>
      (a.source ?? '').toLowerCase().includes('bank')
    ).length;
    const totalExposure = anomalies.reduce((sum, a) => {
      const diff = parseFloat(a.amount_difference);
      return sum + (isNaN(diff) ? 0 : Math.abs(diff));
    }, 0);

    return { total, highCount, paymentSourceCount, bankSourceCount, totalExposure };
  }, [anomalies]);

  const columns = [
    {
      key: 'transaction_id',
      label: 'Affected Record ID',
      render: (v) => (
        <span className="font-mono text-xs font-semibold text-slate-800 bg-surface-100 px-2.5 py-1 rounded">
          {safe(v)}
        </span>
      ),
    },
    {
      key: 'source',
      label: 'Audit Source',
      render: (v) => (
        <span className="text-xs font-medium text-slate-700 bg-surface-100 px-2.5 py-1 rounded-md">
          {safe(v)}
        </span>
      ),
    },
    {
      key: 'anomaly_type',
      label: 'Anomaly Type',
      render: (v, row) => (
        <div className="flex items-center gap-2">
          <SeverityIcon severity={row.severity} />
          <span className="font-semibold text-slate-800">{safe(v)}</span>
        </div>
      ),
    },
    {
      key: 'amount_difference',
      label: 'Amount Discrepancy',
      align: 'right',
      render: (v) => {
        const val = parseFloat(v);
        if (isNaN(val)) {
          return (
            <span className="text-xs font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded">
              Full Record Missing
            </span>
          );
        }
        return (
          <span className="font-bold text-rose-600 tabular-nums">
            {formatCurrency(val)}
          </span>
        );
      },
    },
    {
      key: 'severity',
      label: 'Severity',
      render: (v) => <StatusBadge status={v} />,
    },
    {
      key: 'guidance',
      label: 'Operational Assessment',
      sortable: false,
      render: (_, row) => (
        <span className="text-xs text-slate-500 leading-relaxed block max-w-md">
          {getActionGuidance(row.anomaly_type, row.source, row.amount_difference)}
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
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Financial Anomalies</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Exceptions flagged across payment-to-settlement and settlement-to-bank reconciliation pipelines
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button onClick={refetch} disabled={loading} className="btn-secondary"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} />Refresh</button>
          <button onClick={runDetection} disabled={running} className="btn-primary"><PlayCircle size={14} />{running ? 'Detecting…' : 'Detect anomalies'}</button>
          <Link to="/ai-investigator" className="btn-primary">
            <Sparkles size={15} className="text-emerald-400" />
            AI investigation status
            <ArrowUpRight size={14} />
          </Link>
        </div>
      </div>
      {runError && <p role="alert" className="text-sm text-rose-700">{runError}</p>}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Flagged"
          value={hasRun ? formatNumber(summary.total) : '—'}
          icon={<AlertTriangle size={18} />}
          iconBg="bg-amber-50"
          iconColor="text-amber-600"
          sub={hasRun ? `${formatNumber(summary.highCount)} high-severity alerts` : 'Run anomaly detection to populate this count'}
          loading={loading}
        />
        <KPICard
          label="Known Variance Exposure"
          value={hasRun ? formatCurrency(summary.totalExposure) : '—'}
          icon={<DollarSign size={18} />}
          iconBg="bg-rose-50"
          iconColor="text-rose-600"
          sub="Excludes unquantified missing records"
          loading={loading}
        />
        <KPICard
          label="Payment Recon Alerts"
          value={hasRun ? formatNumber(summary.paymentSourceCount) : '—'}
          icon={<AlertOctagon size={18} />}
          iconBg="bg-slate-100"
          iconColor="text-navy-800"
          sub="Gateway settlement discrepancies"
          loading={loading}
        />
        <KPICard
          label="Bank Recon Alerts"
          value={hasRun ? formatNumber(summary.bankSourceCount) : '—'}
          icon={<AlertOctagon size={18} />}
          iconBg="bg-sky-50"
          iconColor="text-sky-600"
          sub="Bank statement credit discrepancies"
          loading={loading}
        />
      </div>

      <DataTable
        columns={columns}
        data={anomalies}
        loading={loading}
        emptyMessage={data?.run_id ? 'No anomalies in the latest detection run' : 'No anomaly detection run yet. Run detection after reconciliation.'}
        searchPlaceholder="Search ID, source, type, or severity…"
        searchFilter={(row, q) =>
          String(row.transaction_id ?? '').toLowerCase().includes(q) ||
          String(row.source ?? '').toLowerCase().includes(q) ||
          String(row.anomaly_type ?? '').toLowerCase().includes(q) ||
          String(row.severity ?? '').toLowerCase().includes(q)
        }
        caption="Detected Reconciliation Anomalies"
      />
    </div>
  );
}
