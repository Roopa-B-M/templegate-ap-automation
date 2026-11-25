import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Grid,
  IconButton,
  InputAdornment,
  Link,
  TextField,
  Tooltip,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import api from '../api/client';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormTextField } from '../components/FormControls';
import { useAuth } from '../context/AuthContext';
import useDebouncedValue from '../hooks/useDebouncedValue';
import usePagedList from '../hooks/usePagedList';
import { INVOICE_STATUSES } from '../utils/constants';
import { formatCurrency, formatDate, humanize } from '../utils/format';

const STATUS_OPTIONS = INVOICE_STATUSES.map((s) => ({ value: s, label: humanize(s) }));
const EMPTY_FILTERS = { status: '', vendor_id: '', search: '', date_from: '', date_to: '' };

export default function InvoiceListPage() {
  const { isAdmin, isClerk } = useAuth();
  const navigate = useNavigate();
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const debouncedSearch = useDebouncedValue(filters.search, 400);
  const [vendorOptions, setVendorOptions] = useState([]);

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
      return api.get('/invoices', { params }).then((res) => res.data);
    },
    [effectiveFilters]
  );

  const list = usePagedList(fetchFn, [effectiveFilters]);

  // Vendor filter options (per API contract: /vendors?pageSize=100).
  useEffect(() => {
    api
      .get('/vendors', { params: { pageSize: 100 } })
      .then((res) => setVendorOptions(res.data.results || []))
      .catch(() => {});
  }, []);

  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));

  const columns = [
    {
      id: 'invoice_number',
      label: 'Invoice #',
      render: (row) => (
        <Link component={RouterLink} to={`/invoices/${row.id}`} fontWeight={600}>
          {row.invoice_number}
        </Link>
      ),
    },
    { id: 'vendor_name', label: 'Vendor', render: (row) => row.vendor_name || row.vendor?.name || '—' },
    { id: 'po', label: 'PO', render: (row) => row.po?.po_number || '—' },
    { id: 'invoice_date', label: 'Invoice Date', render: (row) => formatDate(row.invoice_date) },
    { id: 'due_date', label: 'Due Date', render: (row) => formatDate(row.due_date) },
    {
      id: 'total_amount',
      label: 'Total',
      align: 'right',
      render: (row) => formatCurrency(row.total_amount),
    },
    { id: 'status', label: 'Status', render: (row) => <StatusChip status={row.status} display={row.status_display} /> },
    { id: 'ocr_status', label: 'OCR', render: (row) => <StatusChip status={row.ocr_status} /> },
    {
      id: 'actions',
      label: '',
      align: 'right',
      render: (row) => (
        <Tooltip title="View invoice">
          <IconButton
            size="small"
            component={RouterLink}
            to={`/invoices/${row.id}`}
            aria-label={`View ${row.invoice_number}`}
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
        title="Invoices"
        subtitle="Accounts payable invoices across the OCR → validation → matching → approval → payment pipeline."
        actions={
          (isAdmin || isClerk) && (
            <Button
              variant="contained"
              startIcon={<UploadFileIcon />}
              onClick={() => navigate('/invoices/upload')}
            >
              Upload invoices
            </Button>
          )
        }
      />

      <Grid container spacing={2} sx={{ mb: 2 }} alignItems="center">
        <Grid item xs={12} sm={6} md={2.5}>
          <FormSelect
            label="Status"
            value={filters.status}
            onChange={(e) => setFilter('status', e.target.value)}
            options={STATUS_OPTIONS}
            emptyOption="All statuses"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2.5}>
          <FormSelect
            label="Vendor"
            value={filters.vendor_id}
            onChange={(e) => setFilter('vendor_id', e.target.value)}
            options={vendorOptions.map((v) => ({ value: v.id, label: v.name }))}
            emptyOption="All vendors"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2.5}>
          <FormTextField
            label="From date"
            type="date"
            value={filters.date_from}
            onChange={(e) => setFilter('date_from', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2.5}>
          <FormTextField
            label="To date"
            type="date"
            value={filters.date_to}
            onChange={(e) => setFilter('date_to', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={9} md={1.5}>
          <TextField
            fullWidth
            label="Search"
            value={filters.search}
            onChange={(e) => setFilter('search', e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
        </Grid>
        <Grid item xs={12} sm={3} md={1}>
          <Button
            color="inherit"
            onClick={() => setFilters(EMPTY_FILTERS)}
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
        emptyTitle="No invoices found"
        emptySubtitle="Adjust the filters, or upload invoices to get started."
      />
    </Box>
  );
}
