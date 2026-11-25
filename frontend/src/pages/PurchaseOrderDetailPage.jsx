import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import api from '../api/client';
import ConfirmDialog from '../components/ConfirmDialog';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import { formatCurrency, formatDate, formatDateTime, getApiErrorMessage, humanize } from '../utils/format';

function MetaRow({ label, value, bold }) {
  return (
    <Stack direction="row" justifyContent="space-between" sx={{ py: 0.4, gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={bold ? 700 : 500} sx={{ textAlign: 'right', wordBreak: 'break-word' }}>
        {value}
      </Typography>
    </Stack>
  );
}

export default function PurchaseOrderDetailPage() {
  const { id } = useParams();
  const { isAdmin, isClerk } = useAuth();
  const snackbar = useSnackbar();
  const [po, setPo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [confirmState, setConfirmState] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/purchase-orders/${id}`);
      setPo(data);
      setLoadError(null);
    } catch (e) {
      setLoadError(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const patchStatus = async (status) => {
    setActionLoading(true);
    try {
      await api.patch(`/purchase-orders/${id}`, { status });
      snackbar.success(`PO marked ${humanize(status)}`);
      await load();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setActionLoading(false);
      setConfirmState(null);
    }
  };

  if (loadError && !po) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={load}>
            Retry
          </Button>
        }
      >
        Failed to load purchase order: {getApiErrorMessage(loadError)}
      </Alert>
    );
  }

  if (!po) {
    return (
      <Box>
        <Skeleton variant="rectangular" width={300} height={36} sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Skeleton variant="rounded" height={300} />
          </Grid>
          <Grid item xs={12} md={7}>
            <Skeleton variant="rounded" height={300} />
          </Grid>
        </Grid>
      </Box>
    );
  }

  const canManage = isAdmin || isClerk;

  return (
    <Box>
      <PageHeader
        title={`Purchase Order ${po.po_number}`}
        subtitle={po.vendor?.name || 'No vendor'}
        actions={
          <>
            <StatusChip status={po.status} display={po.status_display} />
            {canManage && po.status === 'OPEN' && (
              <>
                <Button
                  variant="outlined"
                  onClick={() =>
                    setConfirmState({
                      title: 'Close purchase order',
                      message: 'Mark this PO as closed? No further receipts will be accepted.',
                      confirmText: 'Close PO',
                      action: () => patchStatus('CLOSED'),
                    })
                  }
                >
                  Close PO
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  onClick={() =>
                    setConfirmState({
                      title: 'Cancel purchase order',
                      message: 'Cancel this purchase order? This action cannot be undone.',
                      confirmText: 'Cancel PO',
                      color: 'error',
                      action: () => patchStatus('CANCELLED'),
                    })
                  }
                >
                  Cancel PO
                </Button>
              </>
            )}
            {canManage && po.status === 'CLOSED' && (
              <Button
                variant="outlined"
                onClick={() =>
                  setConfirmState({
                    title: 'Reopen purchase order',
                    message: 'Reopen this PO for receipts?',
                    confirmText: 'Reopen',
                    action: () => patchStatus('OPEN'),
                  })
                }
              >
                Reopen PO
              </Button>
            )}
          </>
        }
      />

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                PO summary
              </Typography>
              <Divider sx={{ mb: 1.5 }} />
              <MetaRow label="PO number" value={po.po_number} bold />
              <MetaRow
                label="Vendor"
                value={
                  po.vendor ? (
                    <Button
                      size="small"
                      component={RouterLink}
                      to={`/vendors/${po.vendor.id}`}
                      sx={{ px: 0, minWidth: 0 }}
                    >
                      {po.vendor.name}
                    </Button>
                  ) : (
                    '—'
                  )
                }
              />
              <MetaRow label="PO date" value={formatDate(po.po_date)} />
              <MetaRow label="Currency" value={po.currency || '—'} />
              <MetaRow label="Subtotal" value={formatCurrency(po.subtotal)} />
              <MetaRow label="Tax" value={formatCurrency(po.tax_amount)} />
              <MetaRow label="Total" value={formatCurrency(po.total_amount)} bold />
              <MetaRow label="Invoices" value={po.invoice_count ?? 0} />
              <MetaRow label="Created by" value={po.created_by?.username || '—'} />
              <MetaRow label="Created at" value={formatDateTime(po.created_at)} />
              {po.notes && (
                <Box sx={{ mt: 1.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    Notes
                  </Typography>
                  <Typography variant="body2">{po.notes}</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography variant="subtitle1" fontWeight={700}>
                  Line items
                </Typography>
                <Chip size="small" variant="outlined" label={`${(po.lines || []).length} line(s)`} />
              </Stack>
              <TableContainer sx={{ overflowX: 'auto' }}>
                <Table size="small" sx={{ minWidth: 780 }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>#</TableCell>
                      <TableCell>Item code</TableCell>
                      <TableCell>Description</TableCell>
                      <TableCell>HSN</TableCell>
                      <TableCell align="right">Qty</TableCell>
                      <TableCell>Unit</TableCell>
                      <TableCell align="right">Unit Price</TableCell>
                      <TableCell align="right">Tax %</TableCell>
                      <TableCell align="right">Line Total</TableCell>
                      <TableCell align="right">Received</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(po.lines || []).length === 0 && (
                      <TableRow>
                        <TableCell colSpan={10}>
                          <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
                            This purchase order has no line items.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                    {(po.lines || []).map((line) => (
                      <TableRow key={line.id} hover>
                        <TableCell>{line.line_number}</TableCell>
                        <TableCell>{line.item_code || '—'}</TableCell>
                        <TableCell>{line.description}</TableCell>
                        <TableCell>{line.hsn_code || '—'}</TableCell>
                        <TableCell align="right">{line.quantity}</TableCell>
                        <TableCell>{line.unit || '—'}</TableCell>
                        <TableCell align="right">{formatCurrency(line.unit_price)}</TableCell>
                        <TableCell align="right">{line.tax_rate}</TableCell>
                        <TableCell align="right">{formatCurrency(line.line_total)}</TableCell>
                        <TableCell align="right">{line.received_qty ?? 0}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

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
    </Box>
  );
}
