import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import api from '../api/client';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormTextField } from '../components/FormControls';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import useDebouncedValue from '../hooks/useDebouncedValue';
import usePagedList from '../hooks/usePagedList';
import { PO_STATUSES } from '../utils/constants';
import { formatCurrency, formatDate, getApiErrorMessage, humanize, todayStr, toNumber } from '../utils/format';

const EMPTY_LINE = { item_code: '', description: '', hsn_code: '', quantity: '', unit: '', unit_price: '', tax_rate: '' };

function CreatePoDialog({ open, onClose, vendorOptions, onCreated }) {
  const snackbar = useSnackbar();
  const [form, setForm] = useState({
    po_number: '',
    vendor_id: '',
    po_date: todayStr(),
    currency: 'INR',
    notes: '',
  });
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [submitting, setSubmitting] = useState(false);

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));
  const setLine = (index, key, value) =>
    setLines((prev) => prev.map((row, i) => (i === index ? { ...row, [key]: value } : row)));

  const submit = async () => {
    if (!form.po_number.trim() || !form.vendor_id || !form.po_date) {
      snackbar.error('PO number, vendor and PO date are required');
      return;
    }
    const validLines = lines.filter((l) => l.description.trim() !== '' || toNumber(l.quantity) > 0);
    if (validLines.length === 0) {
      snackbar.error('Add at least one line item');
      return;
    }
    for (const line of validLines) {
      if (!line.description.trim() || toNumber(line.quantity) <= 0 || toNumber(line.unit_price) <= 0) {
        snackbar.error('Each line item needs a description, quantity and unit price');
        return;
      }
    }
    setSubmitting(true);
    try {
      await api.post('/purchase-orders', {
        po_number: form.po_number.trim(),
        vendor_id: Number(form.vendor_id),
        po_date: form.po_date,
        currency: form.currency || 'INR',
        notes: form.notes || '',
        lines: validLines.map((line) => ({
          item_code: line.item_code.trim() || undefined,
          description: line.description.trim(),
          hsn_code: line.hsn_code.trim() || undefined,
          quantity: toNumber(line.quantity),
          unit: line.unit.trim() || undefined,
          unit_price: toNumber(line.unit_price),
          tax_rate: toNumber(line.tax_rate),
        })),
      });
      snackbar.success('Purchase order created');
      onCreated();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  const resetAndClose = () => {
    setForm({ po_number: '', vendor_id: '', po_date: todayStr(), currency: 'INR', notes: '' });
    setLines([{ ...EMPTY_LINE }]);
    onClose();
  };

  return (
    <Dialog open={open} onClose={submitting ? undefined : resetAndClose} maxWidth="md" fullWidth>
      <DialogTitle>Create purchase order</DialogTitle>
      <DialogContent>
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12} sm={6}>
            <FormTextField label="PO number *" value={form.po_number} onChange={(e) => setField('po_number', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormSelect
              label="Vendor *"
              value={form.vendor_id}
              onChange={(e) => setField('vendor_id', e.target.value)}
              options={vendorOptions.map((v) => ({ value: v.id, label: `${v.code} — ${v.name}` }))}
              emptyOption="Select vendor"
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <FormTextField label="PO date *" type="date" value={form.po_date} onChange={(e) => setField('po_date', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={4}>
            <FormTextField label="Currency" value={form.currency} onChange={(e) => setField('currency', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={4}>
            <FormTextField label="Notes" value={form.notes} onChange={(e) => setField('notes', e.target.value)} />
          </Grid>
        </Grid>

        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle2" gutterBottom>
          Line items
        </Typography>
        <TableContainer sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ minWidth: 760 }}>
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 110 }}>Item code</TableCell>
                <TableCell>Description *</TableCell>
                <TableCell sx={{ width: 100 }}>HSN</TableCell>
                <TableCell sx={{ width: 90 }}>Qty *</TableCell>
                <TableCell sx={{ width: 80 }}>Unit</TableCell>
                <TableCell sx={{ width: 110 }}>Unit Price *</TableCell>
                <TableCell sx={{ width: 90 }}>Tax %</TableCell>
                <TableCell align="right" sx={{ width: 110 }}>
                  Line Amount
                </TableCell>
                <TableCell sx={{ width: 44 }} />
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map((line, index) => (
                <TableRow key={index}>
                  <TableCell>
                    <TextField fullWidth size="small" value={line.item_code} onChange={(e) => setLine(index, 'item_code', e.target.value)} />
                  </TableCell>
                  <TableCell>
                    <TextField fullWidth size="small" value={line.description} onChange={(e) => setLine(index, 'description', e.target.value)} />
                  </TableCell>
                  <TableCell>
                    <TextField fullWidth size="small" value={line.hsn_code} onChange={(e) => setLine(index, 'hsn_code', e.target.value)} />
                  </TableCell>
                  <TableCell>
                    <TextField fullWidth size="small" type="number" value={line.quantity} onChange={(e) => setLine(index, 'quantity', e.target.value)} />
                  </TableCell>
                  <TableCell>
                    <TextField fullWidth size="small" value={line.unit} onChange={(e) => setLine(index, 'unit', e.target.value)} />
                  </TableCell>
                  <TableCell>
                    <TextField fullWidth size="small" type="number" value={line.unit_price} onChange={(e) => setLine(index, 'unit_price', e.target.value)} />
                  </TableCell>
                  <TableCell>
                    <TextField fullWidth size="small" type="number" value={line.tax_rate} onChange={(e) => setLine(index, 'tax_rate', e.target.value)} />
                  </TableCell>
                  <TableCell align="right">
                    {formatCurrency(toNumber(line.quantity) * toNumber(line.unit_price))}
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      aria-label="Remove line"
                      onClick={() => setLines((prev) => (prev.length > 1 ? prev.filter((_row, i) => i !== index) : prev))}
                      disabled={lines.length === 1}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <Button startIcon={<AddIcon />} size="small" sx={{ mt: 1 }} onClick={() => setLines((prev) => [...prev, { ...EMPTY_LINE }])}>
          Add line item
        </Button>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={resetAndClose} disabled={submitting} color="inherit">
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={submitting}>
          {submitting ? 'Creating…' : 'Create PO'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function PurchaseOrderListPage() {
  const { isAdmin, isClerk } = useAuth();
  const snackbar = useSnackbar();
  const [filters, setFilters] = useState({ status: '', vendor_id: '', search: '' });
  const debouncedSearch = useDebouncedValue(filters.search, 400);
  const [vendorOptions, setVendorOptions] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);

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
      return api.get('/purchase-orders', { params }).then((res) => res.data);
    },
    [effectiveFilters]
  );

  const list = usePagedList(fetchFn, [effectiveFilters]);

  useEffect(() => {
    api
      .get('/vendors', { params: { pageSize: 100 } })
      .then((res) => setVendorOptions(res.data.results || []))
      .catch(() => {});
  }, []);

  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));

  const columns = [
    {
      id: 'po_number',
      label: 'PO #',
      render: (row) => (
        <Link component={RouterLink} to={`/purchase-orders/${row.id}`} fontWeight={600}>
          {row.po_number}
        </Link>
      ),
    },
    { id: 'vendor', label: 'Vendor', render: (row) => row.vendor?.name || '—' },
    { id: 'po_date', label: 'PO Date', render: (row) => formatDate(row.po_date) },
    {
      id: 'total_amount',
      label: 'Total',
      align: 'right',
      render: (row) => formatCurrency(row.total_amount),
    },
    { id: 'status', label: 'Status', render: (row) => <StatusChip status={row.status} display={row.status_display} /> },
    { id: 'invoice_count', label: 'Invoices', align: 'center' },
    { id: 'created_by', label: 'Created By', render: (row) => row.created_by?.username || '—' },
    {
      id: 'actions',
      label: '',
      align: 'right',
      render: (row) => (
        <Tooltip title="View PO">
          <IconButton
            size="small"
            component={RouterLink}
            to={`/purchase-orders/${row.id}`}
            aria-label={`View ${row.po_number}`}
          >
            <VisibilityOutlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  return (
    <Box>
      <PageHeader
        title="Purchase Orders"
        subtitle="Supplier purchase orders with line-level receipt tracking for 3-way matching."
        actions={
          (isAdmin || isClerk) && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
              Create PO
            </Button>
          )
        }
      />

      <Grid container spacing={2} sx={{ mb: 2 }} alignItems="center">
        <Grid item xs={12} sm={6} md={3}>
          <FormSelect
            label="Status"
            value={filters.status}
            onChange={(e) => setFilter('status', e.target.value)}
            options={PO_STATUSES.map((s) => ({ value: s, label: humanize(s) }))}
            emptyOption="All statuses"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <FormSelect
            label="Vendor"
            value={filters.vendor_id}
            onChange={(e) => setFilter('vendor_id', e.target.value)}
            options={vendorOptions.map((v) => ({ value: v.id, label: v.name }))}
            emptyOption="All vendors"
          />
        </Grid>
        <Grid item xs={12} sm={9} md={4}>
          <TextField
            fullWidth
            label="Search"
            value={filters.search}
            onChange={(e) => setFilter('search', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={3} md={2}>
          <Button color="inherit" onClick={() => setFilters({ status: '', vendor_id: '', search: '' })} sx={{ minWidth: 0 }}>
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
        emptyTitle="No purchase orders found"
        emptySubtitle="Create a PO to start receiving goods against it."
      />

      <CreatePoDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        vendorOptions={vendorOptions}
        onCreated={() => {
          setCreateOpen(false);
          list.reload();
        }}
      />
    </Box>
  );
}
