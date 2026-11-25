import api from '../api/client';

/** Trigger a browser download for an already-fetched Blob. */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/** Open a fetched Blob (e.g. invoice PDF) in a new browser tab. */
export function openBlobInNewTab(blob) {
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

/** Download a report endpoint as CSV using the authenticated axios client. */
export async function exportCsvReport(url, params = {}, filename = 'report.csv') {
  const res = await api.get(url, { params: { ...params, format: 'csv' }, responseType: 'blob' });
  downloadBlob(res.data, filename);
  return res;
}
