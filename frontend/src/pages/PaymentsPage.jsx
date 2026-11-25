import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  Link,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import PaidIcon from '@mui/icons-material/Paid';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import ScheduleIcon from '@mui/icons-material/Schedule';
import api from '../api/client';
import ConfirmDialog from '../components/ConfirmDialog';
import DataTable from '../components/DataTable';
import KpiCard from '../components/KpiCard';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormTextField } from '../components/FormControls';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import useDebouncedValue from '../hooks/useDebouncedValue';
import usePagedList from '../hooks/usePagedList';
import { PAYMENT_METHODS, PAYMENT_STATUSES } from '../utils/constants';
import { downloadBlob } from '../utils/download';
import { formatCurrency, formatDate, getApiErrorMessage, humanize, todayStr } from '../utils/format';

export default function PaymentsPage() {
  const { isAdmin, isFinance } = useAuth();
  const snackbar = useSnackbar();
  const [filters, setFilters] = useState({ status: '', search: '' });
  const debouncedSearch = useDebouncedValue(filters.search, 400);
  const [kpi, setKpi] = useState(null);
  const [kpiError, setKpiError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [adviceLoadingId, setAdviceLoadingId] = useState(null);
  const [confirmState, setConfirmState] = useState(null);

  // Banking integration state
  const [bankMode, setBankMode] = useState(null);
  const [selectedPayments, setSelectedPayments] = useState([]);
  const [bankFileLoading, setBankFileLoading] = useState(false);
  const [reconcileLoading, setReconcileLoading] = useState(false);
  const [reconcileResult, setReconcileResult] = useState(null);
  const statementInputRef = useRef(null);

  // Create payment dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ invoice_id: '', method: 'NEFT', scheduled_date: '' });
  const [approvedInvoices, setApprovedInvoices] = useState([]);
  const [createSubmitting, setCreateSubmitting] = useState(false);

  // Schedule dialog
  const [scheduleState, setScheduleState] = useState(null);
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleSubmitting, setScheduleSubmitting] = useState(false);

  const effectiveFilters = useMemo(
    () => ({ ...filters, search: debouncedSearch }),
    [filters, debouncedSearch]
  );

  const fetchFn = useCallback(
    (page, pageSize) => {
      const params = { page: page + 1, pageSize };
      Object.entries(effectiveFilters).forEach(([key, value]) => {
        if (value !== '' && value !== null && value !== undefined) params[key] = value;
      });
      return api.get('/payments', { params }).then((res) => res.data);
    },
    [effectiveFilters]
  );

  const list = usePagedList(fetchFn, [effectiveFilters]);

  useEffect(() => {
    api
      .get('/analytics/dashboard')
      .then((res) => {
        setKpi(res.data?.payments || null);
        setKpiError(null);
      })
      .catch((e) => setKpiError(e));
    api
      .get('/payments/bank-mode')
      .then((res) => setBankMode(res.data))
      .catch(() => setBankMode(null));
  }, []);

  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));
  const canManage = isFinance || isAdmin;

  const toggleSelected = (id, enabled) =>
    setSelectedPayments((prev) =>
      enabled ? (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id])
              : prev.filter((v) => v !== id)
    );

  const downloadBankFile = async () => {
    if (selectedPayments.length === 0) {
      snackbar.error('Select at least one SCHEDULED payment first');
      return;
    }
    setBankFileLoading(true);
    try {
      const res = await api.post('/payments/bank-file', { payment_ids: selectedPayments }, { responseType: 'blob' });
      const disposition = res.headers?.['content-disposition'] || '';
      const match = disposition.match(/filename="?([^";]+)"?/);
      downloadBlob(res.data, match ? match[1] : 'bank-payment-instructions.csv');
      snackbar.success('Bank payment instruction file downloaded (upload it to your bank portal)');
      setSelectedPayments([]);
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setBankFileLoading(false);
    }
  };

  const uploadStatement = async (file) => {
    if (!file) return;
    setReconcileLoading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const { data } = await api.post('/payments/reconcile-statement', form,
        { headers: { 'Content-Type': 'multipart/form-data' } });
      setReconcileResult(data);
      list.reload();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setReconcileLoading(false);
      if (statementInputRef.current) statementInputRef.current.value = '';
    }
  };

  const runPaymentAction = async (row, path, successMessage) => {
    setActionLoading(true);
    try {
      const { data } = await api.post(`/payments/${row.id}/${path}`);
      if (path === 'process' && data?.status === 'FAILED') {
        snackbar.error(`Payment failed${data.failure_reason ? `: ${data.failure_reason}` : ''}`);
      } else {
        snackbar.success(successMessage);
      }
      list.reload();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setActionLoading(false);
      setConfirmState(null);
    }
  };

  const downloadAdvice = async (row) => {
    setAdviceLoadingId(row.id);
    try {
      const res = await api.get(`/payments/${row.id}/advice`, { responseType: 'blob' });
      downloadBlob(res.data, `payment-advice-${row.payment_number}.pdf`);
      snackbar.success('Payment advice downloaded');
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setAdviceLoadingId(null);
    }
  };

  const openCreate = () => {
    setCreateForm({ invoice_id: '', method: 'NEFT', scheduled_date: '' });
    setCreateOpen(true);
    api
      .get('/invoices', { params: { status: 'APPROVED', pageSize: 100 } })
      .then((res) => setApprovedInvoices(res.data.results || []))
      .catch((e) => snackbar.error(getApiErrorMessage(e)));
  };

  const submitCreate = async () => {
    if (!createForm.invoice_id) {
      snackbar.error('Select an approved invoice');
      return;
    }
    if (!createForm.method) {
      snackbar.error('Select a payment method');
      return;
    }
    setCreateSubmitting(true);
    try {
      await api.post('/payments', {
        invoice_id: Number(createForm.invoice_id),
        method: createForm.method,
        scheduled_date: createForm.scheduled_date || undefined,
      });
      snackbar.success('Payment request created');
      setCreateOpen(false);
      list.reload();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setCreateSubmitting(false);
    }
  };

  const submitSchedule = async () => {
    if (!scheduleDate) {
      snackbar.error('Pick a scheduled date');
      return;
    }
    setScheduleSubmitting(true);
    try {
      await api.post(`/payments/${scheduleState.id}/schedule`, { scheduled_date: scheduleDate });
      snackbar.success('Payment scheduled');
      setScheduleState(null);
      list.reload();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setScheduleSubmitting(false);
    }
  };

  const columns = [
    {
      id: 'select',
      label: '',
      align: 'center',
      hideOnMobile: true,
      render: (row) => (
        <Checkbox
          size="small"
          color="primary"
          disabled={!canManage || row.status !== 'SCHEDULED'}
          checked={selectedPayments.includes(row.id)}
          onChange={(e) => toggleSelected(row.id, e.target.checked)}
          inputProps={{ 'aria-label': `Select ${row.payment_number}` }}
        />
      ),
    },
    {
      id: 'payment_number',
      label: 'Payment #',
      render: (row) => <Typography fontWeight={600}>{row.payment_number}</Typography>,
    },
    {
      id: 'invoice',
      label: 'Invoice',
      render: (row) =>
        row.invoice ? (
          <Link component={RouterLink} to={`/invoices/${row.invoice.id}`} fontWeight={600}>
            {row.invoice.invoice_number}
          </Link>
        ) : (
          '—'
        ),
    },
    { id: 'vendor', label: 'Vendor', render: (row) => row.invoice?.vendor_name || '—' },
    {
      id: 'amount',
      label: 'Amount',
      align: 'right',
      render: (row) => formatCurrency(row.amount),
    },
    { id: 'method', label: 'Method', render: (row) => row.method_display || humanize(row.method) },
    {
      id: 'status',
      label: 'Status',
      render: (row) => (
        <Stack spacing={0.5}>
          <StatusChip status={row.status} display={row.status_display} />
          {row.is_reconciled && (
            <Chip size="small" color="success" variant="outlined" icon={<FactCheckIcon sx={{ fontSize: 14 }} />} label="Reconciled" />
          )}
          {row.status === 'FAILED' && row.failure_reason && (
            <Typography variant="caption" color="error" sx={{ maxWidth: 180 }}>
              {row.failure_reason}
            </Typography>
          )}
          {row.status === 'PROCESSED' && row.bank_reference && (
            <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 180 }}>
              Ref: {row.bank_reference}
            </Typography>
          )}
        </Stack>
      ),
    },
    { id: 'scheduled_date', label: 'Scheduled', render: (row) => formatDate(row.scheduled_date) },
    { id: 'processed_date', label: 'Processed', render: (row) => formatDate(row.processed_date) },
    { id: 'requested_by', label: 'Requested By', render: (row) => row.requested_by_username || '—' },
    {
      id: 'actions',
      label: 'Actions',
      align: 'right',
      render: (row) => {
        const actions = [];
        if (canManage && row.status === 'PENDING_APPROVAL') {
          actions.push(
            <Button
              key="approve"
              size="small"
              variant="outlined"
              color="success"
              onClick={() =>
                setConfirmState({
                  title: 'Approve payment',
                  message: `Approve payment ${row.payment_number} for ${formatCurrency(row.amount)}?`,
                  confirmText: 'Approve',
                  action: () => runPaymentAction(row, 'approve', 'Payment approved'),
                })
              }
            >
              Approve
            </Button>
          );
        }
        if (canManage && row.status === 'APPROVED') {
          actions.push(
            <Button
              key="schedule"
              size="small"
              variant="outlined"
              onClick={() => {
                setScheduleDate(row.scheduled_date || todayStr());
                setScheduleState(row);
              }}
            >
              Schedule
            </Button>
          );
        }
        if (canManage && (row.status === 'SCHEDULED' || row.status === 'FAILED')) {
          actions.push(
            <Button
              key="process"
              size="small"
              variant="contained"
              onClick={() =>
                setConfirmState({
                  title: row.status === 'FAILED' ? 'Retry payment' : 'Process payment',
                  message:
                    row.status === 'FAILED'
                      ? `Retry processing payment ${row.payment_number}?`
                      : `Send payment ${row.payment_number} for processing? The bank gateway may accept or fail it.`,
                  confirmText: row.status === 'FAILED' ? 'Retry' : 'Process',
                  action: () =>
                    runPaymentAction(
                      row,
                      'process',
                      row.status === 'FAILED' ? 'Payment retry submitted' : 'Payment processed'
                    ),
                })
              }
            >
              {row.status === 'FAILED' ? 'Retry' : 'Process'}
            </Button>
          );
        }
        if (canManage && (row.status === 'APPROVED' || row.status === 'SCHEDULED')) {
          actions.push(
            <Button
              key="cancel"
              size="small"
              color="error"
              onClick={() =>
                setConfirmState({
                  title: 'Cancel payment',
                  message: `Cancel payment ${row.payment_number}? The linked invoice returns to the approved state.`,
                  confirmText: 'Cancel payment',
                  color: 'error',
                  action: () => runPaymentAction(row, 'cancel', 'Payment cancelled'),
                })
              }
            >
              Cancel
            </Button>
          );
        }
        if (row.status === 'PROCESSED') {
          actions.push(
            <Tooltip key="advice" title="Download payment advice (PDF)">
              <IconButton
                size="small"
                color="primary"
                onClick={() => downloadAdvice(row)}
                disabled={adviceLoadingId === row.id}
                aria-label="Download advice"
              >
                <FileDownloadIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          );
        }
        if (actions.length === 0) return '—';
        return (
          <Stack direction="row" spacing={0.5} justifyContent="flex-end" flexWrap="wrap" useFlexGap>
            {actions}
          </Stack>
        );
      },
    },
  ];

  return (
    <Box>
      <PageHeader
        title="Payments"
        subtitle="Payment requests, scheduling, bank processing and advice downloads."
        actions={
          canManage && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
              New payment
            </Button>
          )
        }
      />

      {bankMode && (
        <Alert
          icon={<AccountBalanceIcon fontSize="inherit" />}
          severity={bankMode.mode === 'simulated' ? 'info' : 'success'}
          sx={{ mb: 2 }}
        >
          <strong>{bankMode.mode === 'simulated'
            ? 'Bank integration: SIMULATED mode.'
            : 'Bank integration: FILE mode.'}</strong>{' '}
          {bankMode.note}{' '}
          {canManage && (
            <>Select scheduled payments below and use <strong>Bank file</strong> to export a
            NEFT/RTGS bulk instruction CSV; use <strong>Reconcile statement</strong> to upload the
            bank's returned UTR statement.</>
          )}
        </Alert>
      )}

      {kpiError ? (
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Payment KPIs are unavailable right now.
          </Typography>
        </Box>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gap: 2,
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' },
            mb: 3,
          }}
        >
          <KpiCard
            title="Processed Amount"
            value={formatCurrency(kpi?.processed_amount)}
            sub={`${kpi?.processed_count ?? 0} payment(s) processed`}
            icon={<PaidIcon />}
            color="success"
            loading={!kpi}
          />
          <KpiCard
            title="Pending Approval"
            value={kpi?.pending_count ?? 0}
            sub="payment request(s) awaiting finance approval"
            icon={<PendingActionsIcon />}
            color="warning"
            loading={!kpi}
          />
          <KpiCard
            title="Scheduled"
            value={kpi?.scheduled_count ?? 0}
            sub="payment(s) scheduled for processing"
            icon={<ScheduleIcon />}
            color="info"
            loading={!kpi}
          />
        </Box>
      )}

      <Grid container spacing={2} sx={{ mb: 2 }} alignItems="center">
        <Grid item xs={12} sm={6} md={3}>
          <FormSelect
            label="Status"
            value={filters.status}
            onChange={(e) => setFilter('status', e.target.value)}
            options={PAYMENT_STATUSES.map((s) => ({ value: s, label: humanize(s) }))}
            emptyOption="All statuses"
          />
        </Grid>
        <Grid item xs={12} sm={9} md={4}>
          <TextField fullWidth label="Search" value={filters.search} onChange={(e) => setFilter('search', e.target.value)} />
        </Grid>
        <Grid item xs={12} sm={3} md={2}>
          <Button color="inherit" onClick={() => setFilters({ status: '', search: '' })} sx={{ minWidth: 0 }}>
            Clear
          </Button>
        </Grid>
      </Grid>

      {canManage && (
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1.5}
          alignItems={{ sm: 'center' }}
          sx={{ mb: 2, width: '100%' }}
        >
          <Button
            variant="outlined"
            startIcon={<AccountBalanceIcon />}
            onClick={downloadBankFile}
            disabled={bankFileLoading || selectedPayments.length === 0}
          >
            {bankFileLoading ? 'Generating…' : `Bank file (${selectedPayments.length} selected)`}
          </Button>
          <Button
            variant="outlined"
            startIcon={<FactCheckIcon />}
            onClick={() => statementInputRef.current?.click()}
            disabled={reconcileLoading}
          >
            {reconcileLoading ? 'Reconciling…' : 'Reconcile statement'}
          </Button>
          <input
            ref={statementInputRef}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(e) => uploadStatement(e.target.files?.[0])}
          />
          <Typography variant="caption" color="text.secondary">
            Select SCHEDULED payments to export a bulk NEFT/RTGS instruction CSV,
            or upload the bank statement (UTR, amount, date) to reconcile.
          </Typography>
        </Stack>
      )}

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
        emptyTitle="No payments found"
        emptySubtitle="Create a payment request from an approved invoice to get started."
        minWidth={1080}
      />

      <ConfirmDialog
        open={Boolean(confirmState)}
        title={confirmState?.title || 'Confirm'}
        message={confirmState?.message}
        confirmText={confirmState?.confirmText || 'Confirm'}
        confirmColor={confirmState?.color || 'primary'}
        loading={actionLoading}
        onClose={() => {
          if (!actionLoading) setConfirmState(null);
        }}
        onConfirm={() => {
          if (confirmState?.action) confirmState.action();
        }}
      />

      {/* Create payment dialog */}
      <Dialog open={createOpen} onClose={() => !createSubmitting && setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New payment request</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormSelect
              label="Approved invoice *"
              value={createForm.invoice_id}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, invoice_id: e.target.value }))}
              options={approvedInvoices.map((inv) => ({
                value: inv.id,
                label: `${inv.invoice_number} · ${inv.vendor_name || inv.vendor?.name || '—'} · ${formatCurrency(inv.total_amount)}`,
              }))}
              emptyOption={approvedInvoices.length === 0 ? 'No approved invoices available' : 'Select invoice'}
              disabled={approvedInvoices.length === 0}
            />
            <FormSelect
              label="Method *"
              value={createForm.method}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, method: e.target.value }))}
              options={PAYMENT_METHODS.map((m) => ({ value: m, label: m }))}
            />
            <FormTextField
              label="Scheduled date (optional)"
              type="date"
              value={createForm.scheduled_date}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, scheduled_date: e.target.value }))}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setCreateOpen(false)} disabled={createSubmitting} color="inherit">
            Cancel
          </Button>
          <Button variant="contained" onClick={submitCreate} disabled={createSubmitting}>
            {createSubmitting ? 'Creating…' : 'Create payment'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Schedule dialog */}
      <Dialog open={Boolean(scheduleState)} onClose={() => !scheduleSubmitting && setScheduleState(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Schedule payment</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            {scheduleState?.payment_number} · {formatCurrency(scheduleState?.amount)}
          </Typography>
          <FormTextField label="Scheduled date *" type="date" value={scheduleDate} onChange={(e) => setScheduleDate(e.target.value)} autoFocus />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setScheduleState(null)} disabled={scheduleSubmitting} color="inherit">
            Cancel
          </Button>
          <Button variant="contained" onClick={submitSchedule} disabled={scheduleSubmitting || !scheduleDate}>
            {scheduleSubmitting ? 'Scheduling…' : 'Schedule'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bank statement reconciliation result */}
      <Dialog open={Boolean(reconcileResult)} onClose={() => setReconcileResult(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Statement reconciliation result</DialogTitle>
        <DialogContent>
          <Alert severity={reconcileResult?.matched?.length ? 'success' : 'warning'} sx={{ mb: 2 }}>
            {reconcileResult?.detail}
          </Alert>
          {(reconcileResult?.matched?.length || 0) > 0 && (
            <>
              <Typography variant="subtitle2" gutterBottom>Matched payments</Typography>
              <Stack spacing={0.5} sx={{ mb: 2 }}>
                {reconcileResult.matched.map((m) => (
                  <Typography key={`${m.row}-${m.payment_id}`} variant="body2">
                    Row {m.row}: <strong>{m.payment_number}</strong> · UTR {m.utr} · {formatCurrency(m.amount)}
                  </Typography>
                ))}
              </Stack>
            </>
          )}
          {(reconcileResult?.unmatched?.length || 0) > 0 && (
            <>
              <Typography variant="subtitle2" gutterBottom>Unmatched rows (no scheduled payment found)</Typography>
              <Stack spacing={0.5}>
                {reconcileResult.unmatched.map((u) => (
                  <Typography key={u.row} variant="body2" color="error">
                    Row {u.row}: {u.utr ? `UTR ${u.utr} · ` : ''}{u.amount ? formatCurrency(u.amount) : ''} — {u.reason}
                  </Typography>
                ))}
              </Stack>
            </>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button variant="contained" onClick={() => setReconcileResult(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
