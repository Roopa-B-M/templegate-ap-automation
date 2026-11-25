import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  Link,
  LinearProgress,
  Paper,
  Stack,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableFooter,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CodeIcon from '@mui/icons-material/Code';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import api from '../api/client';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormTextField } from '../components/FormControls';
import { useSnackbar } from '../context/SnackbarContext';
import useDebouncedValue from '../hooks/useDebouncedValue';
import usePagedList from '../hooks/usePagedList';
import { exportCsvReport } from '../utils/download';
import {
  formatCurrency,
  formatDateTime,
  getApiErrorMessage,
  prettyJson,
  todayStr,
} from '../utils/format';

/* ---------- shared pieces ---------- */

function ReportToolbar({ filters, onExport, exporting }) {
  return (
    <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
      {filters}
      <Box sx={{ flexGrow: 1 }} />
      <Button variant="contained" onClick={onExport} disabled={exporting} startIcon={<FileDownloadIcon />}>
        Export CSV
      </Button>
    </Stack>
  );
}

function ReportTable({ loading, error, onRetry, columns, rows, footer, minWidth = 760 }) {
  if (error) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" startIcon={<RefreshIcon />} onClick={onRetry}>
            Retry
          </Button>
        }
      >
        {getApiErrorMessage(error)}
      </Alert>
    );
  }
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
      {loading && <LinearProgress sx={{ height: 2 }} />}
      <TableContainer sx={{ overflowX: 'auto' }}>
        <Table size="small" sx={{ minWidth }}>
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableCell key={column.id} align={column.align || 'left'}>
                  {column.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length}>
                  <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                    No data available for the selected filters.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row, index) => (
                <TableRow hover key={row.id ?? index}>
                  {columns.map((column) => (
                    <TableCell key={column.id} align={column.align || 'left'}>
                      {column.render ? column.render(row) : (row[column.id] ?? '—')}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
          {footer && (
            <TableFooter>
              <TableRow sx={{ '& td': { fontWeight: 700, borderTop: '2px solid', borderColor: 'divider' } }}>
                {footer}
              </TableRow>
            </TableFooter>
          )}
        </Table>
      </TableContainer>
    </Paper>
  );
}

/* ---------- AP Aging tab ---------- */

function AgingTab() {
  const snackbar = useSnackbar();
  const [asOf, setAsOf] = useState(todayStr());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/reports/ap-aging', { params: { as_of: asOf } });
      setData(res.data);
      setError(null);
    } catch (e) {
      setError(e);
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [asOf, snackbar]);

  useEffect(() => {
    load();
  }, [load]);

  const exportCsv = async () => {
    setExporting(true);
    try {
      await exportCsvReport('/reports/ap-aging', { as_of: asOf }, 'ap-aging.csv');
      snackbar.success('Export started — check your downloads');
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setExporting(false);
    }
  };

  const columns = [
    { id: 'vendor', label: 'Vendor' },
    { id: 'current', label: 'Current', align: 'right', render: (row) => formatCurrency(row.current) },
    { id: 'd31_60', label: '31–60 days', align: 'right', render: (row) => formatCurrency(row.d31_60) },
    { id: 'd61_90', label: '61–90 days', align: 'right', render: (row) => formatCurrency(row.d61_90) },
    { id: 'd90_plus', label: '90+ days', align: 'right', render: (row) => formatCurrency(row.d90_plus) },
    { id: 'total', label: 'Total', align: 'right', render: (row) => formatCurrency(row.total) },
  ];

  return (
    <Box>
      <ReportToolbar
        filters={
          <>
            <FormTextField label="As of date" type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} sx={{ width: 190 }} />
            <Button variant="outlined" onClick={load} startIcon={<RefreshIcon />}>
              Refresh
            </Button>
          </>
        }
        onExport={exportCsv}
        exporting={exporting}
      />
      <ReportTable
        loading={loading}
        error={error}
        onRetry={load}
        columns={columns}
        rows={data?.rows || []}
        minWidth={760}
        footer={
          <>
            <TableCell>Totals</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.current)}</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.d31_60)}</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.d61_90)}</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.d90_plus)}</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.total)}</TableCell>
          </>
        }
      />
    </Box>
  );
}

