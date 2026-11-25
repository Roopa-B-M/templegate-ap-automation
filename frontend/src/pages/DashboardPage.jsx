import dayjs from 'dayjs';
import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import DocumentScannerIcon from '@mui/icons-material/DocumentScanner';
import PaidIcon from '@mui/icons-material/Paid';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import RefreshIcon from '@mui/icons-material/Refresh';
import api from '../api/client';
import KpiCard from '../components/KpiCard';
import PageHeader from '../components/PageHeader';
import StatusChip from '../components/StatusChip';
import EmptyState from '../components/EmptyState';
import { useAuth } from '../context/AuthContext';
import {
  formatCompactCurrency,
  formatConfidence,
  formatCurrency,
  formatDate,
  getApiErrorMessage,
} from '../utils/format';

const CHART_COLORS = [
  '#14365D', '#0E8388', '#3B82F6', '#F59E0B', '#EF4444',
  '#10B981', '#8B5CF6', '#EC4899', '#14B8A6', '#64748B',
  '#A855F7', '#84CC16',
];

function monthLabel(month) {
  const d = dayjs(`${month}-01`);
  return d.isValid() ? d.format('MMM YY') : month;
}

function ChartCard({ title, children }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="subtitle1" fontWeight={600} gutterBottom>
          {title}
        </Typography>
        {children}
      </CardContent>
    </Card>
  );
}

function ChartEmpty({ label = 'No data available yet' }) {
  return (
    <Box sx={{ height: 280, display: 'grid', placeItems: 'center' }}>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/analytics/dashboard');
      setData(res.data);
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !data) {
    return (
      <Box>
        <Skeleton variant="rectangular" width={280} height={36} sx={{ mb: 3 }} />
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(5, 1fr)' }, mb: 3 }}>
          {Array.from({ length: 5 }).map((_x, i) => (
            <Skeleton key={i} variant="rounded" height={92} />
          ))}
        </Box>
        <Grid container spacing={3}>
          <Grid item xs={12} lg={5}>
            <Skeleton variant="rounded" height={340} />
          </Grid>
          <Grid item xs={12} lg={7}>
            <Skeleton variant="rounded" height={340} />
          </Grid>
        </Grid>
      </Box>
    );
  }

  if (error && !data) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" startIcon={<RefreshIcon />} onClick={load}>
            Retry
          </Button>
        }
      >
        Failed to load the dashboard: {getApiErrorMessage(error)}
      </Alert>
    );
  }

  const statusCounts = data?.status_counts || [];
  const monthlySpend = data?.monthly_spend || [];
  const aging = data?.aging || [];
  const vendorSpend = (data?.vendor_spend || []).slice(0, 8);
  const recentInvoices = data?.recent_invoices || [];
  const pendingCount = statusCounts.find((s) => s.status === 'PENDING_APPROVAL')?.count ?? 0;

  return (
    <Box>
      <PageHeader
        title="Dashboard"
        subtitle={`Welcome back${user?.first_name ? `, ${user.first_name}` : ''} — here is your AP overview.`}
      />

      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(5, 1fr)' },
          mb: 3,
        }}
      >
        <KpiCard title="Total Invoices" value={data?.totals?.invoices ?? 0} icon={<ReceiptLongIcon />} color="primary" />
        <KpiCard title="Payable Amount" value={formatCurrency(data?.totals?.payable_amount)} icon={<AccountBalanceWalletIcon />} color="secondary" />
        <KpiCard
          title="Pending Approvals"
          value={formatCurrency(data?.totals?.pending_approval_amount)}
          sub={`${pendingCount} invoice(s) awaiting approval`}
          icon={<PendingActionsIcon />}
          color="warning"
        />
        <KpiCard
          title="OCR Avg Confidence"
          value={formatConfidence(data?.ocr?.avg_confidence)}
          sub={`${data?.ocr?.processed ?? 0} processed · ${data?.ocr?.failed ?? 0} failed`}
          icon={<DocumentScannerIcon />}
          color="info"
        />
        <KpiCard title="Paid This Month" value={formatCurrency(data?.totals?.paid_this_month)} icon={<PaidIcon />} color="success" />
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={5}>
          <ChartCard title="Invoice Status Distribution">
            {statusCounts.length === 0 ? (
              <ChartEmpty />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={statusCounts}
                    dataKey="count"
                    nameKey="status_display"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={2}
                  >
                    {statusCounts.map((entry, index) => (
                      <Cell key={entry.status} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </Grid>

        <Grid item xs={12} lg={7}>
          <ChartCard title="Monthly Spend">
            {monthlySpend.length === 0 ? (
              <ChartEmpty />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={monthlySpend} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="month" tickFormatter={monthLabel} fontSize={11} />
                  <YAxis tickFormatter={(v) => formatCompactCurrency(v)} fontSize={11} width={70} />
                  <Tooltip formatter={(value) => formatCurrency(value)} labelFormatter={monthLabel} />
                  <Bar dataKey="amount" name="Spend" fill="#0E8388" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </Grid>

        <Grid item xs={12} md={6}>
          <ChartCard title="AP Aging by Bucket">
            {aging.length === 0 ? (
              <ChartEmpty />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={aging} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="bucket" fontSize={11} />
                  <YAxis tickFormatter={(v) => formatCompactCurrency(v)} fontSize={11} width={70} />
                  <Tooltip
                    formatter={(value, _name, item) => [
                      formatCurrency(value),
                      `${item?.payload?.bucket} · ${item?.payload?.count ?? 0} invoice(s)`,
                    ]}
                  />
                  <Bar dataKey="amount" name="Amount" fill="#14365D" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </Grid>

        <Grid item xs={12} md={6}>
          <ChartCard title="Vendor Spend (Top 8)">
            {vendorSpend.length === 0 ? (
              <ChartEmpty />
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(240, vendorSpend.length * 44)}>
                <BarChart data={vendorSpend} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => formatCompactCurrency(v)} fontSize={11} />
                  <YAxis type="category" dataKey="vendor" width={150} fontSize={11} />
                  <Tooltip formatter={(value) => formatCurrency(value)} />
                  <Bar dataKey="amount" name="Spend" fill="#3B82F6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Recent Invoices
              </Typography>
              {recentInvoices.length === 0 ? (
                <EmptyState
                  title="No invoices yet"
                  subtitle="Upload your first invoice to see it appear here."
                />
              ) : (
                <TableContainer sx={{ overflowX: 'auto' }}>
                  <Table size="small" sx={{ minWidth: 640 }}>
                    <TableHead>
                      <TableRow>
                        <TableCell>Invoice #</TableCell>
                        <TableCell>Vendor</TableCell>
                        <TableCell>Invoice Date</TableCell>
                        <TableCell align="right">Total</TableCell>
                        <TableCell>Status</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {recentInvoices.map((invoice) => (
                        <TableRow hover key={invoice.id}>
                          <TableCell>
                            <Button
                              size="small"
                              component={RouterLink}
                              to={`/invoices/${invoice.id}`}
                              sx={{ px: 0, minWidth: 0, fontWeight: 600 }}
                            >
                              {invoice.invoice_number}
                            </Button>
                          </TableCell>
                          <TableCell>{invoice.vendor_name || invoice.vendor?.name || '—'}</TableCell>
                          <TableCell>{formatDate(invoice.invoice_date)}</TableCell>
                          <TableCell align="right">{formatCurrency(invoice.total_amount)}</TableCell>
                          <TableCell>
                            <StatusChip status={invoice.status} display={invoice.status_display} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
