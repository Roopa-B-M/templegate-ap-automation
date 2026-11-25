import { useMemo, useState } from 'react';
import { Link as RouterLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  AppBar,
  Avatar,
  Badge,
  Box,
  Button,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import DashboardIcon from '@mui/icons-material/Dashboard';
import DescriptionIcon from '@mui/icons-material/Description';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import GroupIcon from '@mui/icons-material/Group';
import LocalShippingIcon from '@mui/icons-material/LocalShipping';
import LogoutIcon from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import NotificationsIcon from '@mui/icons-material/Notifications';
import PaymentsIcon from '@mui/icons-material/Payments';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import SettingsIcon from '@mui/icons-material/Settings';
import StorefrontIcon from '@mui/icons-material/Storefront';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../context/NotificationContext';
import { formatDateTime, humanize } from '../utils/format';

const DRAWER_WIDTH = 250;
const ALL_ROLES = ['ADMIN', 'AP_CLERK', 'APPROVER', 'FINANCE'];

const NAV_ITEMS = [
  { label: 'Dashboard', icon: <DashboardIcon />, path: '/', roles: ALL_ROLES },
  { label: 'Invoices', icon: <ReceiptLongIcon />, path: '/invoices', roles: ALL_ROLES },
  { label: 'Purchase Orders', icon: <DescriptionIcon />, path: '/purchase-orders', roles: ['ADMIN', 'AP_CLERK'] },
  { label: 'Goods Receipts', icon: <LocalShippingIcon />, path: '/grns', roles: ['ADMIN', 'AP_CLERK'] },
  { label: 'Vendors', icon: <StorefrontIcon />, path: '/vendors', roles: ['ADMIN', 'AP_CLERK', 'FINANCE'] },
  { label: 'Approvals', icon: <FactCheckIcon />, path: '/approvals', roles: ['APPROVER', 'ADMIN', 'FINANCE'] },
  { label: 'Payments', icon: <PaymentsIcon />, path: '/payments', roles: ['ADMIN', 'AP_CLERK', 'FINANCE'] },
  { label: 'Accounting / ERP', icon: <AccountBalanceIcon />, path: '/accounting', roles: ['ADMIN', 'FINANCE'] },
  { label: 'Reports', icon: <AssessmentIcon />, path: '/reports', roles: ALL_ROLES },
  { label: 'Settings', icon: <SettingsIcon />, path: '/settings', roles: ['ADMIN'] },
  { label: 'Users', icon: <GroupIcon />, path: '/users', roles: ['ADMIN'] },
];

const PAGE_TITLES = [
  [/^\/invoices\/upload\/?$/, 'Upload Invoices'],
  [/^\/invoices\/[^/]+\/?$/, 'Invoice Detail'],
  [/^\/invoices\/?$/, 'Invoices'],
  [/^\/purchase-orders\/[^/]+\/?$/, 'Purchase Order Detail'],
  [/^\/purchase-orders\/?$/, 'Purchase Orders'],
  [/^\/grns\/?$/, 'Goods Receipt Notes'],
  [/^\/vendors\/[^/]+\/?$/, 'Vendor Detail'],
  [/^\/vendors\/?$/, 'Vendors'],
  [/^\/approvals\/?$/, 'Approvals'],
  [/^\/payments\/?$/, 'Payments'],
  [/^\/accounting\/?$/, 'Accounting / ERP'],
  [/^\/reports\/?$/, 'Reports'],
  [/^\/settings\/?$/, 'Settings'],
  [/^\/users\/?$/, 'User Management'],
  [/^\/$/, 'Dashboard'],
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const { unreadCount, items, fetchList, markRead, markAllRead } = useNotifications();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifAnchor, setNotifAnchor] = useState(null);
  const [userAnchor, setUserAnchor] = useState(null);

  const title = useMemo(() => {
    const found = PAGE_TITLES.find(([regex]) => regex.test(location.pathname));
    return found ? found[1] : 'TempleGate';
  }, [location.pathname]);

  const navItems = NAV_ITEMS.filter((item) => item.roles.includes(user?.role));

  const fullName = `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username || '';
  const initials = (user?.first_name?.[0] || user?.username?.[0] || 'U').toUpperCase();

  const handleLogout = () => {
    setUserAnchor(null);
    logout();
    navigate('/login', { replace: true });
  };

  const openNotifications = (event) => {
    setNotifAnchor(event.currentTarget);
    fetchList();
  };

  const drawerContent = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Toolbar sx={{ px: 2 }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Avatar
            variant="rounded"
            sx={{ fontWeight: 700, background: 'linear-gradient(135deg, #14365D 0%, #0E8388 100%)' }}
          >
            TG
          </Avatar>
          <Box>
            <Typography variant="subtitle1" fontWeight={700} lineHeight={1.2}>
              TempleGate
            </Typography>
            <Typography variant="caption" color="text.secondary">
              AP Automation
            </Typography>
          </Box>
        </Stack>
      </Toolbar>
      <Divider />
      <List sx={{ px: 1, pt: 1, flexGrow: 1 }}>
        {navItems.map((item) => {
          const active =
            item.path === '/'
              ? location.pathname === '/'
              : location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
          return (
            <ListItemButton
              key={item.path}
              component={RouterLink}
              to={item.path}
              selected={active}
              onClick={() => setMobileOpen(false)}
              sx={{
                borderRadius: 1.5,
                mb: 0.5,
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  '&:hover': { bgcolor: 'primary.main' },
                  '& .MuiListItemIcon-root': { color: 'inherit' },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 38 }}>{item.icon}</ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{ fontSize: 14, fontWeight: active ? 700 : 500 }}
              />
            </ListItemButton>
          );
        })}
      </List>
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" color="text.secondary">
          TempleGate AP Automation v1.1
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar position="fixed" elevation={0} sx={{ zIndex: (t) => t.zIndex.drawer + 1, bgcolor: 'primary.main' }}>
        <Toolbar sx={{ gap: 1 }}>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => setMobileOpen(true)}
            sx={{ display: { md: 'none' } }}
            aria-label="Open navigation"
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap sx={{ flexGrow: 1 }}>
            {title}
          </Typography>

          <Tooltip title="Notifications">
            <IconButton color="inherit" onClick={openNotifications} aria-label="Notifications">
              <Badge badgeContent={unreadCount} color="error" max={99}>
                <NotificationsIcon />
              </Badge>
            </IconButton>
          </Tooltip>

          <Tooltip title={fullName}>
            <IconButton color="inherit" onClick={(e) => setUserAnchor(e.currentTarget)} aria-label="Account menu">
              <Avatar sx={{ width: 32, height: 32, bgcolor: 'secondary.main', fontSize: 14 }}>{initials}</Avatar>
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      {/* Mobile: temporary swipeable drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { boxSizing: 'border-box', width: DRAWER_WIDTH },
        }}
      >
        {drawerContent}
      </Drawer>

      {/* Desktop: permanent drawer */}
      <Drawer
        variant="permanent"
        open
        sx={{
          display: { xs: 'none', md: 'block' },
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            width: DRAWER_WIDTH,
            borderRight: '1px solid #E3E9F0',
          },
        }}
      >
        {drawerContent}
      </Drawer>

      <Box
        component="main"
        sx={{ flexGrow: 1, p: { xs: 2, md: 3 }, width: { md: `calc(100% - ${DRAWER_WIDTH}px)` }, minWidth: 0 }}
      >
        <Toolbar />
        <Outlet />
      </Box>

      {/* Notification bell dropdown */}
      <Menu
        anchorEl={notifAnchor}
        open={Boolean(notifAnchor)}
        onClose={() => setNotifAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        PaperProps={{ sx: { width: { xs: 'calc(100vw - 24px)', sm: 360 }, maxHeight: 480, maxWidth: 360 } }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, py: 1 }}>
          <Typography variant="subtitle2">Notifications</Typography>
          <Button size="small" onClick={markAllRead} disabled={unreadCount === 0}>
            Mark all read
          </Button>
        </Stack>
        <Divider />
        <Box sx={{ overflowY: 'auto' }}>
          {items.length === 0 ? (
            <Box sx={{ px: 2, py: 4, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                No unread notifications
              </Typography>
            </Box>
          ) : (
            items.map((item) => (
              <MenuItem
                key={item.id}
                onClick={() => {
                  markRead(item.id);
                  setNotifAnchor(null);
                  if (item.link && String(item.link).startsWith('/')) navigate(item.link);
                }}
                sx={{ display: 'block', py: 1, whiteSpace: 'normal' }}
              >
                <Typography variant="body2" fontWeight={600}>
                  {item.title}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {item.message}
                </Typography>
                <Typography variant="caption" color="text.disabled">
                  {formatDateTime(item.created_at)}
                </Typography>
              </MenuItem>
            ))
          )}
        </Box>
      </Menu>

      {/* User avatar menu */}
      <Menu
        anchorEl={userAnchor}
        open={Boolean(userAnchor)}
        onClose={() => setUserAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Box sx={{ px: 2, py: 1.5, minWidth: 200 }}>
          <Typography variant="subtitle2">{fullName}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {user?.email}
          </Typography>
          <Chip
            size="small"
            color="secondary"
            label={user?.role_display || humanize(user?.role)}
            sx={{ mt: 1 }}
          />
        </Box>
        <Divider />
        <MenuItem onClick={handleLogout}>
          <ListItemIcon>
            <LogoutIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Logout" />
        </MenuItem>
      </Menu>
    </Box>
  );
}
