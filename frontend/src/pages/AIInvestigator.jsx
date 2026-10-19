import { useMemo, useState } from 'react';
import {
  Bot, RefreshCw, ChevronDown, ChevronUp,
  AlertTriangle, Info,
} from 'lucide-react';
import { getInvestigations } from '../services/api';
import { useFetch } from '../hooks/useApi';
import StatusBadge from '../components/ui/StatusBadge';
import ErrorState from '../components/ui/ErrorState';
import { PageLoader } from '../components/ui/LoadingStates';
import { formatCurrency, safe } from '../utils/format';

/**
 * Clean inline bold markdown (**text** and `code`) into React elements
 */
function renderInlineText(text) {
  if (!text) return null;
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={idx} className="font-semibold text-slate-800">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={idx}
          className="font-mono text-xs bg-surface-100 text-slate-800 px-1.5 py-0.5 rounded border border-slate-200/70"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

/**
 * Parse structured markdown investigation text returned by Gemini into clean sections
 */
function FormattedInvestigation({ text }) {
  if (!text) return null;

  const lines = String(text)
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && l !== '---');

  return (
    <div className="space-y-2.5 text-sm text-slate-600 leading-relaxed">
      {lines.map((line, idx) => {
        if (line.startsWith('### ') || line.startsWith('## ')) {
          const heading = line.replace(/^#{2,3}\s*/, '');
          return (
            <h4
              key={idx}
              className="text-xs font-bold uppercase tracking-wider text-navy-800 pt-3 first:pt-0 border-t border-slate-100 first:border-0"
            >
              {heading}
            </h4>
          );
        }
        if (line.startsWith('* ') || line.startsWith('- ')) {
          return (
            <div key={idx} className="flex items-start gap-2.5 pl-1">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-600 mt-2 flex-shrink-0" />
              <p className="flex-1">{renderInlineText(line.slice(2))}</p>
            </div>
          );
        }
        const numberedMatch = line.match(/^(\d+)\.\s+(.*)$/);
        if (numberedMatch) {
          return (
            <div key={idx} className="flex items-start gap-2.5 pl-1">
              <span className="w-5 h-5 rounded-full bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                {numberedMatch[1]}
              </span>
              <p className="flex-1">{renderInlineText(numberedMatch[2])}</p>
            </div>
          );
        }
        return <p key={idx}>{renderInlineText(line)}</p>;
      })}
    </div>
  );
}

function InvestigationCard({ investigation, index }) {
  const [expanded, setExpanded] = useState(true);

  const rawText =
    investigation.ai_investigation ??
    investigation.explanation ??
    '';

  const isFailed =
    rawText.startsWith('AI investigation failed:') ||
    rawText.includes('503 UNAVAILABLE') ||
    rawText.includes('429 RESOURCE_EXHAUSTED');

  const isQuotaError = rawText.includes('429') || rawText.includes('RESOURCE_EXHAUSTED');
  const isDemandError = rawText.includes('503') || rawText.includes('UNAVAILABLE');

  const diffVal = parseFloat(investigation.amount_difference);
  const hasDiff = !isNaN(diffVal);

  return (
    <div
      className={`card border-l-4 ${
        isFailed ? 'border-l-amber-500' : 'border-l-accent-600'
      } p-5 transition-all hover:shadow-card-hover animate-fadeIn`}
    >
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
              isFailed ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600'
            }`}
          >
            {isFailed ? <FileWarning size={18} /> : <Bot size={18} />}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-bold text-slate-900 bg-surface-100 px-2.5 py-0.5 rounded border border-slate-200">
                {safe(investigation.transaction_id, `#${index + 1}`)}
              </span>
              <h3 className="font-bold text-slate-900 text-base">
                {safe(investigation.anomaly_type, 'Reconciliation Anomaly')}
              </h3>
              <span className="text-xs font-medium text-slate-500 bg-surface-100 px-2 py-0.5 rounded-md">
                {safe(investigation.source)}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {hasDiff ? (
                <>
                  Quantified discrepancy:{' '}
                  <strong className="text-rose-600 tabular-nums">
                    {formatCurrency(diffVal)}
                  </strong>
                </>
              ) : (
                'Full settlement or bank entry missing from target ledger'
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <StatusBadge status={investigation.severity ?? 'High'} />
          <StatusBadge
            status={isFailed ? 'Pending' : 'Completed'}
            label={isFailed ? 'Retry Needed' : 'AI Analyzed'}
          />
          <button
            onClick={() => setExpanded((e) => !e)}
            className="btn-ghost p-1.5 rounded-lg text-slate-400 hover:text-slate-700"
            title={expanded ? 'Collapse report' : 'Expand report'}
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {/* Body */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-slate-100">
          {isFailed ? (
            <div className="bg-amber-50/70 border border-amber-200/80 rounded-xl p-4 space-y-2">
              <div className="flex items-center gap-2 text-amber-800 font-semibold text-sm">
                <AlertTriangle size={15} className="text-amber-600 flex-shrink-0" />
                <span>
                  {isQuotaError
                    ? 'Gemini Free-Tier Rate Limit Reached During Batch Run'
                    : isDemandError
                    ? 'Gemini Model Experiencing Temporary High Demand (503)'
                    : 'AI Analysis Incomplete for This Record'}
                </span>
              </div>
              <p className="text-xs text-amber-700 leading-relaxed">
                {isQuotaError
                  ? 'The backend investigation script encountered a temporary 429 rate-limit response from the Gemini API free tier while processing this anomaly. Wait ~60 seconds and click "Run Full Analysis" to regenerate the report.'
                  : 'The Gemini API returned a temporary 503 availability error while analyzing this transaction. Re-running the analysis will retry the investigation.'}
              </p>
              <details className="text-xs text-slate-500 pt-1">
                <summary className="cursor-pointer font-medium hover:text-slate-700">
                  View raw backend response
                </summary>
                <pre className="mt-2 p-2.5 bg-white rounded-lg border border-amber-200/60 overflow-x-auto font-mono text-[11px] text-slate-600 whitespace-pre-wrap">
                  {rawText}
                </pre>
              </details>
            </div>
          ) : rawText ? (
            <div className="bg-surface-50/60 rounded-xl p-4 border border-slate-100">
              <FormattedInvestigation text={rawText} />
            </div>
          ) : (
            <p className="text-sm text-slate-400 italic">
              No investigation text recorded for this anomaly.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function AIInvestigator() {
  const { data, loading, error, refetch } = useFetch(getInvestigations);

  const investigations = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.investigations)) return data.investigations;
    return [];
  }, [data]);

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">AI Financial Investigator</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            AI investigation is not yet connected to business-scoped financial runs.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button onClick={refetch} disabled={loading} className="btn-secondary">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Run result banner */}
      {false && runMsg && (
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

      <div className="card flex items-start gap-3 p-4 border border-sky-200 bg-sky-50/60">
        <Info size={17} className="mt-0.5 text-sky-700 flex-shrink-0" />
        <p className="text-sm text-sky-900">
          Gemini investigation is not connected to business-scoped financial runs. No AI reports or root-cause findings are being generated.
        </p>
      </div>

      {/* Content */}
      {loading && <PageLoader />}
      {error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && investigations.length === 0 && (
        <div className="card p-12 text-center">
          <div className="w-14 h-14 bg-emerald-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Bot size={26} className="text-emerald-600" />
          </div>
          <h3 className="text-base font-bold text-slate-800 mb-1.5">No AI Investigation Reports</h3>
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            You can run business-scoped anomaly detection from the Anomalies page. Gemini report generation is not available in this MVP.
          </p>
          {/* AI investigation is not connected to business-scoped runs yet. */}
          {false && <button onClick={() => setConfirmOpen(true)} className="btn-primary mx-auto">
            <PlayCircle size={16} className="text-emerald-400" />
            Run Full Analysis
          </button>}
        </div>
      )}

      {!loading && !error && investigations.length > 0 && (
        <div className="space-y-4">
          {investigations.map((inv, i) => (
            <InvestigationCard
              key={`${inv.transaction_id ?? i}-${i}`}
              investigation={inv}
              index={i}
            />
          ))}
        </div>
      )}

      {false && <ConfirmDialog
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleRunAnalysis}
        loading={running}
        title="Re-Run Full Financial Analysis?"
        description="This will re-run reconciliation, anomaly detection, and Gemini AI investigation scripts across all detected anomalies. Note: Free-tier Gemini API keys allow 5 requests per minute."
        confirmLabel="Run Analysis"
        variant="warning"
      />}
    </div>
  );
}
