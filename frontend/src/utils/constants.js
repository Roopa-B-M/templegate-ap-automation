export const ROLES = ['ADMIN', 'AP_CLERK', 'APPROVER', 'FINANCE'];

export const ROLE_OPTIONS = [
  { value: 'ADMIN', label: 'Admin' },
  { value: 'AP_CLERK', label: 'AP Clerk' },
  { value: 'APPROVER', label: 'Approver' },
  { value: 'FINANCE', label: 'Finance' },
];

export const INVOICE_STATUSES = [
  'UPLOADED', 'EXTRACTED', 'VALIDATED', 'MATCHED', 'MATCH_EXCEPTION', 'EXCEPTION',
  'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'PAYMENT_REQUESTED', 'SCHEDULED',
  'PAID', 'PAYMENT_FAILED', 'ON_HOLD', 'CANCELLED',
];

export const OCR_STATUSES = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'];

export const PAYMENT_STATUSES = ['PENDING_APPROVAL', 'APPROVED', 'SCHEDULED', 'PROCESSED', 'FAILED', 'CANCELLED'];

export const PAYMENT_METHODS = ['NEFT', 'RTGS', 'IMPS', 'CHEQUE', 'UPI'];

export const PO_STATUSES = ['OPEN', 'CLOSED', 'CANCELLED'];

export const VENDOR_STATUSES = ['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'];

export const APPROVAL_TASK_STATUSES = ['PENDING', 'APPROVED', 'REJECTED', 'ESCALATED', 'SKIPPED'];

export const ACCEPTED_UPLOAD_MIME = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/tiff': ['.tif', '.tiff'],
};
