import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';

export default function KpiCard({ title, value, sub, icon, color = 'primary', loading = false }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
        <Avatar
          variant="rounded"
          sx={{ bgcolor: `${color}.main`, color: '#fff', width: 46, height: 46, flexShrink: 0 }}
        >
          {icon}
        </Avatar>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" color="text.secondary" noWrap>
            {title}
          </Typography>
          {loading ? (
            <Skeleton width={92} height={30} />
          ) : (
            <Typography variant="h6" fontWeight={700} sx={{ wordBreak: 'break-word' }}>
              {value}
            </Typography>
          )}
          {sub && !loading && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              {sub}
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