/* ---------- Invoice Status tab ---------- */

function StatusTab() {
  const snackbar = useSnackbar();
  const [filters, setFilters] = useState({ date_from: '', date_to: '' });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      const res = await api.get('/reports/invoice-status', { params });
      setData(res.data);
      setError(null);
    } catch (e) {
      setError(e);
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [filters, snackbar]);

  useEffect(() => {
    load();
  }, [load]);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const params = {};
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      await exportCsvReport('/reports/invoice-status', params, 'invoice-status.csv');
      snackbar.success('Export started — check your downloads');
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setExporting(false);
    }
  };

  const rows = data?.rows || [];
  const totalCount = rows.reduce((sum, row) => sum + (Number(row.count) || 0), 0);
  const totalAmount = rows.reduce((sum, row) => sum + (parseFloat(row.total_amount) || 0), 0);

  const columns = [
    { id: 'status', label: 'Status', render: (row) => <StatusChip status={row.status} display={row.status_display} /> },
    { id: 'count', label: 'Invoices', align: 'right' },
    { id: 'total_amount', label: 'Total Amount', align: 'right', render: (row) => formatCurrency(row.total_amount) },
  ];

  return (
    <Box>
      <ReportToolbar
        filters={
          <>
            <FormTextField
              label="From date"
              type="date"
              value={filters.date_from}
              onChange={(e) => setFilters((prev) => ({ ...prev, date_from: e.target.value }))}
              sx={{ width: 190 }}
            />
            <FormTextField
              label="To date"
              type="date"
              value={filters.date_to}
              onChange={(e) => setFilters((prev) => ({ ...prev, date_to: e.target.value }))}
              sx={{ width: 190 }}
            />
            <Button variant="outlined" onClick={load} startIcon={<RefreshIcon />}>
              Refresh
            </Button>
          </>
        }
        onExport={exportCsv}
        exporting={exporting}
      />
      <ReportTable
        loading={loading}
        error={error}
        onRetry={load}
        columns={columns}
        rows={rows}
        minWidth={520}
        footer={
          <>
            <TableCell>Totals</TableCell>
            <TableCell align="right">{totalCount}</TableCell>
            <TableCell align="right">{formatCurrency(totalAmount)}</TableCell>
          </>
        }
      />
    </Box>
  );
}

/* ---------- Exceptions tab ---------- */

