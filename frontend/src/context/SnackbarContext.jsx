import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { Alert, Snackbar } from '@mui/material';

const SnackbarContext = createContext(null);

/** Global toast notifications: snackbar.success('Saved'), snackbar.error(msg), etc. */
export function SnackbarProvider({ children }) {
  const [snack, setSnack] = useState(null);

  const showSnackbar = useCallback((message, severity = 'info') => {
    setSnack({ message, severity, key: Date.now() });
  }, []);

  const value = useMemo(
    () => ({
      showSnackbar,
      success: (m) => showSnackbar(m, 'success'),
      error: (m) => showSnackbar(m, 'error'),
      warning: (m) => showSnackbar(m, 'warning'),
      info: (m) => showSnackbar(m, 'info'),
    }),
    [showSnackbar]
  );

  const handleClose = (_event, reason) => {
    if (reason === 'clickaway') return;
    setSnack(null);
  };

  return (
    <SnackbarContext.Provider value={value}>
      {children}
      <Snackbar
        key={snack?.key}
        open={Boolean(snack)}
        autoHideDuration={5000}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleClose}
          severity={snack?.severity || 'info'}
          variant="filled"
          sx={{ width: '100%', borderRadius: 2 }}
        >
          {snack?.message}
        </Alert>
      </Snackbar>
    </SnackbarContext.Provider>
  );
}

export function useSnackbar() {
  const ctx = useContext(SnackbarContext);
  if (!ctx) throw new Error('useSnackbar must be used within a SnackbarProvider');
  return ctx;
}
