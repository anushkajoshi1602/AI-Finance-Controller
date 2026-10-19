/**
 * Format a number as currency.
 * Preserves non-numeric status strings like 'Missing' or 'N/A' safely when appropriate.
 * @param {number|string|null|undefined} value
 * @param {string} currency  – ISO 4217 currency code (business default: INR)
 * @returns {string}
 */
export function formatCurrency(value, currency = 'INR') {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.toLowerCase() === 'missing') return 'Missing';
    if (trimmed.toUpperCase() === 'N/A') return 'N/A';
  }
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(num)) return '—';
  return new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

export function formatCompactCurrency(value, currency = 'INR') {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(num)) return '—';
  return new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
    style: 'currency', currency, notation: 'compact', maximumFractionDigits: 1,
  }).format(num);
}

/**
 * Format an ISO date string or Date into a readable date.
 */
export function formatDate(value) {
  if (!value) return '—';
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return String(value);
    return d.toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return String(value);
  }
}

/**
 * Format an ISO date string into a readable short date (e.g. Oct 15).
 */
export function formatShortDate(value) {
  if (!value) return '—';
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return String(value);
    return d.toLocaleDateString('en-IN', {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return String(value);
  }
}

/**
 * Format an ISO date string into a readable datetime.
 */
export function formatDateTime(value) {
  if (!value) return '—';
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return String(value);
    return d.toLocaleString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(value);
  }
}

/**
 * Safe number formatter — returns '—' for null/undefined/NaN.
 */
export function formatNumber(value, decimals = 0) {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(num)) return '—';
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);
}

/**
 * Truncate a string to maxLen chars, appending '…' if truncated.
 */
export function truncate(str, maxLen = 40) {
  if (!str) return '—';
  const s = String(str);
  return s.length > maxLen ? s.slice(0, maxLen) + '…' : s;
}

/**
 * Return a safe value — fallback to '—' for null/undefined/''/NaN.
 */
export function safe(value, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'number' && isNaN(value)) return fallback;
  return value;
}
