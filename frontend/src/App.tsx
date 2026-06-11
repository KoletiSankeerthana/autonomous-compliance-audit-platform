import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './store/authStore'
import { AppLayout } from './components/layout/AppLayout'
import { ProtectedRoute } from './components/common/ProtectedRoute'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import LoginPage from './pages/Login'
import RegisterPage from './pages/Register'
import DashboardPage from './pages/Dashboard'
import UploadPage from './pages/Upload'
import AskQuestionPage from './pages/AskQuestion'
import ComplianceReportsPage from './pages/ComplianceReports'
import AuditHistoryPage from './pages/AuditHistory'
import RiskAnalyticsPage from './pages/RiskAnalytics'
import UserManagementPage from './pages/UserManagement'
import SettingsPage from './pages/Settings'
import TrendDashboardPage from './pages/TrendDashboard'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

function ThemeInit() {
  useEffect(() => {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark')
    }
  }, [])
  return null
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeInit />
        <BrowserRouter>
          <ErrorBoundary>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<DashboardPage />} />
                <Route path="trends" element={<TrendDashboardPage />} />
                <Route
                  path="documents/upload"
                  element={
                    <ProtectedRoute allowedRoles={['admin', 'auditor']}>
                      <UploadPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="qa" element={<AskQuestionPage />} />
                <Route path="compliance" element={<ComplianceReportsPage />} />
                <Route path="audit" element={<AuditHistoryPage />} />
                <Route path="risk" element={<RiskAnalyticsPage />} />
                <Route
                  path="admin/users"
                  element={
                    <ProtectedRoute allowedRoles={['admin']}>
                      <UserManagementPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="settings" element={<SettingsPage />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ErrorBoundary>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
