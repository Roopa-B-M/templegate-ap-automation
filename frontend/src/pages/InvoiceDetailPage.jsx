import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  LinearProgress,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ErrorIcon from '@mui/icons-material/Error';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import SendIcon from '@mui/icons-material/Send';
import WarningIcon from '@mui/icons-material/Warning';
import api from '../api/client';
import ConfirmDialog from '../components/ConfirmDialog';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormTextField } from '../components/FormControls';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import {
  confidencePct,
  formatConfidence,
  formatCurrency,
  formatDate,
  formatDateTime,
  getApiErrorMessage,
  humanize,
  prettyJson,
  toNumber,
} from '../utils/format';
import { openBlobInNewTab } from '../utils/download';

const EDITABLE_STATUSES = ['EXTRACTED', 'VALIDATED', 'MATCHED', 'MATCH_EXCEPTION', 'EXCEPTION'];

function MetaRow({ label, value, bold }) {
  return (
    <Stack direction="row" justifyContent="space-between" sx={{ py: 0.4, gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        fontWeight={bold ? 700 : 500}
        sx={{ textAlign: 'right', wordBreak: 'break-word' }}
      >
        {value}
      </Typography>
    </Stack>
  );
}

/** Editable OCR-review form for the extracted invoice data. */
function ExtractedDataForm({ detail, vendorOptions, onSaved, onDiscard }) {
  const snackbar = useSnackbar();
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    invoice_number: detail.invoice_number || '',
    vendor_id: detail.vendor?.id || detail.vendor_id || '',
    po_number: detail.po?.po_number || '',
    invoice_date: detail.invoice_date || '',
    due_date: detail.due_date || '',
    currency: detail.currency || 'INR',
    subtotal: detail.subtotal ?? '',
    tax_amount: detail.tax_amount ?? '',
    total_amount: detail.total_amount ?? '',
    line_items: (detail.line_items || []).map((li) => ({
      description: li.description || '',
      hsn_code: li.hsn_code || '',
      quantity: li.quantity ?? '',
      unit: li.unit || '',
      unit_price: li.unit_price ?? '',
      tax_rate: li.tax_rate ?? '',
    })),
  });

  const setField = (name, value) => setForm((prev) => ({ ...prev, [name]: value }));
  const setLine = (index, name, value) =>
    setForm((prev) => ({
      ...prev,
      line_items: prev.line_items.map((row, i) => (i === index ? { ...row, [name]: value } : row)),
    }));
  const addLine = () =>
    setForm((prev) => ({
      ...prev,
      line_items: [
        ...prev.line_items,
        { description: '', hsn_code: '', quantity: '', unit: '', unit_price: '', tax_rate: '' },
      ],
    }));
  const removeLine = (index) =>
    setForm((prev) => ({ ...prev, line_items: prev.line_items.filter((_row, i) => i !== index) }));

  const save = async () => {
    if (!String(form.invoice_number).trim()) {
      snackbar.error('Invoice number is required');
      return;
    }
    if (!form.invoice_date) {
      snackbar.error('Invoice date is required');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        invoice_number: String(form.invoice_number).trim(),
        vendor_id: form.vendor_id ? Number(form.vendor_id) : null,
        po_number: form.po_number ? String(form.po_number).trim() : '',
        invoice_date: form.invoice_date,
        due_date: form.due_date || null,
        currency: form.currency || 'INR',
        subtotal: String(toNumber(form.subtotal)),
        tax_amount: String(toNumber(form.tax_amount)),
        total_amount: String(toNumber(form.total_amount)),
        line_items: form.line_items
          .filter((li) => String(li.description).trim() !== '')
          .map((li) => ({
            description: li.description,
            hsn_code: li.hsn_code || '',
            quantity: toNumber(li.quantity),
            unit: li.unit || '',
            unit_price: toNumber(li.unit_price),
            tax_rate: toNumber(li.tax_rate),
          })),
      };
      const { data } = await api.put(`/invoices/${detail.id}/extracted-fields`, payload);
      snackbar.success('Extracted data saved — validation and matching were re-run');
      onSaved(data);
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Grid container spacing={1.5}>
        <Grid item xs={12} sm={6}>
          <FormTextField
            label="Invoice number *"
            value={form.invoice_number}
            onChange={(e) => setField('invoice_number', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <FormSelect
            label="Vendor"
            value={form.vendor_id}
            onChange={(e) => setField('vendor_id', e.target.value)}
            options={vendorOptions.map((v) => ({ value: v.id, label: `${v.code} — ${v.name}` }))}
            emptyOption="No vendor"
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <FormTextField
            label="PO number (blank = none)"
            value={form.po_number}
            onChange={(e) => setField('po_number', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <FormTextField
            label="Currency"
            value={form.currency}
            onChange={(e) => setField('currency', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <FormTextField
            label="Invoice date *"
            type="date"
            value={form.invoice_date}
            onChange={(e) => setField('invoice_date', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <FormTextField
            label="Due date"
            type="date"
            value={form.due_date}
            onChange={(e) => setField('due_date', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <FormTextField
            label="Subtotal"
            type="number"
            value={form.subtotal}
            onChange={(e) => setField('subtotal', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <FormTextField
            label="Tax amount"
            type="number"
            value={form.tax_amount}
            onChange={(e) => setField('tax_amount', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <FormTextField
            label="Total amount"
            type="number"
            value={form.total_amount}
            onChange={(e) => setField('total_amount', e.target.value)}
          />
        </Grid>
      </Grid>

      <Typography variant="subtitle2" sx={{ mt: 1 }}>
        Line items
      </Typography>
      <TableContainer sx={{ overflowX: 'auto' }}>
        <Table size="small" sx={{ minWidth: 640 }}>
          <TableHead>
            <TableRow>
              <TableCell>Description</TableCell>
              <TableCell sx={{ width: 100 }}>HSN</TableCell>
              <TableCell sx={{ width: 90 }}>Qty</TableCell>
              <TableCell sx={{ width: 80 }}>Unit</TableCell>
              <TableCell sx={{ width: 110 }}>Unit Price</TableCell>
              <TableCell sx={{ width: 90 }}>Tax %</TableCell>
              <TableCell align="right" sx={{ width: 110 }}>
                Line Total
              </TableCell>
              <TableCell sx={{ width: 44 }} />
            </TableRow>
          </TableHead>
          <TableBody>
            {form.line_items.length === 0 && (
              <TableRow>
                <TableCell colSpan={8}>
                  <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
                    No line items — add one below.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {form.line_items.map((line, index) => (
              <TableRow key={index}>
                <TableCell>
                  <TextField
                    fullWidth
                    size="small"
                    placeholder="Description"
                    value={line.description}
                    onChange={(e) => setLine(index, 'description', e.target.value)}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    fullWidth
                    size="small"
                    value={line.hsn_code}
                    onChange={(e) => setLine(index, 'hsn_code', e.target.value)}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={line.quantity}
                    onChange={(e) => setLine(index, 'quantity', e.target.value)}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    fullWidth
                    size="small"
                    value={line.unit}
                    onChange={(e) => setLine(index, 'unit', e.target.value)}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={line.unit_price}
                    onChange={(e) => setLine(index, 'unit_price', e.target.value)}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={line.tax_rate}
                    onChange={(e) => setLine(index, 'tax_rate', e.target.value)}
                  />
                </TableCell>
                <TableCell align="right">
                  {formatCurrency(
                    toNumber(line.quantity) * toNumber(line.unit_price) * (1 + toNumber(line.tax_rate) / 100)
                  )}
                </TableCell>
                <TableCell>
                  <IconButton size="small" onClick={() => removeLine(index)} aria-label="Remove line">
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Button startIcon={<AddIcon />} size="small" onClick={addLine}>
        Add line item
      </Button>

      <Stack direction="row" spacing={1} justifyContent="flex-end">
        <Button color="inherit" onClick={onDiscard} disabled={saving}>
          Discard changes
        </Button>
        <Button variant="contained" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save & re-validate'}
        </Button>
      </Stack>
    </Stack>
  );
}

export default function InvoiceDetailPage() {
  const { id } = useParams();
  const { isAdmin, isClerk, isFinance } = useAuth();
  const snackbar = useSnackbar();
  const navigate = useNavigate();

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [fileLoading, setFileLoading] = useState(false);
  const [ocrTextOpen, setOcrTextOpen] = useState(false);
  const [matchDetailsOpen, setMatchDetailsOpen] = useState(false);
  const [confirmState, setConfirmState] = useState(null);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');
  const [matchPoId, setMatchPoId] = useState('');
  const [formKey, setFormKey] = useState(0);
  const [vendorOptions, setVendorOptions] = useState([]);
  const [poOptions, setPoOptions] = useState([]);
  const [erpLoading, setErpLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/invoices/${id}`);
      setDetail(data);
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

  // Auto-poll while server-side OCR is running; stops on COMPLETED/FAILED.
  const ocrStatus = detail?.ocr_status;
  useEffect(() => {
    if (ocrStatus !== 'PROCESSING') return undefined;
    const timer = setInterval(() => {
      api
        .get(`/invoices/${id}`)
        .then((res) => setDetail(res.data))
        .catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [ocrStatus, id]);

  useEffect(() => {
    api
      .get('/vendors', { params: { pageSize: 100 } })
      .then((res) => setVendorOptions(res.data.results || []))
      .catch(() => {});
    api
      .get('/purchase-orders', { params: { status: 'OPEN', pageSize: 100 } })
      .then((res) => setPoOptions(res.data.results || []))
      .catch(() => {});
  }, []);

  const runAction = async ({ url, body, successMessage, returnsDetail = false }) => {
    setActionLoading(true);
    try {
      const { data } = await api.post(url, body || {});
      if (returnsDetail && data && data.invoice_number) {
        setDetail(data);
      } else {
        await load();
      }
      snackbar.success(successMessage);
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setActionLoading(false);
    }
  };

  const confirmAction = (options) => setConfirmState(options);

  const viewFile = async () => {
    setFileLoading(true);
    try {
      const res = await api.get(`/invoices/${id}/file`, { responseType: 'blob' });
      openBlobInNewTab(res.data);
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setFileLoading(false);
    }
  };

  const postToErp = async () => {
    setErpLoading(true);
    try {
      const { data } = await api.post(`/accounting/post-invoice/${id}`);
      snackbar.success(data.detail || 'Voucher posted to the ERP');
      await load();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setErpLoading(false);
    }
  };

  if (loadError && !detail) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={load}>
            Retry
          </Button>
        }
      >
        Failed to load invoice: {getApiErrorMessage(loadError)}
      </Alert>
    );
  }

  if (!detail) {
    return (
      <Box>
        <Skeleton variant="rectangular" width={300} height={36} sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          <Grid item xs={12} lg={4}>
            <Skeleton variant="rounded" height={420} />
          </Grid>
          <Grid item xs={12} lg={4}>
            <Skeleton variant="rounded" height={420} />
          </Grid>
          <Grid item xs={12} lg={4}>
            <Skeleton variant="rounded" height={420} />
          </Grid>
        </Grid>
      </Box>
    );
  }

  const status = detail.status;
  const canEditExtracted = (isAdmin || isClerk) && EDITABLE_STATUSES.includes(status);
  const canValidate = ['EXTRACTED', 'VALIDATED'].includes(status);  const canSubmit = ['VALIDATED', 'MATCHED'].includes(status);
  const canOverride = isAdmin && ['MATCH_EXCEPTION', 'EXCEPTION'].includes(status);
  const canCancel = !['PAID', 'CANCELLED'].includes(status);
  const canMatch = EDITABLE_STATUSES.includes(status);
  const confidence = confidencePct(detail.ocr_confidence);
  const confidenceColor = confidence >= 80 ? 'success' : confidence >= 60 ? 'warning' : 'error';
  const approvalTasks = [...(detail.approval_tasks || [])].sort((a, b) => (a.level || 0) - (b.level || 0));
  const canPostErp = (isAdmin || isFinance) && ['APPROVED', 'PAID'].includes(status);
  const extractionFields = detail.extracted_data?.fields || null;

  return (
    <Box>
      <PageHeader
        title={`Invoice ${detail.invoice_number}`}
        subtitle={detail.vendor_name || detail.vendor?.name || 'Unassigned vendor'}
        actions={
          <>
            <StatusChip status={detail.status} display={detail.status_display} />
            <Button color="inherit" onClick={() => navigate('/invoices')}>
              Back to invoices
            </Button>
          </>
        }
      />

      <Grid container spacing={3}>
        {/* LEFT: meta + OCR */}
        <Grid item xs={12} lg={4}>
          <Stack spacing={3}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                  Invoice details
                </Typography>
                <Divider sx={{ mb: 1.5 }} />
                <MetaRow label="Invoice #" value={detail.invoice_number} bold />
                <MetaRow label="Vendor" value={detail.vendor_name || detail.vendor?.name || '—'} />
                <MetaRow label="Purchase order" value={detail.po?.po_number || '—'} />
                <MetaRow label="Invoice date" value={formatDate(detail.invoice_date)} />
                <MetaRow label="Due date" value={formatDate(detail.due_date)} />
                <MetaRow label="Subtotal" value={formatCurrency(detail.subtotal)} />
                <MetaRow label="Tax" value={formatCurrency(detail.tax_amount)} />
                <MetaRow label="Total" value={formatCurrency(detail.total_amount)} bold />
                <MetaRow label="Source" value={detail.source_display || humanize(detail.source)} />
                <MetaRow
                  label="File"
                  value={detail.file_name ? `${detail.file_name}${detail.file_type ? ` (${detail.file_type})` : ''}` : '—'}
                />
                <MetaRow label="Pages" value={detail.page_count ?? '—'} />
                <MetaRow label="Created by" value={detail.created_by?.username || '—'} />
                <MetaRow label="Created at" value={formatDateTime(detail.created_at)} />
                {detail.approved_at && <MetaRow label="Approved at" value={formatDateTime(detail.approved_at)} />}
                {detail.paid_at && <MetaRow label="Paid at" value={formatDateTime(detail.paid_at)} />}
                <Button
                  sx={{ mt: 2 }}
                  variant="outlined"
                  startIcon={fileLoading ? <CircularProgress size={16} /> : <OpenInNewIcon />}
                  onClick={viewFile}
                  disabled={fileLoading}
                >
                  View invoice file
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="subtitle1" fontWeight={700}>
                    OCR
                  </Typography>
                  <StatusChip status={detail.ocr_status} />
                </Stack>
                <Box sx={{ mt: 2 }}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">
                      Extraction confidence
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {formatConfidence(detail.ocr_confidence)}
                    </Typography>
                  </Stack>
                  <LinearProgress
                    variant="determinate"
                    value={confidence}
                    color={confidenceColor}
                    sx={{ mt: 1, height: 8, borderRadius: 4 }}
                  />
                  {detail.extracted_data?.extraction_engine && (
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
                      <Typography variant="caption" color="text.secondary">
                        Engine: {detail.extracted_data.extraction_engine}
                      </Typography>
                      {detail.extracted_data.ai_assist_used && (
                        <Chip size="small" color="secondary" variant="outlined" label="AI assist used" />
                      )}
                    </Stack>
                  )}
                </Box>
                {detail.ocr_error && (
                  <Alert severity="error" variant="outlined" sx={{ mt: 2 }}>
                    {detail.ocr_error}
                  </Alert>
                )}
                {detail.ocr_status === 'PROCESSING' && (
                  <Alert severity="info" variant="outlined" icon={<CircularProgress size={16} />} sx={{ mt: 2 }}>
                    OCR is running server-side — this page refreshes automatically every few seconds.
                  </Alert>
                )}
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
                  {['COMPLETED', 'FAILED'].includes(detail.ocr_status) && (
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<AutorenewIcon />}
                      onClick={() =>
                        confirmAction({
                          title: 'Re-run OCR',
                          message:
                            'Reprocess this document through OCR? The extracted data will be replaced with a fresh extraction.',
                          confirmText: 'Reprocess',
                          action: () =>
                            runAction({
                              url: `/invoices/${id}/reprocess-ocr`,
                              successMessage: 'OCR reprocessing started',
                            }).then(() => setConfirmState(null)),
                        })
                      }
                    >
                      Reprocess OCR
                    </Button>
                  )}
                  {detail.raw_ocr_text && (
                    <Button size="small" onClick={() => setOcrTextOpen((v) => !v)}>
                      {ocrTextOpen ? 'Hide' : 'Show'} raw OCR text
                    </Button>
                  )}
                </Stack>
                <Collapse in={ocrTextOpen} sx={{ mt: 1 }}>
                  <Box
                    component="pre"
                    sx={{
                      m: 0,
                      p: 1.5,
                      bgcolor: '#F1F5F9',
                      borderRadius: 1.5,
                      fontSize: 12,
                      maxHeight: 240,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {detail.raw_ocr_text}
                  </Box>
                </Collapse>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="subtitle1" fontWeight={700}>
                    Accounting / ERP
                  </Typography>
                  <Chip
                    size="small"
                    color={detail.erp_status === 'SYNCED' ? 'success' : detail.erp_status === 'FAILED' ? 'error' : 'default'}
                    variant={detail.erp_status === 'NOT_SYNCED' ? 'outlined' : 'filled'}
                    label={humanize(detail.erp_status || 'NOT_SYNCED')}
                  />
                </Stack>
                {detail.erp_reference && (
                  <MetaRow label="ERP reference" value={detail.erp_reference} bold />
                )}
                {!canPostErp ? (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Posting is available to Finance/Admin once the invoice is APPROVED or PAID.
                  </Typography>
                ) : (
                  <Stack spacing={1} sx={{ mt: 1.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Posting is simulated locally — the purchase voucher is built and validated,
                      and an ERP reference is returned. No live ERP connection is made.
                    </Typography>
                    <Button
                      variant="contained"
                      startIcon={erpLoading ? <CircularProgress size={16} /> : <SendIcon />}
                      onClick={postToErp}
                      disabled={erpLoading || detail.erp_status === 'SYNCED'}
                    >
                      {detail.erp_status === 'SYNCED' ? 'Posted to ERP' : 'Post to ERP'}
                    </Button>
                    <Button size="small" color="inherit" onClick={() => navigate('/accounting')}>
                      Open Accounting / ERP page
                    </Button>
                  </Stack>
                )}
              </CardContent>
            </Card>
          </Stack>
        </Grid>

        {/* MIDDLE: extracted data review */}
        <Grid item xs={12} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="subtitle1" fontWeight={700}>
                  Extracted data
                </Typography>
                {canEditExtracted ? (
                  <Chip size="small" color="info" label="Editable" />
                ) : (
                  <Chip size="small" label="Read-only" />
                )}
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                {canEditExtracted
                  ? 'Review and correct the OCR output. Saving re-runs validation and PO matching.'
                  : 'Editing is available to Admins and AP Clerks while the invoice is pre-approval.'}
              </Typography>
              <Divider sx={{ my: 2 }} />
              {canEditExtracted ? (
                <ExtractedDataForm
                  key={formKey}
                  detail={detail}
                  vendorOptions={vendorOptions}
                  onSaved={(data) => {
                    setDetail(data);
                    setFormKey((k) => k + 1);
                  }}
                  onDiscard={() => setFormKey((k) => k + 1)}
                />
              ) : (
                <Stack spacing={2}>
                  {extractionFields && Object.keys(extractionFields).length > 0 && (
                    <Box>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                        Per-field source (engine · confidence)
                      </Typography>
                      <Stack spacing={0.5}>
                        {Object.entries(extractionFields).map(([key, entry]) => (
                          <Stack key={key} direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                            <Typography variant="body2" fontWeight={600} sx={{ wordBreak: 'break-word' }}>
                              {entry?.value !== null && typeof entry?.value === 'object'
                                ? prettyJson(entry.value)
                                : String(entry?.value ?? '—')}
                            </Typography>
                            <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flexShrink: 0 }}>
                              {entry?.engine === 'ai' && (
                                <Chip size="small" color="secondary" variant="outlined" label="AI" />
                              )}
                              {entry?.engine === 'rule' && (
                                <Chip size="small" variant="outlined" label="Rule" />
                              )}
                              {typeof entry?.confidence === 'number' && (
                                <Typography variant="caption" color="text.secondary">
                                  {Math.round(entry.confidence * 100)}%
                                </Typography>
                              )}
                            </Stack>
                          </Stack>
                        ))}
                      </Stack>
                    </Box>
                  )}
                  {Object.keys(detail.extracted_data || {}).length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      No extracted data available yet.
                    </Typography>
                  ) : (
                    <Grid container spacing={1}>
                      {Object.entries(detail.extracted_data || {})
                        .filter(([key]) => key !== 'line_items' && key !== 'fields')
                        .map(([key, value]) => (
                          <Grid item xs={6} key={key}>
                            <Typography variant="caption" color="text.secondary">
                              {humanize(key)}
                            </Typography>
                            <Typography variant="body2" fontWeight={600} sx={{ wordBreak: 'break-word' }}>
                              {value !== null && typeof value === 'object' ? prettyJson(value) : String(value ?? '—')}
                            </Typography>
                          </Grid>
                        ))}
                    </Grid>
                  )}
                  {(detail.line_items || []).length > 0 && (
                    <TableContainer sx={{ overflowX: 'auto' }}>
                      <Table size="small" sx={{ minWidth: 420 }}>
                        <TableHead>
                          <TableRow>
                            <TableCell>Description</TableCell>
                            <TableCell align="right">Qty</TableCell>
                            <TableCell align="right">Unit Price</TableCell>
                            <TableCell align="right">Tax %</TableCell>
                            <TableCell align="right">Total</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {detail.line_items.map((line) => (
                            <TableRow key={line.id}>
                              <TableCell>{line.description}</TableCell>
                              <TableCell align="right">{line.quantity}</TableCell>
                              <TableCell align="right">{formatCurrency(line.unit_price)}</TableCell>
                              <TableCell align="right">{line.tax_rate}</TableCell>
                              <TableCell align="right">{formatCurrency(line.line_total)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* RIGHT: validation, matching, actions, approvals, payment */}
        <Grid item xs={12} lg={4}>
          <Stack spacing={3}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                  Validation results
                </Typography>
                {(detail.validation_results || []).length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No validation checks recorded yet. Run validation to evaluate this invoice.
                  </Typography>
                ) : (
                  <Stack spacing={1} sx={{ mt: 1 }}>
                    {detail.validation_results.map((result) => (
                      <Stack key={result.id} direction="row" spacing={1} alignItems="flex-start">
                        <Box sx={{ mt: 0.25 }}>
                          {result.status === 'PASS' ? (
                            <CheckCircleIcon color="success" fontSize="small" />
                          ) : result.status === 'WARN' ? (
                            <WarningIcon color="warning" fontSize="small" />
                          ) : (
                            <ErrorIcon color="error" fontSize="small" />
                          )}
                        </Box>
                        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                          <Typography variant="body2" fontWeight={600}>
                            {result.check_code_display || humanize(result.check_code)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {result.message}
                          </Typography>
                        </Box>
                        <StatusChip status={result.status} />
                      </Stack>
                    ))}
                  </Stack>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography variant="subtitle1" fontWeight={700}>
                    PO Matching
                  </Typography>
                  {detail.match_result && (
                    <StatusChip
                      status={detail.match_result.status}
                      display={detail.match_result.status_display}
                    />
                  )}
                </Stack>
                {detail.match_result ? (
                  <>
                    <MetaRow
                      label="Match type"
                      value={detail.match_result.match_type_display || humanize(detail.match_result.match_type)}
                    />
                    <MetaRow label="Total variance" value={formatCurrency(detail.match_result.total_variance)} />
                    <MetaRow label="Matched at" value={formatDateTime(detail.match_result.created_at)} />
                    <Button size="small" sx={{ mt: 1 }} onClick={() => setMatchDetailsOpen((v) => !v)}>
                      {matchDetailsOpen ? 'Hide' : 'View'} match details
                    </Button>
                    <Collapse in={matchDetailsOpen} sx={{ mt: 1 }}>
                      <Box
                        component="pre"
                        sx={{
                          m: 0,
                          p: 1.5,
                          bgcolor: '#F1F5F9',
                          borderRadius: 1.5,
                          fontSize: 12,
                          maxHeight: 220,
                          overflow: 'auto',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {prettyJson(detail.match_result.details) || '—'}
                      </Box>
                    </Collapse>
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    This invoice has not been matched against a purchase order yet.
                  </Typography>
                )}
                {canMatch && (
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mt: 2 }} alignItems="flex-start">
                    <FormSelect
                      label="PO to match against"
                      value={matchPoId}
                      onChange={(e) => setMatchPoId(e.target.value)}
                      options={poOptions.map((po) => ({
                        value: po.id,
                        label: `${po.po_number} · ${po.vendor?.name || ''}`,
                      }))}
                      emptyOption="Auto (best match)"
                    />
                    <Button
                      variant="contained"
                      onClick={() =>
                        confirmAction({
                          title: 'Run PO matching',
                          message: 'Run purchase order matching for this invoice now?',
                          confirmText: 'Run match',
                          action: () =>
                            runAction({
                              url: `/invoices/${id}/match`,
                              body: matchPoId ? { po_id: Number(matchPoId) } : {},
                              successMessage: 'Matching completed',
                              returnsDetail: true,
                            }).then(() => setConfirmState(null)),
                        })
                      }
                    >
                      Run match
                    </Button>
                  </Stack>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                  Workflow actions
                </Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {canValidate && (
                    <Button
                      variant="outlined"
                      onClick={() =>
                        confirmAction({
                          title: 'Run validation',
                          message: 'Re-run all validation checks for this invoice?',
                          confirmText: 'Validate',
                          action: () =>
                            runAction({
                              url: `/invoices/${id}/validate`,
                              successMessage: 'Validation completed',
                              returnsDetail: true,
                            }).then(() => setConfirmState(null)),
                        })
                      }
                    >
                      Validate
                    </Button>
                  )}
                  {canSubmit && (
                    <Button
                      variant="contained"
                      startIcon={<SendIcon />}
                      onClick={() =>
                        confirmAction({
                          title: 'Submit for approval',
                          message: 'Route this invoice into the approval workflow?',
                          confirmText: 'Submit',
                          action: () =>
                            runAction({
                              url: `/invoices/${id}/submit-approval`,
                              successMessage: 'Invoice submitted for approval',
                              returnsDetail: true,
                            }).then(() => setConfirmState(null)),
                        })
                      }
                    >
                      Submit for approval
                    </Button>
                  )}
                  {canOverride && (
                    <Button
                      variant="outlined"
                      color="warning"
                      onClick={() => {
                        setOverrideReason('');
                        setOverrideOpen(true);
                      }}
                    >
                      Override exception
                    </Button>
                  )}
                  {canCancel && (
                    <Button
                      variant="outlined"
                      color="error"
                      onClick={() =>
                        confirmAction({
                          title: 'Cancel invoice',
                          message: 'Cancel this invoice? This action cannot be undone.',
                          confirmText: 'Cancel invoice',
                          color: 'error',
                          action: () =>
                            runAction({
                              url: `/invoices/${id}/cancel`,
                              successMessage: 'Invoice cancelled',
                            }).then(() => setConfirmState(null)),
                        })
                      }
                    >
                      Cancel invoice
                    </Button>
                  )}
                  {!canValidate && !canSubmit && !canOverride && !canCancel && (
                    <Typography variant="body2" color="text.secondary">
                      No workflow actions available in the “{detail.status_display || humanize(status)}” state.
                    </Typography>
                  )}
                </Stack>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                  Approval timeline
                </Typography>
                {approvalTasks.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No approval tasks yet.
                  </Typography>
                ) : (
                  <Stack spacing={1.5} sx={{ mt: 1 }}>
                    {approvalTasks.map((task) => (
                      <Box
                        key={task.id}
                        sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1.5, p: 1.5 }}
                      >
                        <Stack
                          direction="row"
                          justifyContent="space-between"
                          alignItems="center"
                          flexWrap="wrap"
                          useFlexGap
                        >
                          <Typography variant="body2" fontWeight={700}>
                            Level {task.level}
                          </Typography>
                          <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
                            {task.is_parallel && (
                              <Chip size="small" variant="outlined" color="info" label="Parallel — all must approve" />
                            )}
                            {task.escalated && (
                              <Chip
                                size="small"
                                color="error"
                                icon={<WarningIcon sx={{ fontSize: 14 }} />}
                                label="Escalated"
                              />
                            )}
                            <StatusChip status={task.status} display={task.status_display} />
                          </Stack>
                        </Stack>
                        <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                          <Typography variant="caption" color="text.secondary">
                            Approver: <b>{task.approver?.username || task.approver_role || '—'}</b>
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Due: {formatDateTime(task.due_at)}
                          </Typography>
                          {task.reminder_count > 0 && (
                            <Typography variant="caption" color="text.secondary">
                              Reminders sent: {task.reminder_count}
                            </Typography>
                          )}
                          {task.approved_at && (
                            <Typography variant="caption" color="text.secondary">
                              Approved: {formatDateTime(task.approved_at)}
                            </Typography>
                          )}
                        </Stack>
                        {task.comments && (
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                            Comments: “{task.comments}”
                          </Typography>
                        )}
                      </Box>
                    ))}
                  </Stack>
                )}
              </CardContent>
            </Card>

            {detail.payment && (
              <Card>
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle1" fontWeight={700}>
                      Payment
                    </Typography>
                    <StatusChip status={detail.payment.status} display={detail.payment.status_display} />
                  </Stack>
                  <Box sx={{ mt: 1 }}>
                    <MetaRow label="Payment #" value={detail.payment.payment_number} />
                    <MetaRow label="Amount" value={formatCurrency(detail.payment.amount)} />
                    <MetaRow label="Method" value={detail.payment.method || '—'} />
                    <MetaRow label="Scheduled" value={formatDate(detail.payment.scheduled_date)} />
                    <MetaRow label="Processed" value={formatDate(detail.payment.processed_date)} />
                    {detail.payment.bank_reference && (
                      <MetaRow label="Bank reference" value={detail.payment.bank_reference} />
                    )}
                  </Box>
                  {detail.payment.failure_reason && (
                    <Alert severity="error" variant="outlined" sx={{ mt: 1 }}>
                      {detail.payment.failure_reason}
                    </Alert>
                  )}
                  <Button size="small" component={RouterLink} to="/payments" sx={{ mt: 1.5 }}>
                    Go to payments
                  </Button>
                </CardContent>
              </Card>
            )}
          </Stack>
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

      {/* Admin override exception dialog */}
      <Dialog
        open={overrideOpen}
        onClose={() => !actionLoading && setOverrideOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Override exception</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Provide a reason for overriding this exception. The invoice will move forward in the workflow.
          </Typography>
          <FormTextField
            label="Reason"
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            multiline
            minRows={3}
            autoFocus
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setOverrideOpen(false)} disabled={actionLoading} color="inherit">
            Cancel
          </Button>
          <Button
            variant="contained"
            color="warning"
            disabled={actionLoading || !overrideReason.trim()}
            onClick={async () => {
              await runAction({
                url: `/invoices/${id}/override-exception`,
                body: { reason: overrideReason.trim() },
                successMessage: 'Exception overridden',
                returnsDetail: true,
              });
              setOverrideOpen(false);
            }}
          >
            Override
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
