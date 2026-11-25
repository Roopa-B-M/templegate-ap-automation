import Chip from '@mui/material/Chip';
import { humanize } from '../utils/format';

const STATUS_COLOR_MAP = {
  // success
  APPROVED: 'success',
  MATCHED: 'success',
  PAID: 'success',
  PROCESSED: 'success',
  VALIDATED: 'success',
  COMPLETED: 'success',
  PASS: 'success',
  ACTIVE: 'success',
  // warning
  PENDING: 'warning',
  PENDING_APPROVAL: 'warning',
  SCHEDULED: 'warning',
  UPLOADED: 'warning',
  EXTRACTED: 'warning',
  PAYMENT_REQUESTED: 'warning',
  ON_HOLD: 'warning',
  WARN: 'warning',
  PARTIAL: 'warning',
  // error
  EXCEPTION: 'error',
  MATCH_EXCEPTION: 'error',
  REJECTED: 'error',
  FAILED: 'error',
  PAYMENT_FAILED: 'error',
  FAIL: 'error',
  MISMATCH: 'error',
  ESCALATED: 'error',
  // default
  CANCELLED: 'default',
  DRAFT: 'default',
  CLOSED: 'default',
  SKIPPED: 'default',
  INACTIVE: 'default',
  // info
  OPEN: 'info',
  PROCESSING: 'info',
};

export default function StatusChip({ status, display, size = 'small' }) {
  if (!status) return null;
  const color = STATUS_COLOR_MAP[status] || 'default';
  return <Chip size={size} color={color} label={display || humanize(status)} />;
}
