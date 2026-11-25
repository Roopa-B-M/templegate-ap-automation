import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import InboxIcon from '@mui/icons-material/Inbox';

export default function EmptyState({ icon, title = 'Nothing here yet', subtitle, action }) {
  return (
    <Box sx={{ py: 6, px: 2, textAlign: 'center' }}>
      <Box sx={{ mb: 1, color: 'text.disabled' }}>{icon || <InboxIcon sx={{ fontSize: 46 }} />}</Box>
      <Typography variant="subtitle1" fontWeight={600}>
        {title}
      </Typography>
      {subtitle && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 440, mx: 'auto' }}>
          {subtitle}
        </Typography>
      )}
      {action && <Box sx={{ mt: 2 }}>{action}</Box>}
    </Box>
  );
}
