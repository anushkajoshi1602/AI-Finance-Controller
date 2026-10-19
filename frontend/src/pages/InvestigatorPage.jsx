import { useState } from 'react';
import { Bot, RefreshCw, Play, Info } from 'lucide-react';
import { getInvestigations, runInvestigation } from '../services/api';
import { useFetch } from '../hooks/useApi';
import StatusBadge from '../components/ui/StatusBadge';
import ErrorState from '../components/ui/ErrorState';
import { PageLoader } from '../components/ui/LoadingStates';
import { formatCurrency, safe } from '../utils/format';

function Amount({ value }) {
  if (value === null || value === undefined || value === '') return <span className="text-slate-400">Not present in stored result</span>;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? <span className="tabular-nums">{formatCurrency(numeric)}</span> : safe(value);
}

function InvestigationCard({ item }) {
  const evidence = item.verified_evidence || {};
  const explanation = item.likely_explanation || {};
  const ai = item.mode === 'gemini_assisted';
  const rows = Object.entries(evidence).filter(([key]) => !['source', 'source_record_id', 'record_found', 'variance_convention'].includes(key));
  return <article className="card p-5 border-l-4 border-l-accent-600 space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs font-bold text-slate-900 bg-surface-100 px-2.5 py-1 rounded border border-slate-200">{safe(item.record?.external_id, 'Unknown record')}</span><h3 className="font-bold text-slate-900">{safe(item.anomaly_type, 'Anomaly')}</h3><StatusBadge status={item.severity || 'Info'} /></div><p className="text-xs text-slate-500 mt-1">{safe(item.record?.source, 'Financial reconciliation')}</p></div><StatusBadge status={ai ? 'Completed' : 'Info'} label={ai ? 'Gemini assisted' : 'Rule-based fallback'} /></div>
    <div className="rounded-xl border border-slate-100 bg-surface-50/60 p-4"><h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Verified stored evidence</h4>{rows.length ? <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2 text-sm">{rows.map(([key, value]) => <div key={key} className="flex justify-between gap-3"><dt className="text-slate-500">{key.replaceAll('_', ' ')}</dt><dd className="text-right font-medium text-slate-800">{key.includes('amount') || key === 'variance' || key.includes('difference') ? <Amount value={value} /> : typeof value === 'boolean' ? String(value) : safe(value)}</dd></div>)}</dl> : <p className="text-sm text-slate-500">No linked source result is available.</p>}{evidence.variance_convention && <p className="mt-3 text-xs text-slate-500">Variance convention: {evidence.variance_convention}</p>}</div>
    <div className="grid gap-3 md:grid-cols-2"><section className="rounded-xl border border-surface-200 bg-surface-50 p-4"><h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">{safe(explanation.label, 'Assessment')}</h4><p className="text-sm text-slate-800 mt-1 leading-relaxed">{safe(explanation.text, 'No explanation was stored.')}</p></section><section className="rounded-xl border border-slate-100 p-4"><h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Recommended next action</h4><p className="text-sm text-slate-700 mt-1 leading-relaxed">{safe(item.recommended_next_action, 'Review the linked source records.')}</p></section></div>
    <p className="text-xs text-slate-500">Confidence: <strong>{safe(item.confidence?.level, 'Limited')}</strong> · {safe(item.confidence?.basis, 'Based on stored evidence.')}</p>
  </article>;
}

export default function InvestigatorPage() {
  const { data, loading, error, refetch } = useFetch(getInvestigations);
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');
  const results = data?.results || [];
  const run = async () => {
    setRunning(true); setActionError(''); setNotice('');
    try {
      const response = await runInvestigation();
      await refetch();
      setNotice(response.reused ? 'Existing investigation report reused.' : 'Investigation completed for ' + response.result_count + ' anomaly records.');
    } catch (err) { setActionError(err.message || 'Investigation could not be completed.'); }
    finally { setRunning(false); }
  };
  return <div className="space-y-5 animate-fadeIn">
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4"><div><h2 className="text-xl font-bold text-slate-900 tracking-tight">AI Financial Investigator</h2><p className="text-sm text-slate-500 mt-0.5">Evidence-based review of stored anomaly and reconciliation records for this workspace.</p></div><div className="flex gap-2"><button onClick={refetch} disabled={loading || running} className="btn-secondary"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} />Refresh</button><button onClick={run} disabled={running || loading} className="btn-primary"><Play size={14} className={running ? 'animate-pulse' : ''} />{running ? 'Investigating…' : 'Run investigation'}</button></div></div>
    <div className="card flex items-start gap-3 p-4 border border-surface-200 bg-surface-50"><Info size={17} className="mt-0.5 text-accent-700 flex-shrink-0" /><p className="text-sm text-slate-800">Financial amounts and variance come from stored business records. Explanations are hypotheses unless proven by those records. Gemini-assisted results are labelled; unavailable or invalid Gemini responses use a rule-based fallback.</p></div>
    {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}{actionError && <div role="alert"><ErrorState message={actionError} onRetry={run} /></div>}
    {loading && <PageLoader />}{!loading && error && <ErrorState message={error} onRetry={refetch} />}
    {!loading && !error && results.length === 0 && <div className="card p-10 text-center"><div className="w-14 h-14 bg-surface-100 rounded-2xl flex items-center justify-center mx-auto mb-4"><Bot size={26} className="text-accent-700" /></div><h3 className="text-base font-bold text-slate-800 mb-1.5">No investigation results yet</h3><p className="text-sm text-slate-500 max-w-md mx-auto">Run anomaly detection first, then run an investigation. If the latest anomaly run contains no anomalies, the completed report will also be empty.</p></div>}
    {!loading && !error && results.length > 0 && <><p className="text-xs text-slate-500">Completed {data.completed_at ? new Date(data.completed_at).toLocaleString() : 'time unavailable'} · {results.length} record{results.length === 1 ? '' : 's'}</p><div className="space-y-4">{results.map((item) => <InvestigationCard key={item.anomaly_id} item={item} />)}</div></>}
  </div>;
}
