import { Navigate, Route, Routes } from 'react-router-dom';
import DashboardLayout from './components/DashboardLayout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import InvoiceListPage from './pages/InvoiceListPage';
import InvoiceUploadPage from './pages/InvoiceUploadPage';
import InvoiceDetailPage from './pages/InvoiceDetailPage';
import PurchaseOrderListPage from './pages/PurchaseOrderListPage';
import PurchaseOrderDetailPage from './pages/PurchaseOrderDetailPage';
import GrnListPage from './pages/GrnListPage';
import VendorListPage from './pages/VendorListPage';
import VendorDetailPage from './pages/VendorDetailPage';
import ApprovalsPage from './pages/ApprovalsPage';
import PaymentsPage from './pages/PaymentsPage';
import AccountingPage from './pages/AccountingPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import UsersPage from './pages/UsersPage';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/invoices" element={<InvoiceListPage />} />
        <Route
          path="/invoices/upload"
          element={
            <ProtectedRoute roles={['ADMIN', 'AP_CLERK']}>
              <InvoiceUploadPage />
            </ProtectedRoute>
          }
        />
        <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="/purchase-orders" element={<PurchaseOrderListPage />} />
        <Route path="/purchase-orders/:id" element={<PurchaseOrderDetailPage />} />
        <Route path="/grns" element={<GrnListPage />} />
        <Route path="/vendors" element={<VendorListPage />} />
        <Route path="/vendors/:id" element={<VendorDetailPage />} />
        <Route
          path="/approvals"
          element={
            <ProtectedRoute roles={['APPROVER', 'ADMIN', 'FINANCE']}>
              <ApprovalsPage />
            </ProtectedRoute>
          }
        />
        <Route path="/payments" element={<PaymentsPage />} />
        <Route
          path="/accounting"
          element={
            <ProtectedRoute roles={['FINANCE', 'ADMIN']}>
              <AccountingPage />
            </ProtectedRoute>
          }
        />
        <Route path="/reports" element={<ReportsPage />} />
        <Route
          path="/settings"
          element={
            <ProtectedRoute roles={['ADMIN']}>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/users"
          element={
            <ProtectedRoute roles={['ADMIN']}>
              <UsersPage />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
