import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
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
  Grid,
  IconButton,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditIcon from '@mui/icons-material/Edit';
import SendIcon from '@mui/icons-material/Send';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import VerifiedIcon from '@mui/icons-material/Verified';
import api from '../api/client';
import ConfirmDialog from '../components/ConfirmDialog';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSwitch, FormTextField } from '../components/FormControls';
import VendorFormFields, { EMPTY_VENDOR_FORM, validateVendorForm } from '../components/VendorFormFields';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import { formatCurrency, formatDate, formatDateTime, getApiErrorMessage } from '../utils/format';

const EMPTY_BANK_FORM = {
  account_name: '',
  account_number: '',
  ifsc: '',
  bank_name: '',
  branch: '',
  upi_id: '',
  is_primary: false,
};

function MetaRow({ label, value }) {
  return (
    <Stack direction="row" justifyContent="space-between" sx={{ py: 0.4, gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={500} sx={{ textAlign: 'right', wordBreak: 'break-word' }}>
        {value}
      </Typography>
    </Stack>
  );
}

export default function VendorDetailPage() {
  const { id } = useParams();
  const { isAdmin, isClerk, isFinance } = useAuth();
  const snackbar = useSnackbar();
  const navigate = useNavigate();

  const [vendor, setVendor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [confirmState, setConfirmState] = useState(null);

  // Notes dialog (approve / reject)
  const [notesOpen, setNotesOpen] = useState(false); // 'approve' | 'reject'
  const [notes, setNotes] = useState('');

  // Vendor edit dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState(EMPTY_VENDOR_FORM);
  const [editErrors, setEditErrors] = useState({});
  const [savingVendor, setSavingVendor] = useState(false);

  // Bank account dialog (add / edit)
  const [bankOpen, setBankOpen] = useState(false);
  const [bankForm, setBankForm] = useState(EMPTY_BANK_FORM);
  const [bankEditId, setBankEditId] = useState(null);
  const [savingBank, setSavingBank] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/vendors/${id}`);
      setVendor(data);
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

  const runAction = async (fn, successMessage) => {
    setActionLoading(true);
    try {
      await fn();
      snackbar.success(successMessage);
      await load();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setActionLoading(false);
      setConfirmState(null);
    }
  };

  const openEdit = () => {
    setEditForm({
      code: vendor.code || '',
      name: vendor.name || '',
      legal_name: vendor.legal_name || '',
      gstin: vendor.gstin || '',
      pan: vendor.pan || '',
      email: vendor.email || '',
      phone: vendor.phone || '',
      address_line1: vendor.address_line1 || '',
      address_line2: vendor.address_line2 || '',
      city: vendor.city || '',
      state: vendor.state || '',
      state_code: vendor.state_code || '',
      pincode: vendor.pincode || '',
    });
    setEditErrors({});
    setEditOpen(true);
  };

  const saveVendorEdit = async () => {
    const validation = validateVendorForm(editForm);
    setEditErrors(validation);
    if (Object.keys(validation).length > 0) {
      snackbar.error('Please fill in all required fields');
      return;
    }
    setSavingVendor(true);
    try {
      await api.patch(`/vendors/${id}`, editForm);
      snackbar.success('Vendor updated');
      setEditOpen(false);
      await load();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSavingVendor(false);
    }
  };

  const openBankDialog = (account = null) => {
    setBankEditId(account?.id || null);
    setBankForm(
      account
        ? {
            account_name: account.account_name || '',
            account_number: account.account_number || '',
            ifsc: account.ifsc || '',
            bank_name: account.bank_name || '',
            branch: account.branch || '',
            upi_id: account.upi_id || '',
            is_primary: Boolean(account.is_primary),
          }
        : EMPTY_BANK_FORM
    );
    setBankOpen(true);
  };

  const saveBank = async () => {
    if (!bankForm.account_name.trim() || !bankForm.account_number.trim() || !bankForm.ifsc.trim() || !bankForm.bank_name.trim()) {
      snackbar.error('Account name, number, IFSC and bank name are required');
      return;
    }
    setSavingBank(true);
    try {
      if (bankEditId) {
        await api.patch(`/vendors/${id}/bank-accounts/${bankEditId}`, bankForm);
        snackbar.success('Bank account updated');
      } else {
        await api.post(`/vendors/${id}/bank-accounts`, bankForm);
        snackbar.success('Bank account added');
      }
      setBankOpen(false);
      await load();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSavingBank(false);
    }
  };

  const submitApprovalNotes = async () => {
    if (notesOpen === 'reject' && !notes.trim()) {
      snackbar.error('Rejection notes are required');
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/vendors/${id}/${notesOpen}`, { notes: notes.trim() });
      snackbar.success(notesOpen === 'approve' ? 'Vendor approved' : 'Vendor rejected');
      setNotesOpen(false);
      setNotes('');
      await load();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setActionLoading(false);
    }
  };

  if (loadError && !vendor) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={load}>
            Retry
          </Button>
        }
      >
        Failed to load vendor: {getApiErrorMessage(loadError)}
      </Alert>
    );
  }

  if (!vendor) {
    return (
      <Box>
        <Skeleton variant="rectangular" width={300} height={36} sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Skeleton variant="rounded" height={360} />
          </Grid>
          <Grid item xs={12} md={7}>
            <Skeleton variant="rounded" height={360} />
          </Grid>
        </Grid>
      </Box>
    );
  }

  const canEdit = isAdmin || isClerk;
  const canVerifyBank = isAdmin || isFinance;

  return (
    <Box>
      <PageHeader
        title={vendor.name}
        subtitle={`${vendor.code}${vendor.status_display ? ` · ${vendor.status_display}` : ''}`}
        actions={
          <>
            <StatusChip status={vendor.status} display={vendor.status_display} />
            {vendor.status === 'DRAFT' && canEdit && (
              <Button
                variant="outlined"
                startIcon={<SendIcon />}
                onClick={() =>
                  setConfirmState({
                    title: 'Submit for approval',
                    message: 'Submit this vendor onboarding for admin approval?',
                    confirmText: 'Submit',
                    action: () => runAction(() => api.post(`/vendors/${id}/submit`), 'Vendor submitted for approval'),
                  })
                }
              >
                Submit for approval
              </Button>
            )}
            {vendor.status === 'PENDING_APPROVAL' && isAdmin && (
              <>
                <Button
                  variant="contained"
                  color="success"
                  startIcon={<ThumbUpIcon />}
                  onClick={() => {
                    setNotes('');
                    setNotesOpen('approve');
                  }}
                >
                  Approve
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<ThumbDownIcon />}
                  onClick={() => {
                    setNotes('');
                    setNotesOpen('reject');
                  }}
                >
                  Reject
                </Button>
              </>
            )}
            {canEdit && (
              <Button variant="outlined" startIcon={<EditIcon />} onClick={openEdit}>
                Edit
              </Button>
            )}
            <Button color="inherit" onClick={() => navigate('/vendors')}>
              Back
            </Button>
          </>
        }
      />

      <Grid container spacing={3}>
        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                Vendor profile
              </Typography>
              <Divider sx={{ mb: 1.5 }} />
              <MetaRow label="Legal name" value={vendor.legal_name || '—'} />
              <MetaRow label="GSTIN" value={vendor.gstin || '—'} />
              <MetaRow label="PAN" value={vendor.pan || '—'} />
              <MetaRow label="Email" value={vendor.email || '—'} />
              <MetaRow label="Phone" value={vendor.phone || '—'} />
              <MetaRow
                label="Address"
                value={
                  [vendor.address_line1, vendor.address_line2, vendor.city, `${vendor.state || ''} ${vendor.pincode || ''}`]
                    .filter(Boolean)
                    .join(', ') || '—'
                }
              />
              <MetaRow label="State code" value={vendor.state_code || '—'} />
              <MetaRow label="Invoices" value={vendor.invoice_count ?? 0} />
              <MetaRow label="Total billed" value={formatCurrency(vendor.total_billed)} bold />
              <MetaRow label="Created by" value={vendor.created_by?.username || '—'} />
              <MetaRow label="Approved by" value={vendor.approved_by?.username || '—'} />
              <MetaRow label="Created at" value={formatDateTime(vendor.created_at)} />
              <MetaRow label="Updated at" value={formatDateTime(vendor.updated_at)} />
              {vendor.onboarding_notes && (
                <Alert severity="info" variant="outlined" sx={{ mt: 1.5 }}>
                  {vendor.onboarding_notes}
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={7}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="subtitle1" fontWeight={700}>
                  Bank accounts
                </Typography>
                {canEdit && (
                  <Button size="small" startIcon={<AddIcon />} onClick={() => openBankDialog()}>
                    Add bank account
                  </Button>
                )}
              </Stack>
              {(vendor.bank_accounts || []).length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  No bank accounts recorded yet. Add one to enable payments.
                </Typography>
              ) : (
                <TableContainer sx={{ overflowX: 'auto', mt: 1 }}>
                  <Table size="small" sx={{ minWidth: 700 }}>
                    <TableHead>
                      <TableRow>
                        <TableCell>Account</TableCell>
                        <TableCell>Account #</TableCell>
                        <TableCell>IFSC</TableCell>
                        <TableCell>Bank / Branch</TableCell>
                        <TableCell>UPI</TableCell>
                        <TableCell>Flags</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {vendor.bank_accounts.map((account) => (
                        <TableRow key={account.id} hover>
                          <TableCell>{account.account_name}</TableCell>
                          <TableCell>{account.account_number}</TableCell>
                          <TableCell>{account.ifsc}</TableCell>
                          <TableCell>
                            {account.bank_name}
                            {account.branch ? ` · ${account.branch}` : ''}
                          </TableCell>
                          <TableCell>{account.upi_id || '—'}</TableCell>
                          <TableCell>
                            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                              {account.is_primary && <Chip size="small" color="info" label="Primary" />}
                              <Chip
                                size="small"
                                color={account.is_verified ? 'success' : 'warning'}
                                label={account.is_verified ? 'Verified' : 'Unverified'}
                              />
                            </Stack>
                          </TableCell>
                          <TableCell align="right">
                            <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                              {canVerifyBank && !account.is_verified && (
                                <Tooltip title="Verify bank account">
                                  <IconButton
                                    size="small"
                                    color="success"
                                    aria-label="Verify"
                                    onClick={() =>
                                      setConfirmState({
                                        title: 'Verify bank account',
                                        message: `Mark account ${account.account_number} (${account.bank_name}) as verified?`,
                                        confirmText: 'Verify',
                                        action: () =>
                                          runAction(
                                            () => api.post(`/vendors/${id}/bank-accounts/${account.id}/verify`),
                                            'Bank account verified'
                                          ),
                                      })
                                    }
                                  >
                                    <VerifiedIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              )}
                              {canEdit && (
                                <>
                                  <Tooltip title="Edit bank account">
                                    <IconButton size="small" aria-label="Edit" onClick={() => openBankDialog(account)}>
                                      <EditIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                  <Tooltip title="Delete bank account">
                                    <IconButton
                                      size="small"
                                      color="error"
                                      aria-label="Delete"
                                      onClick={() =>
                                        setConfirmState({
                                          title: 'Delete bank account',
                                          message: `Delete account ${account.account_number}? This cannot be undone.`,
                                          confirmText: 'Delete',
                                          color: 'error',
                                          action: () =>
                                            runAction(
                                              () => api.delete(`/vendors/${id}/bank-accounts/${account.id}`),
                                              'Bank account deleted'
                                            ),
                                        })
                                      }
                                    >
                                      <DeleteOutlineIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                </>
                              )}
                            </Stack>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
              {!canVerifyBank && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  Bank verification is performed by Admin or Finance users.
                </Typography>
              )}
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

      {/* Approve / reject notes dialog */}
      <Dialog open={Boolean(notesOpen)} onClose={() => !actionLoading && setNotesOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{notesOpen === 'approve' ? 'Approve vendor' : 'Reject vendor'}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            {notesOpen === 'approve'
              ? 'Optionally add onboarding notes that will be stored with the vendor.'
              : 'Rejection notes are required and stored with the vendor.'}
          </Typography>
          <FormTextField label={notesOpen === 'approve' ? 'Notes' : 'Notes *'} value={notes} onChange={(e) => setNotes(e.target.value)} multiline minRows={3} autoFocus />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setNotesOpen(false)} disabled={actionLoading} color="inherit">
            Cancel
          </Button>
          <Button
            variant="contained"
            color={notesOpen === 'approve' ? 'success' : 'error'}
            disabled={actionLoading || (notesOpen === 'reject' && !notes.trim())}
            onClick={submitApprovalNotes}
            startIcon={notesOpen === 'approve' ? <CheckCircleIcon /> : <ThumbDownIcon />}
          >
            {notesOpen === 'approve' ? 'Approve' : 'Reject'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Vendor edit dialog */}
      <Dialog open={editOpen} onClose={() => !savingVendor && setEditOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Edit vendor</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 1 }}>
            <VendorFormFields
              form={editForm}
              setField={(key, value) => setEditForm((prev) => ({ ...prev, [key]: value }))}
              errors={editErrors}
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditOpen(false)} disabled={savingVendor} color="inherit">
            Cancel
          </Button>
          <Button variant="contained" onClick={saveVendorEdit} disabled={savingVendor}>
            {savingVendor ? 'Saving…' : 'Save changes'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bank account add / edit dialog */}
      <Dialog open={bankOpen} onClose={() => !savingBank && setBankOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{bankEditId ? 'Edit bank account' : 'Add bank account'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
            <Grid item xs={12} sm={6}>
              <FormTextField label="Account name *" value={bankForm.account_name} onChange={(e) => setBankForm((prev) => ({ ...prev, account_name: e.target.value }))} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormTextField label="Account number *" value={bankForm.account_number} onChange={(e) => setBankForm((prev) => ({ ...prev, account_number: e.target.value }))} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormTextField label="IFSC *" value={bankForm.ifsc} onChange={(e) => setBankForm((prev) => ({ ...prev, ifsc: e.target.value }))} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormTextField label="Bank name *" value={bankForm.bank_name} onChange={(e) => setBankForm((prev) => ({ ...prev, bank_name: e.target.value }))} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormTextField label="Branch" value={bankForm.branch} onChange={(e) => setBankForm((prev) => ({ ...prev, branch: e.target.value }))} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormTextField label="UPI ID" value={bankForm.upi_id} onChange={(e) => setBankForm((prev) => ({ ...prev, upi_id: e.target.value }))} />
            </Grid>
            <Grid item xs={12}>
              <FormSwitch
                label="Primary account"
                checked={bankForm.is_primary}
                onChange={(checked) => setBankForm((prev) => ({ ...prev, is_primary: checked }))}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setBankOpen(false)} disabled={savingBank} color="inherit">
            Cancel
          </Button>
          <Button variant="contained" onClick={saveBank} disabled={savingBank}>
            {savingBank ? 'Saving…' : bankEditId ? 'Save changes' : 'Add account'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
