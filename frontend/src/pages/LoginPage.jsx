import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import LoginIcon from '@mui/icons-material/Login';
import { useAuth } from '../context/AuthContext';
import { useSnackbar } from '../context/SnackbarContext';
import { getApiErrorMessage } from '../utils/format';

export default function LoginPage() {
  const { user, login } = useAuth();
  const snackbar = useSnackbar();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (user) return <Navigate to="/" replace />;

  const redirectTo = location.state?.from || '/';

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError('Please enter both username and password.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
      snackbar.success('Signed in successfully');
      navigate(redirectTo, { replace: true });
    } catch (err) {
      const message = getApiErrorMessage(err);
      setError(message);
      snackbar.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        p: 2,
        background: 'linear-gradient(135deg, #14365D 0%, #0E8388 100%)',
      }}
    >
      <Card sx={{ width: '100%', maxWidth: 430, py: 2 }}>
        <CardContent>
          <Stack alignItems="center" sx={{ mb: 3 }}>
            <Avatar
              variant="rounded"
              sx={{
                width: 56,
                height: 56,
                fontWeight: 700,
                fontSize: 20,
                background: 'linear-gradient(135deg, #14365D 0%, #0E8388 100%)',
                mb: 1.5,
              }}
            >
              TG
            </Avatar>
            <Typography variant="h5" fontWeight={700}>
              TempleGate
            </Typography>
            <Typography variant="body2" color="secondary" fontWeight={600}>
              AP Automation
            </Typography>
          </Stack>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <Stack spacing={2}>
              <TextField
                fullWidth
                label="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
                disabled={submitting}
              />
              <TextField
                fullWidth
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                disabled={submitting}
              />
              <Button type="submit" variant="contained" size="large" disabled={submitting}>
                {submitting ? 'Signing in…' : 'Sign in'}
              </Button>
            </Stack>
          </form>

          <Divider sx={{ my: 2.5 }} />
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center' }}>
            This demo environment is seeded with one account per role (admin, ap_clerk, approver, finance).
            Sign in with your assigned credentials.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
