import dayjs from 'dayjs';

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
const inrCompact = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', notation: 'compact', maximumFractionDigits: 1 });

export function toNumber(value) {
  const n = parseFloat(value);
  return Number.isNaN(n) ? 0 : n;
}

export function formatCurrency(value) {
  const n = parseFloat(value);
  return Number.isNaN(n) ? '—' : inr.format(n);
}

export function formatCompactCurrency(value) {
  const n = parseFloat(value);
  return Number.isNaN(n) ? '—' : inrCompact.format(n);
}

export function formatDate(value) {
  if (!value) return '—';
  const d = dayjs(value);
  return d.isValid() ? d.format('DD MMM YYYY') : String(value);
}

export function formatDateTime(value) {
  if (!value) return '—';
  const d = dayjs(value);
  return d.isValid() ? d.format('DD MMM YYYY, HH:mm') : String(value);
}

/** OCR confidence may arrive as 0-1 or 0-100; normalise to a percentage string. */
export function formatConfidence(value) {
  const n = parseFloat(value) || 0;
  const pct = n > 0 && n <= 1 ? n * 100 : n;
  return `${Math.round(pct * 10) / 10}%`;
}

export function confidencePct(value) {
  const n = parseFloat(value) || 0;
  const pct = n > 0 && n <= 1 ? n * 100 : n;
  return Math.max(0, Math.min(100, Math.round(pct)));
}

export function humanize(value) {
  if (value === null || value === undefined || value === '') return '—';
  return String(value)
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function getApiErrorMessage(error) {
  const data = error?.response?.data;
  if (!data) return error?.message || 'Something went wrong. Please try again.';
  if (typeof data === 'string') return data;
  if (data.detail) return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
  const parts = Object.entries(data).map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : String(msgs)}`);
  return parts.length ? parts.join(' · ') : 'Request failed. Please try again.';
}

export function todayStr() {
  return dayjs().format('YYYY-MM-DD');
}

/** Pretty-print a JSON value (or JSON string) for display. */
export function prettyJson(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
