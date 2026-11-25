import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
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
  IconButton,
  Link,
  Stack,
  Typography,
} from '@mui/material';
import DescriptionIcon from '@mui/icons-material/Description';
import EmailIcon from '@mui/icons-material/Email';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import CloseIcon from '@mui/icons-material/Close';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import api from '../api/client';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormTextField } from '../components/FormControls';
import { useSnackbar } from '../context/SnackbarContext';
import usePagedList from '../hooks/usePagedList';
import { ACCEPTED_UPLOAD_MIME } from '../utils/constants';
import { formatCurrency, formatDateTime, getApiErrorMessage } from '../utils/format';

function UploadResultList({ result }) {
  const uploaded = result?.uploaded || [];
  const failed = result?.failed || [];
  if (uploaded.length === 0 && failed.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No files were processed.
      </Typography>
    );
  }
  return (
    <Stack spacing={1}>
      {uploaded.map((item) => (
        <Stack key={item.id} direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
          <DescriptionIcon fontSize="small" color="action" />
          <Typography variant="body2" sx={{ flexGrow: 1, minWidth: 120 }}>
            {item.file_name}
          </Typography>
          <StatusChip status={item.status} display={item.status} />
          <StatusChip status={item.ocr_status} />
          <IconButton
            size="small"
            component={RouterLink}
            to={`/invoices/${item.id}`}
            aria-label={`View ${item.file_name}`}
          >
            <VisibilityOutlinedIcon fontSize="small" />
          </IconButton>
        </Stack>
      ))}
      {failed.map((item, index) => (
        <Stack key={`failed-${index}`} direction="row" alignItems="center" spacing={1}>
          <DescriptionIcon fontSize="small" color="error" />
          <Typography variant="body2" color="error">
            {item.file_name}: {item.reason}
          </Typography>
        </Stack>
      ))}
    </Stack>
  );
}