function ExceptionsTab() {
  const snackbar = useSnackbar();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/reports/exceptions');
      setData(res.data);
      setError(null);
    } catch (e) {
      setError(e);
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [snackbar]);

  useEffect(() => {
    load();
  }, [load]);

  const exportCsv = async () => {
    setExporting(true);
    try {
      await exportCsvReport('/reports/exceptions', {}, 'exceptions.csv');
      snackbar.success('Export started — check your downloads');
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setExporting(false);
    }
  };

  const columns = [
    {
      id: 'invoice_number',
      label: 'Invoice #',
      render: (row) => (
        <Link component={RouterLink} to={`/invoices/${row.invoice_id}`} fontWeight={600}>
          {row.invoice_number}
        </Link>
      ),
    },
    { id: 'vendor', label: 'Vendor' },
    { id: 'status', label: 'Status', render: (row) => <StatusChip status={row.status} display={row.status_display} /> },
    { id: 'total_amount', label: 'Amount', align: 'right', render: (row) => formatCurrency(row.total_amount) },
    { id: 'reason', label: 'Reason', render: (row) => row.reason || '—' },
    { id: 'created_at', label: 'Created', render: (row) => formatDateTime(row.created_at) },
    {
      id: 'actions',
      label: '',
      align: 'right',
      render: (row) => (
        <Tooltip title="Open invoice">
          <IconButton size="small" component={RouterLink} to={`/invoices/${row.invoice_id}`} aria-label="Open invoice">
            <VisibilityOutlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  return (
    <Box>
      <ReportToolbar filters={null} onExport={exportCsv} exporting={exporting} />
      <ReportTable
        loading={loading}
        error={error}
        onRetry={load}
        columns={columns}
        rows={data?.rows || []}
        minWidth={860}
      />
    </Box>
  );
}

/* ---------- GST tab ---------- */

function GstTab() {
  const snackbar = useSnackbar();
  const [filters, setFilters] = useState({ date_from: '', date_to: '' });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      const res = await api.get('/reports/gst', { params });
      setData(res.data);
      setError(null);
    } catch (e) {
      setError(e);
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [filters, snackbar]);

  useEffect(() => {
    load();
  }, [load]);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const params = {};
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      await exportCsvReport('/reports/gst', params, 'gst-report.csv');
      snackbar.success('Export started — check your downloads');
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setExporting(false);
    }
  };

  const columns = [
    { id: 'gst_rate', label: 'GST Rate', render: (row) => `${parseFloat(row.gst_rate) || 0}%` },
    { id: 'taxable_value', label: 'Taxable Value', align: 'right', render: (row) => formatCurrency(row.taxable_value) },
    { id: 'cgst', label: 'CGST', align: 'right', render: (row) => formatCurrency(row.cgst) },
    { id: 'sgst', label: 'SGST', align: 'right', render: (row) => formatCurrency(row.sgst) },
    { id: 'igst', label: 'IGST', align: 'right', render: (row) => formatCurrency(row.igst) },
    { id: 'total_tax', label: 'Total Tax', align: 'right', render: (row) => formatCurrency(row.total_tax) },
  ];

  return (
    <Box>
      <ReportToolbar
        filters={
          <>
            <FormTextField
              label="From date"
              type="date"
              value={filters.date_from}
              onChange={(e) => setFilters((prev) => ({ ...prev, date_from: e.target.value }))}
              sx={{ width: 190 }}
            />
            <FormTextField
              label="To date"
              type="date"
              value={filters.date_to}
              onChange={(e) => setFilters((prev) => ({ ...prev, date_to: e.target.value }))}
              sx={{ width: 190 }}
            />
            <Button variant="outlined" onClick={load} startIcon={<RefreshIcon />}>
              Refresh
            </Button>
          </>
        }
        onExport={exportCsv}
        exporting={exporting}
      />
      <ReportTable
        loading={loading}
        error={error}
        onRetry={load}
        columns={columns}
        rows={data?.rows || []}
        minWidth={760}
        footer={
          <>
            <TableCell>Totals</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.taxable_value)}</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.cgst)}</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.sgst)}</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.igst)}</TableCell>
            <TableCell align="right">{formatCurrency(data?.totals?.total_tax)}</TableCell>
          </>
        }
      />
    </Box>
  );
}

/* ---------- Audit Logs tab ---------- */

