import { useState, useMemo, useEffect } from 'react';
import {
  ChevronUp, ChevronDown, ChevronsUpDown, Search,
  ChevronLeft, ChevronRight, X, Inbox,
} from 'lucide-react';

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

/**
 * DataTable – sortable, searchable, paginated table with accurate numeric/date/string sorting.
 *
 * @param {Object[]} columns       – { key, label, render?, sortable?, align? }
 * @param {Object[]} data          – array of row objects
 * @param {boolean}  loading
 * @param {string}   error
 * @param {string}   emptyMessage
 * @param {string}   emptySubtext
 * @param {Function} [searchFilter] – (row, query) => boolean
 * @param {string}   [searchPlaceholder]
 * @param {string}   [caption]
 * @param {React.ReactNode} [headerActions]
 */
export default function DataTable({
  columns = [],
  data = [],
  loading = false,
  error = null,
  emptyMessage = 'No records match the current view',
  emptySubtext = 'Try adjusting your search query or filters.',
  searchFilter,
  searchPlaceholder = 'Search records…',
  caption,
  headerActions,
}) {
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Reset to page 1 when external data (e.g. status filter) changes
  useEffect(() => {
    setPage(1);
  }, [data.length]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !searchFilter) return data;
    return data.filter((row) => searchFilter(row, q));
  }, [data, query, searchFilter]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];

      // Push null/undefined/empty/N/A/Missing to the bottom
      const aEmpty = av === null || av === undefined || av === '' || av === 'N/A' || av === 'Missing';
      const bEmpty = bv === null || bv === undefined || bv === '' || bv === 'N/A' || bv === 'Missing';
      if (aEmpty && bEmpty) return 0;
      if (aEmpty) return 1;
      if (bEmpty) return -1;

      // Numeric comparison if both parse purely as numbers
      const aNum = typeof av === 'number' ? av : (typeof av === 'string' && /^-?\d+(\.\d+)?$/.test(av.trim()) ? parseFloat(av) : NaN);
      const bNum = typeof bv === 'number' ? bv : (typeof bv === 'string' && /^-?\d+(\.\d+)?$/.test(bv.trim()) ? parseFloat(bv) : NaN);

      if (!isNaN(aNum) && !isNaN(bNum)) {
        return sortDir === 'asc' ? aNum - bNum : bNum - aNum;
      }

      // Natural alphanumeric string comparison (handles p00001, S00002, dates, etc.)
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: 'base' });
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const paginated = sorted.slice((safePage - 1) * pageSize, safePage * pageSize);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
    setPage(1);
  };

  const SortIcon = ({ colKey }) => {
    if (sortKey !== colKey) return <ChevronsUpDown size={13} className="text-slate-300 group-hover:text-slate-400" />;
    return sortDir === 'asc'
      ? <ChevronUp size={13} className="text-accent-600" />
      : <ChevronDown size={13} className="text-accent-600" />;
  };

  // Row unique key resolver across all CSV schemas
  const getRowKey = (row, idx) =>
    row.payment_id ??
    row.settlement_id ??
    row.refund_id ??
    row.transaction_id ??
    row.id ??
    `${idx}`;

  // ── Loading skeletons ─────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          {caption ? (
            <span className="font-semibold text-slate-700 text-sm">{caption}</span>
          ) : (
            <div className="skeleton h-5 w-36 rounded-lg" />
          )}
          <div className="skeleton h-9 w-64 rounded-xl" />
        </div>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
            </thead>
            <tbody>
              {Array.from({ length: 6 }).map((_, i) => (
                <tr key={i}>
                  {columns.map((c) => (
                    <td key={c.key}><div className="skeleton h-4 rounded-md" /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="card p-8 text-center">
        <p className="text-danger-600 font-semibold mb-1">Unable to load table records</p>
        <p className="text-slate-500 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      {/* Header row */}
      {(caption || searchFilter || headerActions) && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-slate-100 bg-white">
          <div className="flex items-center gap-2.5">
            {caption && <span className="font-semibold text-slate-800 text-sm">{caption}</span>}
            <span className="text-xs font-medium text-slate-500 bg-surface-100 px-2 py-0.5 rounded-full tabular-nums">
              {sorted.length.toLocaleString()} {sorted.length === 1 ? 'record' : 'records'}
            </span>
          </div>

          <div className="flex items-center gap-2.5 ml-auto">
            {headerActions}
            {searchFilter && (
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                <input
                  className="input pl-8 pr-8 py-1.5 w-60 sm:w-64 text-sm"
                  placeholder={searchPlaceholder}
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setPage(1); }}
                />
                {query && (
                  <button
                    onClick={() => { setQuery(''); setPage(1); }}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    title="Clear search"
                  >
                    <X size={13} />
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} className={col.align === 'right' ? 'text-right' : 'text-left'}>
                  {col.sortable !== false ? (
                    <button
                      onClick={() => handleSort(col.key)}
                      className="group inline-flex items-center gap-1 hover:text-slate-800 transition-colors"
                    >
                      <span>{col.label}</span>
                      <SortIcon colKey={col.key} />
                    </button>
                  ) : col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center py-14 px-4">
                  <div className="flex flex-col items-center justify-center max-w-sm mx-auto">
                    <div className="w-10 h-10 rounded-xl bg-surface-100 flex items-center justify-center text-slate-400 mb-2.5">
                      <Inbox size={18} />
                    </div>
                    <p className="text-sm font-medium text-slate-700">{emptyMessage}</p>
                    {emptySubtext && (
                      <p className="text-xs text-slate-400 mt-1">{emptySubtext}</p>
                    )}
                    {query && (
                      <button
                        onClick={() => { setQuery(''); setPage(1); }}
                        className="mt-3 text-xs font-medium text-accent-600 hover:text-accent-700"
                      >
                        Clear search query
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              paginated.map((row, i) => (
                <tr key={`${getRowKey(row, i)}-${i}`}>
                  {columns.map((col) => (
                    <td key={col.key} className={col.align === 'right' ? 'text-right' : 'text-left'}>
                      {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-t border-slate-100 bg-surface-50/40">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>Rows per page:</span>
          <select
            className="border border-slate-200 bg-white rounded-lg px-2 py-1 text-xs text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-accent-500/25"
            value={pageSize}
            onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
          >
            {PAGE_SIZE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <span className="ml-2 tabular-nums">
            {sorted.length === 0
              ? 'Showing 0 records'
              : `Showing ${(safePage - 1) * pageSize + 1}–${Math.min(safePage * pageSize, sorted.length)} of ${sorted.length.toLocaleString()}`}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <button
            className="btn-ghost px-2 py-1 rounded-lg text-xs disabled:opacity-30"
            onClick={() => setPage(1)}
            disabled={safePage === 1}
            title="First page"
          >
            First
          </button>
          <button
            className="btn-ghost p-1.5 rounded-lg disabled:opacity-30"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={safePage === 1}
            title="Previous page"
          >
            <ChevronLeft size={15} />
          </button>
          <span className="text-xs font-medium text-slate-700 px-2.5 tabular-nums">
            Page {safePage} of {totalPages}
          </span>
          <button
            className="btn-ghost p-1.5 rounded-lg disabled:opacity-30"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={safePage === totalPages}
            title="Next page"
          >
            <ChevronRight size={15} />
          </button>
          <button
            className="btn-ghost px-2 py-1 rounded-lg text-xs disabled:opacity-30"
            onClick={() => setPage(totalPages)}
            disabled={safePage === totalPages}
            title="Last page"
          >
            Last
          </button>
        </div>
      </div>
    </div>
  );
}
