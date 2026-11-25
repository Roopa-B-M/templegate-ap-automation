import dayjs from 'dayjs';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  Link,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import PriorityHighIcon from '@mui/icons-material/PriorityHigh';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import api from '../api/client';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormTextField } from '../components/FormControls';
import { useSnackbar } from '../context/SnackbarContext';
import usePagedList from '../hooks/usePagedList';
import { formatCurrency, formatDate, formatDateTime, getApiErrorMessage } from '../utils/format';

function ActionDialog({ state, onClose }) {
  const snackbar = useSnackbar();
  const [comments, setComments] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!state) return null;
  const isReject = state.action === 'reject';

  const submit = async () => {
    if (isReject && !comments.trim()) {
      snackbar.error('Comments are required when rejecting');
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/approvals/${state.task.id}/action`, { action: state.action, comments: comments.trim() });
      snackbar.success(isReject ? 'Invoice rejected' : 'Invoice approved');
      onClose(true);
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onClose={() => onClose(false)} maxWidth="xs" fullWidth>
      <DialogTitle>{isReject ? 'Reject invoice' : 'Approve invoice'}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {state.task.invoice?.invoice_number} · {formatCurrency(state.task.invoice?.total_amount)}
        </Typography>
        <FormTextField
          label={isReject ? 'Comments *' : 'Comments'}
          value={comments}
          onChange={(e) => setComments(e.target.value)}
          multiline
          minRows={3}
          autoFocus
        />
      </DialogContent>
      <DialogActions sx={{ px: { xs: 2, sm: 3 }, pb: 2, flexDirection: { xs: 'column', sm: 'row' }, gap: { xs: 1, sm: 0 } }}>
        <Button onClick={() => onClose(false)} disabled={submitting} color="inherit" fullWidth sx={{ display: { xs: 'block', sm: 'none' } }}>
          Cancel
        </Button>
        <Button
          variant="contained"
          color={isReject ? 'error' : 'success'}
          startIcon={isReject ? <ThumbDownIcon /> : <ThumbUpIcon />}
          onClick={submit}
          disabled={submitting || (isReject && !comments.trim())}
          fullWidth
        >
          {isReject ? 'Reject' : 'Approve'}
        </Button>
        <Button onClick={() => onClose(false)} disabled={submitting} color="inherit" sx={{ display: { xs: 'none', sm: 'inline-flex' } }}>
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function OverdueMark({ row }) {
  const overdue = row.due_at && dayjs(row.due_at).isBefore(dayjs()) && row.status === 'PENDING';
  if (!overdue) return null;
  return (
    <Tooltip title="Overdue">
      <PriorityHighIcon fontSize="small" color="error" />
    </Tooltip>
  );
}

function TaskCard({ row, onAction }) {
  const pending = row.status === 'PENDING';
  return (
    <Card variant="outlined">
      <CardContent sx={{ p: { xs: 1.75, sm: 2 } }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
          <Box sx={{ minWidth: 0 }}>
            <Link component={RouterLink} to={`/invoices/${row.invoice?.id}`} fontWeight={700}>
              {row.invoice?.invoice_number || '—'}
            </Link>
            <Typography variant="body2" color="text.secondary" noWrap>
              {row.invoice?.vendor_name || '—'}
            </Typography>
          </Box>
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flexShrink: 0 }}>
            {row.escalated && (
              <Tooltip title="Escalated due to SLA breach">
                <Chip size="small" color="error" icon={<PriorityHighIcon sx={{ fontSize: 14 }} />} label="Escalated" />
              </Tooltip>
            )}
            <StatusChip status={row.status} display={row.status_display} />
          </Stack>
        </Stack>

        <Divider sx={{ my: 1.25 }} />

        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h6" fontWeight={700} color="text.primary">
            {formatCurrency(row.invoice?.total_amount)}
          </Typography>
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Chip size="small" variant="outlined" color={row.is_parallel ? 'info' : 'default'}
                  label={row.is_parallel ? 'Parallel' : 'Sequential'} />
            <Chip size="small" variant="outlined" label={`Level ${row.level}`} />
          </Stack>
        </Stack>

        <Stack direction="row" justifyContent="space-between" sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Invoice date {formatDate(row.invoice?.invoice_date)}
          </Typography>
          <Stack direction="row" spacing={0.5} alignItems="center">
            <OverdueMark row={row} />
            <Typography variant="caption" color={row.due_at && dayjs(row.due_at).isBefore(dayjs()) && row.status === 'PENDING' ? 'error' : 'text.secondary'}>
              Due {formatDateTime(row.due_at)}
            </Typography>
            {row.reminder_count > 0 && (
              <Typography variant="caption" color="text.secondary">
                · {row.reminder_count} reminder(s)
              </Typography>
            )}
          </Stack>
        </Stack>

        {row.comments && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            Comments: {row.comments}
          </Typography>
        )}

        {pending && (
          <Stack direction="row" spacing={1.5} sx={{ mt: 1.75 }}>
            <Button
              fullWidth
              size="large"
              variant="contained"
              color="success"
              startIcon={<ThumbUpIcon />}
              onClick={() => onAction({ task: row, action: 'approve' })}
            >
              Approve
            </Button>
            <Button
              fullWidth
              size="large"
              variant="contained"
              color="error"
              startIcon={<ThumbDownIcon />}
              onClick={() => onAction({ task: row, action: 'reject' })}
            >
              Reject
            </Button>
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

export default function ApprovalsPage() {
  const snackbar = useSnackbar();
  const [tab, setTab] = useState('PENDING');
  const [actionState, setActionState] = useState(null);

  const fetchFn = useCallback(
    (page, pageSize) => {
      const params = { page: page + 1, pageSize };
      if (tab === 'PENDING') params.status = 'PENDING';
      return api.get('/approvals', { params }).then((res) => res.data);
    },
    [tab]
  );

  const list = usePagedList(fetchFn, [tab], { pageSize: 10 });

  const columns = [
    {
      id: 'invoice',
      label: 'Invoice',
      render: (row) => (
        <Link component={RouterLink} to={`/invoices/${row.invoice?.id}`} fontWeight={600}>
          {row.invoice?.invoice_number || '—'}
        </Link>
      ),
    },
    { id: 'vendor', label: 'Vendor', render: (row) => row.invoice?.vendor_name || '—' },
    {
      id: 'amount',
      label: 'Amount',
      align: 'right',
      render: (row) => formatCurrency(row.invoice?.total_amount),
    },
    { id: 'invoice_date', label: 'Invoice Date', render: (row) => formatDate(row.invoice?.invoice_date) },
    { id: 'level', label: 'Level', align: 'center' },
    {
      id: 'parallel',
      label: 'Mode',
      render: (row) =>
        row.is_parallel ? (
          <Tooltip title="Parallel — all approvers at this level must approve">
            <Chip size="small" variant="outlined" color="info" label="Parallel" />
          </Tooltip>
        ) : (
          <Chip size="small" variant="outlined" label="Sequential" />
        ),
    },
    {
      id: 'approver',
      label: 'Approver',
      render: (row) => row.approver?.username || row.approver_role || '—',
    },
    {
      id: 'due',
      label: 'Due',
      render: (row) => {
        const overdue = row.due_at && dayjs(row.due_at).isBefore(dayjs()) && row.status === 'PENDING';
        return (
          <Stack direction="row" spacing={0.5} alignItems="center">
            <OverdueMark row={row} />
            <Typography variant="body2" color={overdue ? 'error' : 'text.primary'}>
              {formatDateTime(row.due_at)}
            </Typography>
            {row.reminder_count > 0 && (
              <Typography variant="caption" color="text.secondary">
                ({row.reminder_count} reminder(s))
              </Typography>
            )}
          </Stack>
        );
      },
    },
    {
      id: 'status',
      label: 'Status',
      render: (row) => (
        <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
          {row.escalated && (
            <Tooltip title="Escalated due to SLA breach">
              <Chip size="small" color="error" icon={<PriorityHighIcon sx={{ fontSize: 14 }} />} label="Escalated" />
            </Tooltip>
          )}
          <StatusChip status={row.status} display={row.status_display} />
        </Stack>
      ),
    },
    {
      id: 'comments',
      label: 'Comments',
      render: (row) =>
        row.comments ? (
          <Tooltip title={row.comments}>
            <Typography
              variant="body2"
              sx={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {row.comments}
            </Typography>
          </Tooltip>
        ) : (
          '—'
        ),
    },
    {
      id: 'actions',
      label: 'Actions',
      align: 'right',
      render: (row) =>
        tab === 'PENDING' && row.status === 'PENDING' ? (
          <Stack direction="row" spacing={0.5} justifyContent="flex-end">
            <Button
              size="small"
              variant="outlined"
              color="success"
              startIcon={<ThumbUpIcon />}
              onClick={() => setActionState({ task: row, action: 'approve' })}
            >
              Approve
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="error"
              startIcon={<ThumbDownIcon />}
              onClick={() => setActionState({ task: row, action: 'reject' })}
            >
              Reject
            </Button>
          </Stack>
        ) : row.status === 'APPROVED' && row.approved_at ? (
          <Typography variant="caption" color="text.secondary">
            {formatDateTime(row.approved_at)}
          </Typography>
        ) : (
          '—'
        ),
    },
  ];

  const totalPages = Math.max(1, Math.ceil(list.count / list.pageSize));

  return (
    <Box>
      <PageHeader
        title="Approvals"
        subtitle="Invoice approval tasks assigned to you — approve or reject with comments."
        actions={
          tab === 'PENDING' ? (
            <Chip icon={<CheckCircleIcon />} color="warning" variant="outlined" label={`${list.count} pending`} />
          ) : null
        }
      />

      <Box sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_e, value) => setTab(value)}>
          <Tab value="PENDING" label="Pending" />
          <Tab value="HISTORY" label="History" />
        </Tabs>
        <Divider />
      </Box>

      {/* Mobile-first: card list (visible below md) */}
      <Box sx={{ display: { xs: 'block', md: 'none' } }}>
        {list.loading ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
            Loading…
          </Typography>
        ) : list.rows.length === 0 ? (
          <Card variant="outlined">
            <CardContent sx={{ textAlign: 'center', py: 5 }}>
              <Typography variant="subtitle1" fontWeight={700}>
                {tab === 'PENDING' ? 'No pending approvals' : 'No approval history'}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {tab === 'PENDING'
                  ? 'Invoices submitted for approval will appear here.'
                  : 'Approved and rejected tasks will appear here.'}
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Stack spacing={2}>
            {list.rows.map((row) => (
              <TaskCard key={row.id} row={row} onAction={setActionState} />
            ))}
          </Stack>
        )}
        {list.count > 0 && (
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Page {list.page + 1} of {totalPages} · {list.count} task(s)
            </Typography>
            <Stack direction="row" spacing={1}>
              <IconButton size="small" disabled={list.page === 0} onClick={() => list.setPage(list.page - 1)} aria-label="Previous page">
                <ChevronLeftIcon />
              </IconButton>
              <IconButton
                size="small"
                disabled={list.page + 1 >= totalPages}
                onClick={() => list.setPage(list.page + 1)}
                aria-label="Next page"
              >
                <ChevronRightIcon />
              </IconButton>
            </Stack>
          </Stack>
        )}
      </Box>

      {/* Desktop table (md and up) */}
      <Box sx={{ display: { xs: 'none', md: 'block' } }}>
        <DataTable
          columns={columns}
          rows={list.rows}
          count={list.count}
          page={list.page}
          pageSize={list.pageSize}
          onPageChange={list.setPage}
          onPageSizeChange={list.changePageSize}
          loading={list.loading}
          error={list.error}
          onRetry={list.reload}
          emptyTitle={tab === 'PENDING' ? 'No pending approvals' : 'No approval history'}
          emptySubtitle={
            tab === 'PENDING'
              ? 'Invoices submitted for approval will appear here.'
              : 'Approved and rejected tasks will appear here.'
          }
          minWidth={1080}
        />
      </Box>

      <ActionDialog
        state={actionState}
        onClose={(refresh) => {
          setActionState(null);
          if (refresh) list.reload();
        }}
      />
    </Box>
  );
}
