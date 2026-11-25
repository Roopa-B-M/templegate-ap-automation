import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
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
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import api from '../api/client';
import ConfirmDialog from '../components/ConfirmDialog';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormTextField } from '../components/FormControls';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import useDebouncedValue from '../hooks/useDebouncedValue';
import usePagedList from '../hooks/usePagedList';
import { formatCurrency, formatDate, formatDateTime, getApiErrorMessage, todayStr, toNumber } from '../utils/format';

function CreateGrnDialog({ open, onClose, onCreated }) {
  const snackbar = useSnackbar();
  const [form, setForm] = useState({ grn_number: '', po_id: '', receipt_date: todayStr(), remarks: '' });
  const [poOptions, setPoOptions] = useState([]);
  const [poDetail, setPoDetail] = useState(null);
  const [poLoading, setPoLoading] = useState(false);
  const [qtys, setQtys] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    api
      .get('/purchase-orders', { params: { status: 'OPEN', pageSize: 100 } })
      .then((res) => setPoOptions(res.data.results || []))
      .catch(() => {});
  }, [open]);

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const selectPo = async (poId) => {
    setField('po_id', poId);
    setPoDetail(null);
    setQtys({});
    if (!poId) return;
    setPoLoading(true);
    try {
      const { data } = await api.get(`/purchase-orders/${poId}`);
      setPoDetail(data);
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setPoLoading(false);
    }
  };

  const remaining = (line) => toNumber(line.quantity) - toNumber(line.received_qty);

  const submit = async () => {
    if (!form.grn_number.trim()) {
      snackbar.error('GRN number is required');
      return;
    }
    if (!form.po_id || !poDetail) {
      snackbar.error('Select the purchase order being received against');
      return;
    }
    const lines = poDetail.lines
      .map((line) => ({ po_line_id: line.id, quantity_received: toNumber(qtys[line.id]) }))
      .filter((line) => line.quantity_received > 0);
    if (lines.length === 0) {
      snackbar.error('Enter the quantity to receive for at least one line');
      return;
    }
    for (const line of poDetail.lines) {
      const qty = toNumber(qtys[line.id]);
      if (qty < 0 || qty > remaining(line)) {
        snackbar.error(`Quantity for “${line.description}” cannot exceed the remaining ${remaining(line)}`);
        return;
      }
    }
    setSubmitting(true);
    try {
      await api.post('/grns', {
        grn_number: form.grn_number.trim(),
        po_id: Number(form.po_id),
        receipt_date: form.receipt_date || todayStr(),
        remarks: form.remarks || '',
        lines,
      });
      snackbar.success('Goods receipt note created');
      onCreated();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  const resetAndClose = () => {
    setForm({ grn_number: '', po_id: '', receipt_date: todayStr(), remarks: '' });
    setPoDetail(null);
    setQtys({});
    onClose();
  };

  return (
    <Dialog open={open} onClose={submitting ? undefined : resetAndClose} maxWidth="md" fullWidth>
      <DialogTitle>Create goods receipt note</DialogTitle>
      <DialogContent>
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12} sm={5}>
            <FormTextField
              label="GRN number *"
              value={form.grn_number}
              onChange={(e) => setField('grn_number', e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <FormSelect
              label="Purchase order (open) *"
              value={form.po_id}
              onChange={(e) => selectPo(e.target.value)}
              options={poOptions.map((po) => ({ value: po.id, label: `${po.po_number} — ${po.vendor?.name || ''}` }))}
              emptyOption="Select PO"
            />
          </Grid>
          <Grid item xs={12} sm={3}>
            <FormTextField
              label="Receipt date"
              type="date"
              value={form.receipt_date}
              onChange={(e) => setField('receipt_date', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <FormTextField label="Remarks" value={form.remarks} onChange={(e) => setField('remarks', e.target.value)} />
          </Grid>
        </Grid>

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
          Quantities to receive
        </Typography>
        {!form.po_id ? (
          <Typography variant="body2" color="text.secondary">
            Select an open purchase order to load its lines.
          </Typography>
        ) : poLoading ? (
          <Box sx={{ py: 3, textAlign: 'center' }}>
            <CircularProgress size={28} />
          </Box>
        ) : (
          <TableContainer sx={{ overflowX: 'auto' }}>
            <Table size="small" sx={{ minWidth: 640 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Line</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell align="right">Ordered</TableCell>
                  <TableCell align="right">Already received</TableCell>
                  <TableCell align="right">Remaining</TableCell>
                  <TableCell sx={{ width: 140 }}>Receive now</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(poDetail?.lines || []).map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>{line.line_number}</TableCell>
                    <TableCell>{line.description}</TableCell>
                    <TableCell align="right">{line.quantity}</TableCell>
                    <TableCell align="right">{line.received_qty ?? 0}</TableCell>
                    <TableCell align="right">{remaining(line)}</TableCell>
                    <TableCell>
                      <TextField
                        fullWidth
                        size="small"
                        type="number"
                        inputProps={{ min: 0, max: remaining(line) }}
                        value={qtys[line.id] ?? ''}
                        onChange={(e) => setQtys((prev) => ({ ...prev, [line.id]: e.target.value }))}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={resetAndClose} disabled={submitting} color="inherit">
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={submitting}>
          {submitting ? 'Creating…' : 'Create GRN'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function GrnViewDialog({ grnId, onClose }) {
  const snackbar = useSnackbar();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!grnId) return undefined;
    setLoading(true);
    api
      .get(`/grns/${grnId}`)
      .then((res) => setDetail(res.data))
      .catch((e) => snackbar.error(getApiErrorMessage(e)))
      .finally(() => setLoading(false));
    return undefined;
  }, [grnId, snackbar]);

  return (
    <Dialog open={Boolean(grnId)} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Goods receipt note</DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <CircularProgress size={28} />
          </Box>
        ) : detail ? (
          <>
            <Stack spacing={0.5} sx={{ mb: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  GRN number
                </Typography>
                <Typography variant="body2" fontWeight={700}>
                  {detail.grn_number}
                </Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Purchase order
                </Typography>
                <Typography variant="body2" fontWeight={600}>
                  {detail.po?.po_number || '—'}
                </Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Receipt date
                </Typography>
                <Typography variant="body2">{formatDate(detail.receipt_date)}</Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Received by
                </Typography>
                <Typography variant="body2">{detail.received_by?.username || '—'}</Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Status
                </Typography>
                <StatusChip status={detail.status} display={detail.status_display} />
              </Stack>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Created at
                </Typography>
                <Typography variant="body2">{formatDateTime(detail.created_at)}</Typography>
              </Stack>
            </Stack>
            {detail.remarks && (
              <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
                {detail.remarks}
              </Alert>
            )}
            <TableContainer sx={{ overflowX: 'auto' }}>
              <Table size="small" sx={{ minWidth: 420 }}>
                <TableHead>
                  <TableRow>
                    <TableCell>PO line</TableCell>
                    <TableCell align="right">Quantity received</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(detail.lines || []).map((line) => (
                    <TableRow key={line.id}>
                      <TableCell>{line.po_line?.description || `#${line.po_line_id}`}</TableCell>
                      <TableCell align="right">{line.quantity_received}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        ) : (
          <Typography variant="body2" color="text.secondary">
            GRN not found.
          </Typography>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} color="inherit">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function GrnListPage() {
  const { isAdmin, isClerk } = useAuth();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 400);
  const [createOpen, setCreateOpen] = useState(false);
  const [viewId, setViewId] = useState(null);

  const fetchFn = useCallback(
    (page, pageSize) => {
      const params = { page: page + 1, pageSize };
      if (debouncedSearch) params.search = debouncedSearch;
      return api.get('/grns', { params }).then((res) => res.data);
    },
    [debouncedSearch]
  );

  const list = usePagedList(fetchFn, [debouncedSearch]);

  const columns = [
    { id: 'grn_number', label: 'GRN #', render: (row) => <Typography variant="body2" fontWeight={600}>{row.grn_number}</Typography> },
    { id: 'po', label: 'Purchase Order', render: (row) => row.po?.po_number || '—' },
    { id: 'receipt_date', label: 'Receipt Date', render: (row) => formatDate(row.receipt_date) },
    { id: 'status', label: 'Status', render: (row) => <StatusChip status={row.status} display={row.status_display} /> },
    { id: 'lines', label: 'Lines', align: 'center', render: (row) => (row.lines || []).length },
    { id: 'received_by', label: 'Received By', render: (row) => row.received_by?.username || '—' },
    { id: 'created_at', label: 'Created', render: (row) => formatDateTime(row.created_at) },
    {
      id: 'actions',
      label: '',
      align: 'right',
      render: (row) => (
        <Tooltip title="View GRN">
          <IconButton size="small" onClick={() => setViewId(row.id)} aria-label={`View ${row.grn_number}`}>
            <VisibilityOutlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  return (
    <Box>
      <PageHeader
        title="Goods Receipt Notes"
        subtitle="Record quantities received against purchase orders — receipts feed 3-way invoice matching."
        actions={
          (isAdmin || isClerk) && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
              Create GRN
            </Button>
          )
        }
      />

      <Grid container spacing={2} sx={{ mb: 2 }} alignItems="center">
        <Grid item xs={12} sm={9} md={4}>
          <TextField fullWidth label="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </Grid>
        <Grid item xs={12} sm={3} md={2}>
          <Button color="inherit" onClick={() => setSearch('')} sx={{ minWidth: 0 }}>
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
        emptyTitle="No goods receipts found"
        emptySubtitle="Create a GRN when goods arrive against a purchase order."
        minWidth={820}
      />

      <CreateGrnDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          list.reload();
        }}
      />

      {viewId && <GrnViewDialog grnId={viewId} onClose={() => setViewId(null)} />}
    </Box>
  );
}
