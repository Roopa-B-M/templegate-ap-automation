import { useCallback, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditIcon from '@mui/icons-material/Edit';
import api from '../api/client';
import ConfirmDialog from '../components/ConfirmDialog';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormSwitch, FormTextField } from '../components/FormControls';
import { useSnackbar } from '../context/SnackbarContext';
import usePagedList from '../hooks/usePagedList';
import { ROLE_OPTIONS } from '../utils/constants';
import { formatCurrency, formatDateTime, getApiErrorMessage, toNumber } from '../utils/format';

const EMPTY_MATRIX_FORM = {
  name: '',
  level: 1,
  min_amount: '',
  max_amount: '',
  approver_role: 'APPROVER',
  is_parallel: false,
  escalation_hours: 24,
  active: true,
};

function MatrixDialog({ open, initial, onClose, onSaved }) {
  const snackbar = useSnackbar();
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);
  const editing = Boolean(initial?.id);

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async () => {
    if (!form.name.trim()) {
      snackbar.error('Rule name is required');
      return;
    }
    if (!form.approver_role) {
      snackbar.error('Select the approver role');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        level: Math.max(1, Math.round(toNumber(form.level) || 1)),
        min_amount: form.min_amount === '' || form.min_amount === null ? null : String(toNumber(form.min_amount)),
        max_amount: form.max_amount === '' || form.max_amount === null ? null : String(toNumber(form.max_amount)),
        approver_role: form.approver_role,
        is_parallel: Boolean(form.is_parallel),
        escalation_hours: Math.max(1, Math.round(toNumber(form.escalation_hours) || 24)),
        active: Boolean(form.active),
      };
      if (editing) {
        await api.patch(`/workflow/matrix/${form.id}`, payload);
        snackbar.success('Approval rule updated');
      } else {
        await api.post('/workflow/matrix', payload);
        snackbar.success('Approval rule created');
      }
      onSaved();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{editing ? 'Edit approval rule' : 'Create approval rule'}</DialogTitle>
      <DialogContent>
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12} sm={6}>
            <FormTextField label="Rule name *" value={form.name} onChange={(e) => setField('name', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormTextField label="Level *" type="number" value={form.level} onChange={(e) => setField('level', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormTextField
              label="Min amount (blank = none)"
              type="number"
              value={form.min_amount}
              onChange={(e) => setField('min_amount', e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormTextField
              label="Max amount (blank = none)"
              type="number"
              value={form.max_amount}
              onChange={(e) => setField('max_amount', e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormSelect
              label="Approver role *"
              value={form.approver_role}
              onChange={(e) => setField('approver_role', e.target.value)}
              options={ROLE_OPTIONS}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormTextField
              label="Escalation hours *"
              type="number"
              value={form.escalation_hours}
              onChange={(e) => setField('escalation_hours', e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormSwitch
              label="Parallel — all must approve"
              checked={form.is_parallel}
              onChange={(checked) => setField('is_parallel', checked)}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormSwitch label="Active" checked={form.active} onChange={(checked) => setField('active', checked)} />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={saving} color="inherit">
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={saving}>
          {saving ? 'Saving…' : editing ? 'Save changes' : 'Create rule'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function SettingsPage() {
  const snackbar = useSnackbar();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogInitial, setDialogInitial] = useState(EMPTY_MATRIX_FORM);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [runLoading, setRunLoading] = useState(false);
  const [lastRun, setLastRun] = useState(null);
  const [confirmState, setConfirmState] = useState(null);

  const fetchFn = useCallback(
    (page, pageSize) =>
      api.get('/workflow/matrix', { params: { page: page + 1, pageSize } }).then((res) => res.data),
    []
  );

  const list = usePagedList(fetchFn, []);

  const openCreate = () => {
    setDialogInitial(EMPTY_MATRIX_FORM);
    setDialogOpen(true);
  };

  const openEdit = (row) => {
    setDialogInitial({
      id: row.id,
      name: row.name || '',
      level: row.level ?? 1,
      min_amount: row.min_amount ?? '',
      max_amount: row.max_amount ?? '',
      approver_role: row.approver_role || 'APPROVER',
      is_parallel: Boolean(row.is_parallel),
      escalation_hours: row.escalation_hours ?? 24,
      active: Boolean(row.active),
    });
    setDialogOpen(true);
  };

  const runAutomation = async () => {
    setRunLoading(true);
    try {
      const { data } = await api.post('/workflow/run-automation');
      setLastRun(data);
      snackbar.success(
        `Automation complete — escalated: ${data.escalated ?? 0}, reminders sent: ${data.reminders ?? 0}`
      );
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setRunLoading(false);
      setConfirmState(null);
    }
  };

  const deleteRule = async () => {
    setActionLoading(true);
    try {
      await api.delete(`/workflow/matrix/${deleteTarget.id}`);
      snackbar.success(`Approval rule “${deleteTarget.name}” deleted`);
      setDeleteTarget(null);
      list.reload();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setActionLoading(false);
      setConfirmState(null);
    }
  };

  const columns = useMemo(
    () => [
      {
        id: 'name',
        label: 'Rule',
        render: (row) => <Typography fontWeight={600}>{row.name}</Typography>,
      },
      { id: 'level', label: 'Level', align: 'center' },
      {
        id: 'min_amount',
        label: 'Min Amount',
        align: 'right',
        render: (row) => (row.min_amount === null || row.min_amount === undefined || row.min_amount === '' ? 'No limit' : formatCurrency(row.min_amount)),
      },
      {
        id: 'max_amount',
        label: 'Max Amount',
        align: 'right',
        render: (row) => (row.max_amount === null || row.max_amount === undefined || row.max_amount === '' ? 'No limit' : formatCurrency(row.max_amount)),
      },
      { id: 'approver_role', label: 'Approver Role', render: (row) => row.approver_role || '—' },
      {
        id: 'is_parallel',
        label: 'Mode',
        render: (row) =>
          row.is_parallel ? (
            <Chip size="small" variant="outlined" color="info" label="Parallel — all" />
          ) : (
            <Chip size="small" variant="outlined" label="Sequential" />
          ),
      },
      { id: 'escalation_hours', label: 'Escalation', align: 'center', render: (row) => `${row.escalation_hours} h` },
      {
        id: 'active',
        label: 'Active',
        render: (row) => <StatusChip status={row.active ? 'ACTIVE' : 'INACTIVE'} />,
      },
      { id: 'created_at', label: 'Created', render: (row) => formatDateTime(row.created_at) },
      {
        id: 'actions',
        label: '',
        align: 'right',
        render: (row) => (
          <Stack direction="row" spacing={0.5} justifyContent="flex-end">
            <Tooltip title="Edit rule">
              <IconButton size="small" onClick={() => openEdit(row)} aria-label={`Edit ${row.name}`}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete rule">
              <IconButton
                size="small"
                color="error"
                onClick={() => setDeleteTarget(row)}
                aria-label={`Delete ${row.name}`}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
        ),
      },
    ],
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  return (
    <Box>
      <PageHeader
        title="Settings"
        subtitle="Approval matrix and workflow automation controls."
        actions={
          <>
            <Button
              variant="outlined"
              startIcon={runLoading ? undefined : <AutoFixHighIcon />}
              disabled={runLoading}
              onClick={() =>
                setConfirmState({
                  title: 'Run escalation & reminder automation',
                  message:
                    'Scan overdue approval tasks and escalate them per the matrix, and send reminders to approvers. Run now?',
                  confirmText: 'Run automation',
                  action: runAutomation,
                })
              }
            >
              {runLoading ? 'Running…' : 'Run escalation & reminders'}
            </Button>
            <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
              Create rule
            </Button>
          </>
        }
      />

      {lastRun && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setLastRun(null)}>
          Last automation run: {lastRun.escalated ?? 0} task(s) escalated, {lastRun.reminders ?? 0} reminder(s) sent.
        </Alert>
      )}

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
        emptyTitle="No approval rules defined"
        emptySubtitle="Create the first rule to define who approves invoices at each level."
        minWidth={980}
      />

      {dialogOpen && (
        <MatrixDialog
          open={dialogOpen}
          initial={dialogInitial}
          onClose={() => setDialogOpen(false)}
          onSaved={() => {
            setDialogOpen(false);
            list.reload();
          }}
        />
      )}

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete approval rule"
        message={`Delete the rule “${deleteTarget?.name}”? Invoices already in the workflow are not affected.`}
        confirmText="Delete"
        confirmColor="error"
        loading={actionLoading}
        onClose={() => {
          if (!actionLoading) setDeleteTarget(null);
        }}
        onConfirm={deleteRule}
      />

      <ConfirmDialog
        open={Boolean(confirmState)}
        title={confirmState?.title || 'Confirm'}
        message={confirmState?.message}
        confirmText={confirmState?.confirmText || 'Confirm'}
        loading={runLoading}
        onClose={() => {
          if (!runLoading) setConfirmState(null);
        }}
        onConfirm={() => {
          if (confirmState?.action) confirmState.action();
        }}
      />
    </Box>
  );
}
