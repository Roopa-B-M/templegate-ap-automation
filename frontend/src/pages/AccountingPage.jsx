import dayjs from 'dayjs';
import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  Link,   
  Paper,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import RefreshIcon from '@mui/icons-material/Refresh';
import SettingsIcon from '@mui/icons-material/Settings';
import api from '../api/client';
import DataTable from '../components/DataTable';
import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormSwitch, FormTextField } from '../components/FormControls';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import usePagedList from '../hooks/usePagedList';
import { downloadBlob } from '../utils/download';
import { formatCurrency, formatDateTime, getApiErrorMessage, todayStr } from '../utils/format';

const SYNC_STATUSES = ['NOT_SYNCED', 'SYNCED', 'FAILED'];
const EXPORT_FORMATS = [
  { value: 'CSV', label: 'Generic CSV (any accounting system)' },
  { value: 'JSON', label: 'Generic JSON (REST-capable ERP)' },
  { value: 'TALLY_XML', label: 'Tally XML purchase vouchers' },
];

function SyncLogStatusChip({ row }) {
  const map = { SYNCED: 'success', FAILED: 'error', NOT_SYNCED: 'default' };
  return (
    <Chip
      size="small"
      color={map[row.status] || 'default'}
      variant={row.status === 'NOT_SYNCED' ? 'outlined' : 'filled'}
      label={row.status_display || row.status}
    />
  );
}

function BulkExportCard() {
  const snackbar = useSnackbar();
  const [form, setForm] = useState({
    date_from: dayjs().startOf('year').format('YYYY-MM-DD'),
    date_to: todayStr(),
    format: 'CSV',
  });
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      const res = await api.post(
        '/accounting/bulk-export',
        { date_from: form.date_from, date_to: form.date_to, format: form.format },
        { responseType: 'blob' }
      );
      const disposition = res.headers?.['x-export-filename'] || `erp-export.${form.format.toLowerCase()}`;
      downloadBlob(res.data, disposition);
      const posted = res.headers?.['x-sync-posted'];
      const failed = res.headers?.['x-sync-failed'];
      snackbar.success(`Export downloaded — ${posted} voucher(s) posted, ${failed} failed (see Sync log)`);
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
      <Typography variant="h6" fontWeight={700} gutterBottom>
        Bulk export &amp; posting
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Exports every APPROVED / PAID invoice in the date range as purchase vouchers, posts each
        one to the ERP connector and records a sync log entry per invoice. ERP posting is
        simulated locally — no live ERP connection is made.
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <FormTextField
            label="Date from"
            type="date"
            value={form.date_from}
            onChange={(e) => setForm((prev) => ({ ...prev, date_from: e.target.value }))}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <FormTextField
            label="Date to"
            type="date"
            value={form.date_to}
            onChange={(e) => setForm((prev) => ({ ...prev, date_to: e.target.value }))}
          />
        </Grid>
        <Grid item xs={12} sm={8} md={4}>
          <FormSelect
            label="Format"
            value={form.format}
            onChange={(e) => setForm((prev) => ({ ...prev, format: e.target.value }))}
            options={EXPORT_FORMATS}
          />
        </Grid>
        <Grid item xs={12} sm={4} md={2}>
          <Button
            fullWidth
            variant="contained"
            startIcon={<CloudUploadIcon />}
            onClick={submit}
            disabled={loading}
            sx={{ height: 40 }}
          >
            {loading ? 'Exporting…' : 'Export & post'}
          </Button>
        </Grid>
      </Grid>
    </Paper>
  );
}