export default function InvoiceUploadPage() {
  const snackbar = useSnackbar();
  const [files, setFiles] = useState([]);
  const [vendorId, setVendorId] = useState('');
  const [poNumber, setPoNumber] = useState('');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [vendorOptions, setVendorOptions] = useState([]);
  const [poOptions, setPoOptions] = useState([]);

  const [emailOpen, setEmailOpen] = useState(false);
  const [emailForm, setEmailForm] = useState({ from_email: '', subject: '' });
  const [emailFiles, setEmailFiles] = useState([]);
  const [emailSubmitting, setEmailSubmitting] = useState(false);
  const [emailResult, setEmailResult] = useState(null);

  const onDrop = useCallback((accepted, rejected) => {
    setFiles((prev) => [...prev, ...accepted]);
    rejected.forEach((rej) =>
      snackbar.error(
        `${rej.file.name}: ${rej.errors.map((e) => (e.code === 'file-too-large' ? 'exceeds the 25 MB limit' : e.message)).join(', ')}`
      )
    );
  }, [snackbar]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_UPLOAD_MIME,
    multiple: true,
    maxSize: 25 * 1024 * 1024,
  });

  const onEmailDrop = useCallback((accepted) => {
    setEmailFiles((prev) => [...prev, ...accepted]);
  }, []);

  const {
    getRootProps: getEmailRootProps,
    getInputProps: getEmailInputProps,
    isDragActive: emailDragActive,
  } = useDropzone({
    onDrop: onEmailDrop,
    accept: ACCEPTED_UPLOAD_MIME,
    multiple: true,
    maxSize: 25 * 1024 * 1024,
  });

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

  const fetchFn = useCallback(
    (page, pageSize) =>
      api.get('/invoices', { params: { page: page + 1, pageSize } }).then((res) => res.data),
    []
  );
  const recentList = usePagedList(fetchFn, []);

  const upload = async () => {
    if (files.length === 0) {
      snackbar.warning('Select at least one file to upload');
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));
      if (vendorId) formData.append('vendor_id', vendorId);
      if (poNumber) formData.append('po_number', poNumber);
      const { data } = await api.post('/invoices/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(data);
      setFiles([]);
      snackbar.success(`Uploaded ${(data.uploaded || []).length} file(s) — OCR is running in the background`);
      recentList.reload();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  const submitEmailIngest = async () => {
    if (!emailForm.from_email.trim() || emailFiles.length === 0) {
      snackbar.warning('From email and at least one attachment are required');
      return;
    }
    setEmailSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('from_email', emailForm.from_email.trim());
      formData.append('subject', emailForm.subject);
      emailFiles.forEach((file) => formData.append('attachments', file));
      const { data } = await api.post('/invoices/email-ingest', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setEmailResult(data);
      setEmailFiles([]);
      snackbar.success(`Ingested ${(data.uploaded || []).length} attachment(s) from email`);
      recentList.reload();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setEmailSubmitting(false);
    }
  };

  const recentColumns = [
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
    {
      id: 'total_amount',
      label: 'Total',
      align: 'right',
      render: (row) => formatCurrency(row.total_amount),
    },
    { id: 'status', label: 'Status', render: (row) => <StatusChip status={row.status} display={row.status_display} /> },
    { id: 'ocr_status', label: 'OCR', render: (row) => <StatusChip status={row.ocr_status} /> },
    { id: 'created_at', label: 'Uploaded', render: (row) => formatDateTime(row.created_at) },
  ];

  return (
    <Box>
      <PageHeader
        title="Upload Invoices"
        subtitle="Drop supplier invoice documents — OCR extraction runs automatically in the background."
        actions={
          <Button variant="outlined" startIcon={<EmailIcon />} onClick={() => setEmailOpen(true)}>
            Simulate email
          </Button>
        }
      />

      <Card>
        <CardContent>
          <Box
            {...getRootProps()}
            sx={{
              border: '2px dashed',
              borderColor: isDragActive ? 'secondary.main' : 'divider',
              borderRadius: 2,
              p: { xs: 4, md: 6 },
              textAlign: 'center',
              cursor: 'pointer',
              bgcolor: isDragActive ? 'rgba(14, 131, 136, 0.06)' : 'background.default',
              transition: 'all 0.2s',
            }}
          >
            <input {...getInputProps()} />
            <UploadFileIcon sx={{ fontSize: 44, color: 'text.secondary', mb: 1 }} />
            <Typography variant="subtitle1" fontWeight={600}>
              {isDragActive ? 'Drop files here…' : 'Drag & drop invoice files here, or click to browse'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              PDF, JPG, PNG or TIFF · multiple files supported · max 25 MB each
            </Typography>
          </Box>

          {files.length > 0 && (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
              {files.map((file) => (
                <Chip
                  key={file.name + file.size}
                  icon={<DescriptionIcon />}
                  label={`${file.name} (${Math.round(file.size / 1024)} KB)`}
                  onDelete={() => setFiles((prev) => prev.filter((f) => f !== file))}
                  variant="outlined"
                />
              ))}
            </Stack>
          )}

          <Divider sx={{ my: 2.5 }} />

          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
            <FormSelect
              label="Vendor (optional)"
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
              options={vendorOptions.map((v) => ({ value: v.id, label: `${v.code} — ${v.name}` }))}
              emptyOption="No vendor selected"
              sx={{ maxWidth: { sm: 320 } }}
            />
            <FormSelect
              label="Purchase order (optional)"
              value={poNumber}
              onChange={(e) => setPoNumber(e.target.value)}
              options={poOptions.map((p) => ({ value: p.po_number, label: `${p.po_number} — ${p.vendor?.name || ''}` }))}
              emptyOption="No PO selected"
              sx={{ maxWidth: { sm: 320 } }}
            />
            <Button
              variant="contained"
              startIcon={uploading ? undefined : <UploadFileIcon />}
              disabled={uploading || files.length === 0}
              onClick={upload}
            >
              {uploading ? 'Uploading…' : `Upload ${files.length || ''} file(s)`}
            </Button>
          </Stack>

          {result && (
            <Box sx={{ mt: 3 }}>
              <Divider sx={{ mb: 2 }} />
              <Typography variant="subtitle2" gutterBottom>
                Upload results
              </Typography>
              <UploadResultList result={result} />
            </Box>
          )}
        </CardContent>
      </Card>

      <Box sx={{ mt: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} gutterBottom>
          Recently uploaded invoices
        </Typography>
        <DataTable
          columns={recentColumns}
          rows={recentList.rows}
          count={recentList.count}
          page={recentList.page}
          pageSize={recentList.pageSize}
          onPageChange={recentList.setPage}
          onPageSizeChange={recentList.changePageSize}
          loading={recentList.loading}
          error={recentList.error}
          onRetry={recentList.reload}
          emptyTitle="No invoices yet"
          emptySubtitle="Upload invoice files above to populate this list."
          minWidth={640}
        />
      </Box>

      {/* Email ingestion channel simulation */}
      <Dialog
        open={emailOpen}
        onClose={() => !emailSubmitting && setEmailOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Simulate email ingestion</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Demo shortcut: files placed in the project's <code>sample_invoices/</code> folder can be
              ingested with <code>python manage.py ingest_folder sample_invoices</code> (same pipeline,
              tagged source = Email).
            </Typography>
            <FormTextField
              label="From email"
              type="email"
              value={emailForm.from_email}
              onChange={(e) => setEmailForm((prev) => ({ ...prev, from_email: e.target.value }))}
            />
            <FormTextField
              label="Subject"
              value={emailForm.subject}
              onChange={(e) => setEmailForm((prev) => ({ ...prev, subject: e.target.value }))}
            />
            <Box
              {...getEmailRootProps()}
              sx={{
                border: '2px dashed',
                borderColor: emailDragActive ? 'secondary.main' : 'divider',
                borderRadius: 1.5,
                p: 3,
                textAlign: 'center',
                cursor: 'pointer',
                bgcolor: emailDragActive ? 'rgba(14, 131, 136, 0.06)' : 'background.default',
              }}
            >
              <input {...getEmailInputProps()} />
              <Typography variant="body2" fontWeight={600}>
                {emailDragActive ? 'Drop attachments here…' : 'Drop email attachments here, or click to browse'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                PDF, JPG, PNG or TIFF
              </Typography>
            </Box>
            {emailFiles.length > 0 && (
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {emailFiles.map((file) => (
                  <Chip
                    key={file.name + file.size}
                    icon={<DescriptionIcon />}
                    label={file.name}
                    onDelete={() => setEmailFiles((prev) => prev.filter((f) => f !== file))}
                    variant="outlined"
                  />
                ))}
              </Stack>
            )}
            {emailResult && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Ingestion results
                </Typography>
                <UploadResultList result={emailResult} />
              </Box>
            )}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEmailOpen(false)} disabled={emailSubmitting} color="inherit">
            Close
          </Button>
          <Button
            variant="contained"
            onClick={submitEmailIngest}
            disabled={emailSubmitting || emailFiles.length === 0}
          >
            {emailSubmitting ? 'Ingesting…' : 'Ingest email'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
