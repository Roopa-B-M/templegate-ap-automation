import { useCallback, useMemo, useState } from 'react';
import {
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
  TextField,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import api from '../api/client';
import DataTable from '../components/DataTable';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import { FormSelect, FormSwitch, FormTextField } from '../components/FormControls';
import { useSnackbar } from '../context/SnackbarContext';
import useDebouncedValue from '../hooks/useDebouncedValue';
import usePagedList from '../hooks/usePagedList';
import { ROLE_OPTIONS } from '../utils/constants';
import { formatDate, formatDateTime, getApiErrorMessage, humanize } from '../utils/format';

const EMPTY_CREATE = { username: '', email: '', password: '', first_name: '', last_name: '', role: 'AP_CLERK' };

function CreateUserDialog({ open, onClose, onSaved }) {
  const snackbar = useSnackbar();
  const [form, setForm] = useState(EMPTY_CREATE);
  const [saving, setSaving] = useState(false);

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async () => {
    if (!form.username.trim() || !form.email.trim() || !form.password) {
      snackbar.error('Username, email and password are required');
      return;
    }
    if (!form.role) {
      snackbar.error('Select a role');
      return;
    }
    setSaving(true);
    try {
      await api.post('/users', {
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        role: form.role,
      });
      snackbar.success(`User ${form.username.trim()} created`);
      onSaved();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Create user</DialogTitle>
      <DialogContent>
        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
          <Grid item xs={12} sm={6}>
            <FormTextField label="Username *" value={form.username} onChange={(e) => setField('username', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormTextField label="Email *" type="email" value={form.email} onChange={(e) => setField('email', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormTextField label="Password *" type="password" value={form.password} onChange={(e) => setField('password', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormSelect label="Role *" value={form.role} onChange={(e) => setField('role', e.target.value)} options={ROLE_OPTIONS} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormTextField label="First name" value={form.first_name} onChange={(e) => setField('first_name', e.target.value)} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormTextField label="Last name" value={form.last_name} onChange={(e) => setField('last_name', e.target.value)} />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={saving} color="inherit">
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={saving}>
          {saving ? 'Creating…' : 'Create user'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function EditUserDialog({ user, onClose, onSaved }) {
  const snackbar = useSnackbar();
  const [role, setRole] = useState(user.role || 'AP_CLERK');
  const [isActive, setIsActive] = useState(Boolean(user.is_active));
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    try {
      const payload = { role, is_active: isActive };
      if (password) payload.password = password;
      await api.patch(`/users/${user.id}`, payload);
      snackbar.success(`User ${user.username} updated`);
      onSaved();
    } catch (e) {
      snackbar.error(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onClose={saving ? undefined : onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Edit user — {user.username}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <FormSelect label="Role" value={role} onChange={(e) => setRole(e.target.value)} options={ROLE_OPTIONS} />
          <FormSwitch label="Active" checked={isActive} onChange={setIsActive} />
          <FormTextField
            label="Reset password (leave blank to keep current)"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={saving} color="inherit">
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function UsersPage() {
  const [roleFilter, setRoleFilter] = useState('');
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 400);
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState(null);

  const fetchFn = useCallback(
    (page, pageSize) => {
      const params = { page: page + 1, pageSize };
      if (roleFilter) params.role = roleFilter;
      if (debouncedSearch) params.search = debouncedSearch;
      return api.get('/users', { params }).then((res) => res.data);
    },
    [roleFilter, debouncedSearch]
  );

  const list = usePagedList(fetchFn, [roleFilter, debouncedSearch]);

  const columns = useMemo(
    () => [
      {
        id: 'username',
        label: 'Username',
        render: (row) => <strong>{row.username}</strong>,
      },
      {
        id: 'name',
        label: 'Name',
        render: (row) => `${row.first_name || ''} ${row.last_name || ''}`.trim() || '—',
      },
      { id: 'email', label: 'Email' },
      {
        id: 'role',
        label: 'Role',
        render: (row) => <Chip size="small" color="secondary" label={row.role_display || humanize(row.role)} />,
      },
      {
        id: 'is_active',
        label: 'Active',
        render: (row) => <StatusChip status={row.is_active ? 'ACTIVE' : 'INACTIVE'} />,
      },
      { id: 'date_joined', label: 'Joined', render: (row) => formatDate(row.date_joined) },
      { id: 'last_login', label: 'Last Login', render: (row) => formatDateTime(row.last_login) },
      {
        id: 'actions',
        label: '',
        align: 'right',
        render: (row) => (
          <Tooltip title="Edit user">
            <IconButton size="small" onClick={() => setEditTarget(row)} aria-label={`Edit ${row.username}`}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ),
      },
    ],
    []
  );

  return (
    <Box>
      <PageHeader
        title="User Management"
        subtitle="Create users, manage roles, activation and password resets."
        actions={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
            Create user
          </Button>
        }
      />

      <Grid container spacing={2} sx={{ mb: 2 }} alignItems="center">
        <Grid item xs={12} sm={6} md={3}>
          <FormSelect
            label="Role"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            options={ROLE_OPTIONS}
            emptyOption="All roles"
          />
        </Grid>
        <Grid item xs={12} sm={9} md={4}>
          <TextField fullWidth label="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </Grid>
        <Grid item xs={12} sm={3} md={2}>
          <Button
            color="inherit"
            onClick={() => {
              setRoleFilter('');
              setSearch('');
            }}
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
        emptyTitle="No users found"
        emptySubtitle="Create the first user account to get started."
        minWidth={860}
      />

      {createOpen && (
        <CreateUserDialog
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
            list.reload();
          }}
        />
      )}

      {editTarget && (
        <EditUserDialog
          user={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null);
            list.reload();
          }}
        />
      )}
    </Box>
  );
}