function MappingDialog({ open, initial, onClose, onSaved }) {
  const snackbar = useSnackbar();
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(initial || {
        name: '', vendor: '', vendor_name: '', expense_account: 'Purchase Account',
        cgst_account: 'Input CGST', sgst_account: 'Input SGST', igst_account: 'Input IGST',
        payable_account: 'Accounts Payable', is_active: true,
      });
    }
  }, [open, initial]);

  if (!form) return null;
  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const save = async () => {
    if (!form.name?.trim()) {
      snackbar.error('Name is required');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        vendor: form.vendor || null,
        expense_account: form.expense_account,
        cgst_account: form.cgst_account || '',
        sgst_account: form.sgst_account || '',
        igst_account: form.igst_account || '',
        payable_account: form.payable_account,
        is_active: form.is_active !== false,
      };
      if (form.id) await api.patch(`/accounting/mappings/${form.id}`, payload);
      else await api.post('/accounting/mappings', payload);
      snackbar.success(form.id ? 'Mapping updated' : 'Mapping created');
      onSaved();
      onClose();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!form.id) return;
    setSaving(true);
    try {
      await api.delete(`/accounting/mappings/${form.id}`);
      snackbar.success('Mapping deleted');
      onSaved();
      onClose();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={() => !saving && onClose()} maxWidth="sm" fullWidth>
      <DialogTitle>{form.id ? 'Edit GL account mapping' : 'New GL account mapping'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <FormTextField label="Name *" value={form.name} onChange={(e) => set('name', e.target.value)} />
          <FormTextField
            label="Vendor ID (empty = default mapping)"
            value={form.vendor ?? ''}
            type="number"
            onChange={(e) => set('vendor', e.target.value)}
            helperText={form.vendor_name || 'Leave empty to make this the default mapping for all vendors'}
          />
          <FormTextField label="Expense / purchase ledger *" value={form.expense_account} onChange={(e) => set('expense_account', e.target.value)} />
          <Grid container spacing={2}>
            <Grid item xs={6} sm={3}>
              <FormTextField label="Input CGST" value={form.cgst_account} onChange={(e) => set('cgst_account', e.target.value)} />
            </Grid>
            <Grid item xs={6} sm={3}>
              <FormTextField label="Input SGST" value={form.sgst_account} onChange={(e) => set('sgst_account', e.target.value)} />
            </Grid>
            <Grid item xs={6} sm={3}>
              <FormTextField label="Input IGST" value={form.igst_account} onChange={(e) => set('igst_account', e.target.value)} />
            </Grid>
            <Grid item xs={6} sm={3}>
              <FormTextField label="Payable ledger *" value={form.payable_account} onChange={(e) => set('payable_account', e.target.value)} />
            </Grid>
          </Grid>
          <FormSwitch label="Active" checked={form.is_active !== false} onChange={(checked) => set('is_active', checked)} />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {form.id && (
          <Button color="error" onClick={remove} disabled={saving} sx={{ mr: 'auto' }}>
            Delete
          </Button>
        )}
        <Button color="inherit" onClick={() => onClose()} disabled={saving}>Cancel</Button>
        <Button variant="contained" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save mapping'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function MappingSettings() {
  const snackbar = useSnackbar();
  const [mappings, setMappings] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => {
    api.get('/accounting/mappings', { params: { pageSize: 100 } })
      .then((res) => setMappings(res.data.results || []))
      .catch((e) => snackbar.error(getApiErrorMessage(e)));
  }, [snackbar]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
        <Stack direction="row" spacing={1} alignItems="center">
          <SettingsIcon color="primary" />
          <Typography variant="h6" fontWeight={700}>GL account mappings</Typography>
        </Stack>
        <Button variant="outlined" size="small" onClick={() => { setEditing(null); setDialogOpen(true); }}>
          New mapping
        </Button>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Configure which expense, input-GST and payable ledgers a purchase voucher posts to.
        A vendor-specific row overrides the default mapping for that vendor.
      </Typography>
      {!mappings ? (
        <Typography variant="body2" color="text.secondary">Loading mappings…</Typography>
      ) : mappings.length === 0 ? (
        <EmptyState
          title="No mappings configured"
          subtitle="ERP posting requires at least one default mapping (expense account + payable account)."
        />
      ) : (
        mappings.map((mapping, index) => (
          <Box key={mapping.id}>
            {index > 0 && <Divider sx={{ my: 1.5 }} />}
            <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={1}>
              <Box sx={{ minWidth: 0 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography fontWeight={700}>{mapping.name}</Typography>
                  {mapping.vendor
                    ? <Chip size="small" color="primary" variant="outlined" label={`Vendor #${mapping.vendor}`} />
                    : <Chip size="small" color="secondary" variant="outlined" label="Default" />}
                  {!mapping.is_active && <Chip size="small" label="Inactive" />}
                </Stack>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                  Expense: {mapping.expense_account} · Payable: {mapping.payable_account}
                  {mapping.cgst_account && ` · CGST: ${mapping.cgst_account}`}
                  {mapping.sgst_account && ` · SGST: ${mapping.sgst_account}`}
                  {mapping.igst_account && ` · IGST: ${mapping.igst_account}`}
                </Typography>
              </Box>
              <Button
                size="small"
                onClick={() => { setEditing(mapping); setDialogOpen(true); }}
              >
                Edit
              </Button>
            </Stack>
          </Box>
        ))
      )}
      <MappingDialog
        open={dialogOpen}
        initial={editing}
        onClose={() => setDialogOpen(false)}
        onSaved={load}
      />
    </Paper>
  );
}

export default function AccountingPage() {
  const { isAdmin, isFinance } = useAuth();
  const canManage = isAdmin || isFinance;
  const snackbar = useSnackbar();
  const [tab, setTab] = useState('SYNC_LOG');
  const [connector, setConnector] = useState(null);
  const [filters, setFilters] = useState({ status: '' });

  const fetchFn = useCallback(
    (page, pageSize) => {
      const params = { page: page + 1, pageSize };
      if (filters.status) params.status = filters.status;
      return api.get('/accounting/sync-logs', { params }).then((res) => res.data);
    },
    [filters.status]
  );
  const list = usePagedList(fetchFn, [filters.status]);

  useEffect(() => {
    api.get('/accounting/status')
      .then((res) => setConnector(res.data))
      .catch(() => setConnector(null));
  }, []);

  const retry = async (row) => {
    try {
      const { data } = await api.post(`/accounting/retry/${row.id}`);
      snackbar.success(data.detail || 'Retry succeeded');
      list.reload();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    }
  };

  const columns = [
    {
      id: 'invoice',
      label: 'Invoice',
      render: (row) => (
        <Link component={RouterLink} to={`/invoices/${row.invoice}`} fontWeight={600}>
          {row.invoice_number || `#${row.invoice}`}
        </Link>
      ),
    },
    { id: 'vendor', label: 'Vendor', render: (row) => row.vendor_name || '—' },
    { id: 'invoice_total', label: 'Amount', align: 'right', render: (row) => formatCurrency(row.invoice_total) },
    { id: 'connector', label: 'Connector', render: (row) => row.connector },
    { id: 'format', label: 'Format', render: (row) => row.format_display || row.format },
    { id: 'status', label: 'Status', render: (row) => <SyncLogStatusChip row={row} /> },
    {
      id: 'erp_reference',
      label: 'ERP reference',
      render: (row) => row.erp_reference || (row.error ? (
        <Tooltip title={row.error}>
          <Typography variant="caption" color="error" sx={{ display: 'inline-block', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {row.error}
          </Typography>
        </Tooltip>
      ) : '—'),
    },
    { id: 'created_at', label: 'Requested', render: (row) => formatDateTime(row.created_at) },
    {
      id: 'actions',
      label: 'Actions',
      align: 'right',
      render: (row) => canManage && row.status === 'FAILED' ? (
        <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={() => retry(row)}>
          Retry
        </Button>
      ) : row.posted_at ? formatDateTime(row.posted_at) : '—',
    },
  ];

  return (
    <Box>
      <PageHeader
        title="Accounting / ERP"
        subtitle="Post approved invoices to the accounting system and monitor every sync."
        actions={connector && (
          <Chip
            icon={<DoneAllIcon />}
            color="warning"
            variant="outlined"
            label={`Connector: ${connector.connector} (simulated)`}
          />
        )}
      />

      {connector && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <strong>ERP integration: SIMULATED mode.</strong> {connector.note} The connector builds
          and validates real purchase vouchers ({connector.export_format} export); a live Tally or
          ERP host adapter can be plugged in behind the same interface without any other change.
        </Alert>
      )}

      <BulkExportCard />

      <Box sx={{ mb: 1 }}>
        <Tabs value={tab} onChange={(_e, value) => setTab(value)}>
          <Tab value="SYNC_LOG" label="Sync log" />
          <Tab value="MAPPINGS" label="Mappings" />
        </Tabs>
        <Divider />
      </Box>

      {tab === 'SYNC_LOG' ? (
        <>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 2, maxWidth: 360 }}>
            <FormSelect
              label="Status"
              value={filters.status}
              onChange={(e) => setFilters({ status: e.target.value })}
              options={SYNC_STATUSES.map((s) => ({ value: s, label: s === 'NOT_SYNCED' ? 'Not synced' : s === 'SYNCED' ? 'Synced' : 'Failed' }))}
              emptyOption="All statuses"
            />
          </Stack>
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
            emptyTitle="No ERP sync logs yet"
            emptySubtitle="Post an approved invoice or run a bulk export to see sync activity here."
            minWidth={1040}
          />
        </>
      ) : (
        <MappingSettings />
      )}
    </Box>
  );
}