function AuditTab() {
  const [filters, setFilters] = useState({ entity: '', user: '', date_from: '', date_to: '' });
  const debouncedEntity = useDebouncedValue(filters.entity, 400);
  const debouncedUser = useDebouncedValue(filters.user, 400);

  const effectiveFilters = useMemo(
    () => ({ ...filters, entity: debouncedEntity, user: debouncedUser }),
    [filters, debouncedEntity, debouncedUser]
  );

  const fetchFn = useCallback(
    (page, pageSize) => {
      const params = { page: page + 1, pageSize };
      Object.entries(effectiveFilters).forEach(([key, value]) => {
        if (value !== '' && value !== null && value !== undefined) params[key] = value;
      });
      return api.get('/reports/audit-logs', { params }).then((res) => res.data);
    },
    [effectiveFilters]
  );

  const list = usePagedList(fetchFn, [effectiveFilters]);
  const [changesOpen, setChangesOpen] = useState(null);

  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));

  const columns = [
    { id: 'created_at', label: 'Time', render: (row) => formatDateTime(row.created_at) },
    { id: 'user', label: 'User', render: (row) => row.user?.username || 'system' },
    { id: 'action', label: 'Action', render: (row) => <Typography variant="body2" fontWeight={600}>{row.action}</Typography> },
    {
      id: 'entity',
      label: 'Entity',
      render: (row) => (
        <Stack>
          <Typography variant="body2">
            {row.entity} #{row.entity_id}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {row.entity_repr}
          </Typography>
        </Stack>
      ),
    },
    {
      id: 'changes',
      label: 'Changes',
      render: (row) =>
        row.changes ? (
          <Tooltip title="View changes">
            <IconButton size="small" onClick={() => setChangesOpen(prettyJson(row.changes) || row.changes)} aria-label="View changes">
              <CodeIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : (
          '—'
        ),
    },
    { id: 'ip_address', label: 'IP Address' },
  ];

  return (
    <Box>
      <Grid container spacing={2} sx={{ mb: 2 }} alignItems="center">
        <Grid item xs={12} sm={6} md={2.5}>
          <FormTextField label="Entity" value={filters.entity} onChange={(e) => setFilter('entity', e.target.value)} />
        </Grid>
        <Grid item xs={12} sm={6} md={2.5}>
          <FormTextField label="User" value={filters.user} onChange={(e) => setFilter('user', e.target.value)} />
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <FormTextField
            label="From date"
            type="date"
            value={filters.date_from}
            onChange={(e) => setFilter('date_from', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <FormTextField
            label="To date"
            type="date"
            value={filters.date_to}
            onChange={(e) => setFilter('date_to', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={1.5}>
          <Button
            color="inherit"
            onClick={() => setFilters({ entity: '', user: '', date_from: '', date_to: '' })}
            sx={{ minWidth: 0 }}
          >
            Clear
          </Button>
        </Grid>
      </Grid>

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
        emptyTitle="No audit log entries"
        emptySubtitle="System activity will appear here as users work with the application."
        minWidth={900}
      />

      <Dialog open={Boolean(changesOpen)} onClose={() => setChangesOpen(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Change details</DialogTitle>
        <DialogContent>
          <Box
            component="pre"
            sx={{
              m: 0,
              p: 1.5,
              bgcolor: '#F1F5F9',
              borderRadius: 1.5,
              fontSize: 12,
              maxHeight: 360,
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {changesOpen}
          </Box>
        </DialogContent>
      </Dialog>
    </Box>
  );
}

/* ---------- page shell ---------- */

const TABS = [
  { value: 'aging', label: 'AP Aging' },
  { value: 'status', label: 'Invoice Status' },
  { value: 'exceptions', label: 'Exceptions' },
  { value: 'gst', label: 'GST Report' },
  { value: 'audit', label: 'Audit Logs' },
];

export default function ReportsPage() {
  const [tab, setTab] = useState('aging');

  return (
    <Box>
      <PageHeader
        title="Reports"
        subtitle="Operational and compliance reporting across the AP lifecycle."
      />
      <Paper variant="outlined" sx={{ mb: 0 }}>
        <Tabs value={tab} onChange={(_e, value) => setTab(value)} variant="scrollable" scrollButtons="auto">
          {TABS.map((item) => (
            <Tab key={item.value} value={item.value} label={item.label} />
          ))}
        </Tabs>
        <Divider />
        <Box sx={{ p: { xs: 1.5, md: 2.5 } }}>
          {tab === 'aging' && <AgingTab />}
          {tab === 'status' && <StatusTab />}
          {tab === 'exceptions' && <ExceptionsTab />}
          {tab === 'gst' && <GstTab />}
          {tab === 'audit' && <AuditTab />}
        </Box>
      </Paper>
    </Box>
  );
}
