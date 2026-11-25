import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  Link,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import api from '../api/client';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormTextField } from '../components/FormControls';
import VendorFormFields, { EMPTY_VENDOR_FORM, validateVendorForm } from '../components/VendorFormFields';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import useDebouncedValue from '../hooks/useDebouncedValue';
import usePagedList from '../hooks/usePagedList';
import { VENDOR_STATUSES } from '../utils/constants';
import { formatCurrency, formatDate, getApiErrorMessage, humanize } from '../utils/format';

function CreateVendorDialog({ open, onClose, onCreated }) {
  const snackbar = useSnackbar();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY_VENDOR_FORM);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async () => {
    const validation = validateVendorForm(form);
    setErrors(validation);
    if (Object.keys(validation).length > 0) {
      snackbar.error('Please fill in all required fields');
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post('/vendors', form);
      snackbar.success(`Vendor ${data.name} created`);
      onCreated();
      navigate(`/vendors/${data.id}`);
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={submitting ? undefined : onClose} maxWidth="md" fullWidth>
      <DialogTitle>Create vendor</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1 }}>
          <VendorFormFields form={form} setField={setField} errors={errors} />
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={submitting} color="inherit">
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={submitting}>
          {submitting ? 'Creating…' : 'Create vendor'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function VendorListPage() {
  const { isAdmin, isClerk } = useAuth();
  const [filters, setFilters] = useState({ status: '', search: '' });
  const debouncedSearch = useDebouncedValue(filters.search, 400);
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
      return api.get('/vendors', { params }).then((res) => res.data);
    },
    [effectiveFilters]
  );

  const list = usePagedList(fetchFn, [effectiveFilters]);

  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));

  const columns = [
    { id: 'code', label: 'Code', render: (row) => <Typography fontWeight={600}>{row.code}</Typography> },
    {
      id: 'name',
      label: 'Vendor',
      render: (row) => (
        <Link component={RouterLink} to={`/vendors/${row.id}`} fontWeight={600}>
          {row.name}
        </Link>
      ),
    },
    { id: 'gstin', label: 'GSTIN', render: (row) => row.gstin || '—' },
    {
      id: 'location',
      label: 'City / State',
      render: (row) => `${row.city || '—'}${row.state ? `, ${row.state}` : ''}`,
    },
    { id: 'status', label: 'Status', render: (row) => <StatusChip status={row.status} display={row.status_display} /> },
    { id: 'invoice_count', label: 'Invoices', align: 'center' },
    { id: 'total_billed', label: 'Total Billed', align: 'right', render: (row) => formatCurrency(row.total_billed) },
    { id: 'created_at', label: 'Created', render: (row) => formatDate(row.created_at) },
    {
      id: 'actions',
      label: '',
      align: 'right',
      render: (row) => (
        <Tooltip title="View vendor">
          <IconButton size="small" component={RouterLink} to={`/vendors/${row.id}`} aria-label={`View ${row.name}`}>
            <VisibilityOutlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  return (
    <Box>
      <PageHeader
        title="Vendors"
        subtitle="Supplier master data with onboarding approval and bank account verification."
        actions={
          (isAdmin || isClerk) && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
              Create vendor
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
            options={VENDOR_STATUSES.map((s) => ({ value: s, label: humanize(s) }))}
            emptyOption="All statuses"
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
          <Button color="inherit" onClick={() => setFilters({ status: '', search: '' })} sx={{ minWidth: 0 }}>
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
        emptyTitle="No vendors found"
        emptySubtitle="Create a vendor to start booking invoices against it."
      />

      {createOpen && (
        <CreateVendorDialog
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          onCreated={() => setCreateOpen(false)}
        />
      )}
    </Box>
  );
}
