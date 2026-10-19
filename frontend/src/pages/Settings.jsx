import { useState } from 'react';
import {
  Server, RefreshCw, CheckCircle2, XCircle, Loader2,
  Globe, Info, Database,
} from 'lucide-react';
import { useHealth } from '../hooks/useApi';
import ConnectionBadge from '../components/ui/ConnectionBadge';
import { uploadCsv } from '../services/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

function SettingRow({ label, value, description, children }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 py-4 border-b border-slate-100 last:border-0">
      <div className="flex-1 min-w-0 pr-4">
        <p className="text-sm font-semibold text-slate-800">{label}</p>
        {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
        {value && (
          <p className="text-xs text-slate-700 font-mono mt-1.5 bg-surface-100 inline-block px-2 py-0.5 rounded border border-slate-200/70 truncate max-w-full">
            {value}
          </p>
        )}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

const ENDPOINTS = [
  { method: 'GET', path: '/api/health', source: 'System status', desc: 'Live backend health check' },
  { method: 'GET', path: '/api/businesses', source: 'Memberships', desc: 'Available business workspaces' },
  { method: 'POST', path: '/api/businesses/{id}/imports/{dataset}', source: 'Relational financial tables', desc: 'Validate and import CSV data into the selected business' },
  { method: 'GET', path: '/api/businesses/{id}/dashboard and /ledger/*', source: 'Business-scoped relational data', desc: 'Dashboard metrics and imported financial records' },
  { method: 'POST/GET', path: '/api/businesses/{id}/reconciliation/run and /results', source: 'Payments, refunds, settlements', desc: 'Business-scoped reconciliation and persisted results' },
  { method: 'POST/GET', path: '/api/businesses/{id}/bank-reconciliation/run and /results', source: 'Settlements and bank transactions', desc: 'Business-scoped settlement-to-bank matching' },
  { method: 'POST/GET', path: '/api/businesses/{id}/anomalies/run and /results', source: 'Business-scoped reconciliation results', desc: 'Detect and list financial anomalies' },
  { method: 'POST/GET', path: '/api/businesses/{id}/cash-flow/run and /results', source: 'Payments and settlements', desc: 'Create and list a seven-day cash-flow forecast' },
];

const CSV_SCHEMAS = {
  customers: 'Required headers: external_id, name, email.',
  payments: 'Required: external_id, amount, status. Add customer_external_id and payment_date to link customers and enable forecasting.',
  refunds: 'Required: external_id, payment_external_id, refund_amount.',
  settlements: 'Required: external_id, payment_external_id, gross_amount, refund_amount, fee, tax, net_amount.',
  bank_transactions: 'Required: external_id, amount. Add settlement_external_id to match a settlement.',
};

export default function Settings() {
  const { status, lastChecked, retry } = useHealth(30_000);
  const [dataset, setDataset] = useState('customers');
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploading, setUploading] = useState(false);

  async function submitUpload(event) {
    event.preventDefault();
    if (!selectedFile) return;
    setUploading(true);
    setUploadMessage('');
    try {
      const result = await uploadCsv(dataset, selectedFile);
      setUploadMessage(result.status === 'validated'
        ? `Imported ${dataset} successfully${result.duplicate_upload ? ' (duplicate upload)' : ''}.`
        : `Import rejected: ${result.validation_errors.join('; ')}`);
    } catch (error) {
      setUploadMessage(`Import failed: ${error.message || 'Please try again.'}`);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-6 animate-fadeIn max-w-4xl">
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">System Configuration & Diagnostics</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          FastAPI backend connectivity, data pipeline mapping, and security posture
        </p>
      </div>

      <form onSubmit={submitUpload} className="card p-5 space-y-3">
        <div>
          <h3 className="text-sm font-bold text-slate-800">Import business data</h3>
          <p className="text-xs text-slate-500 mt-1">Upload CSV files into the selected workspace. Import customers, payments, refunds, settlements, and bank transactions before running analysis.</p>
          <p className="text-xs text-slate-600 mt-2"><strong>{dataset.replaceAll('_', ' ')} CSV:</strong> {CSV_SCHEMAS[dataset]}</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <select className="input" value={dataset} onChange={(event) => setDataset(event.target.value)}>
            {['customers', 'payments', 'refunds', 'settlements', 'bank_transactions'].map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
          </select>
          <input className="input flex-1" type="file" accept=".csv,text/csv" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} />
          <button className="btn-primary justify-center" disabled={!selectedFile || uploading}>{uploading ? 'Importing…' : 'Upload CSV'}</button>
        </div>
        {uploadMessage && <p role={uploadMessage.startsWith('Import rejected') || uploadMessage.startsWith('Import failed') ? 'alert' : 'status'} className={`text-sm ${uploadMessage.startsWith('Import rejected') || uploadMessage.startsWith('Import failed') ? 'text-rose-700' : 'text-slate-600'}`}>{uploadMessage}</p>}
      </form>

      {/* Backend Connection */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Server size={16} className="text-accent-600" />
            <h3 className="text-sm font-bold text-slate-800">FastAPI Backend Connection</h3>
          </div>
          <button
            onClick={retry}
            disabled={status === 'checking'}
            className="btn-secondary py-1.5 px-3 text-xs"
          >
            <RefreshCw size={13} className={status === 'checking' ? 'animate-spin' : ''} />
            Test Connection
          </button>
        </div>

        <div className="px-5">
          <SettingRow
            label="API Base URL"
            value={API_BASE_URL}
            description="Configured via VITE_API_BASE_URL in frontend/.env"
          >
            <ConnectionBadge status={status} lastChecked={lastChecked} />
          </SettingRow>

          <SettingRow
            label="Health Check Endpoint"
            value={`${API_BASE_URL}/api/health`}
            description="Automatically polled every 30 seconds to verify backend availability"
          >
            <span
              className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${
                status === 'online'
                  ? 'bg-emerald-50 text-emerald-700'
                  : status === 'offline'
                  ? 'bg-rose-50 text-rose-700'
                  : 'bg-amber-50 text-amber-700'
              }`}
            >
              {status === 'online' && <CheckCircle2 size={13} />}
              {status === 'offline' && <XCircle size={13} />}
              {status === 'checking' && <Loader2 size={13} className="animate-spin" />}
              {status === 'online' ? 'Healthy (200 OK)' : status === 'offline' ? 'Unreachable' : 'Checking…'}
            </span>
          </SettingRow>

          <SettingRow
            label="AI Investigation"
            description="Gemini investigation is not connected to the business-scoped financial workflow."
          >
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 bg-slate-100 px-2.5 py-1 rounded-full">
              <Info size={13} />
              Not connected
            </span>
          </SettingRow>
        </div>
      </div>

      {/* API Contract & Data Sources */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2.5">
          <Globe size={16} className="text-accent-600" />
          <div>
            <h3 className="text-sm font-bold text-slate-800">Integrated API Endpoints & CSV Schemas</h3>
            <p className="text-xs text-slate-400">Business-scoped endpoints used by the current application workflow</p>
          </div>
        </div>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Method</th>
                <th>Endpoint</th>
                <th>Backend Source</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map(({ method, path, source, desc }) => (
                <tr key={path}>
                  <td className="w-20">
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded-md ${
                        method === 'GET'
                          ? 'bg-sky-50 text-sky-700 border border-sky-200/60'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
                      }`}
                    >
                      {method}
                    </span>
                  </td>
                  <td>
                    <code className="text-xs text-slate-800 font-mono font-semibold">{path}</code>
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-1.5 text-xs text-slate-600 font-mono">
                      <Database size={12} className="text-slate-400" />
                      {source}
                    </span>
                  </td>
                  <td className="text-xs text-slate-500">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
