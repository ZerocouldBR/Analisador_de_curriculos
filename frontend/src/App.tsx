import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { CssBaseline, CircularProgress, Box } from '@mui/material';
import { ThemeContextProvider } from './contexts/ThemeContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { NotificationProvider } from './contexts/NotificationContext';
import { CompanyProvider } from './contexts/CompanyContext';
import ErrorBoundary from './components/ErrorBoundary';
import AdminGuard from './components/AdminGuard';

// Layout
import Layout from './components/Layout';

// Pages
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import CandidatesPage from './pages/CandidatesPage';
import CandidateDetailPage from './pages/CandidateDetailPage';
import SearchPage from './pages/SearchPage';
import UploadPage from './pages/UploadPage';
import SettingsPage from './pages/SettingsPage';
import RolesPage from './pages/RolesPage';
import ChatPage from './pages/ChatPage';
import ProfilePage from './pages/ProfilePage';
import CompaniesPage from './pages/CompaniesPage';
import LinkedInPage from './pages/LinkedInPage';
import DatabasePage from './pages/DatabasePage';
import SourcingProvidersPage from './pages/SourcingProvidersPage';
import SyncRunsPage from './pages/SyncRunsPage';
import SnapshotTimelinePage from './pages/SnapshotTimelinePage';
import DiagnosticsPage from './pages/DiagnosticsPage';
import BatchImportPage from './pages/BatchImportPage';
import CandidatePortalPage from './pages/CandidatePortalPage';
import JobsPage from './pages/JobsPage';
import JobFormPage from './pages/JobFormPage';
import JobDetailPage from './pages/JobDetailPage';
import PublicCareersPage from './pages/PublicCareersPage';
import PublicJobApplyPage from './pages/PublicJobApplyPage';

interface ProtectedRouteProps {
  children: React.ReactElement;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress size={48} />
      </Box>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" />;
};

const PublicRoute: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress size={48} />
      </Box>
    );
  }

  return isAuthenticated ? <Navigate to="/dashboard" /> : children;
};

function App() {
  return (
    <ThemeContextProvider>
      <CssBaseline />
      <NotificationProvider>
        <ErrorBoundary>
          <AuthProvider>
            <CompanyProvider>
            <Router>
              <Routes>
                {/* Public routes */}
                <Route
                  path="/login"
                  element={
                    <PublicRoute>
                      <LoginPage />
                    </PublicRoute>
                  }
                />
                <Route
                  path="/register"
                  element={
                    <PublicRoute>
                      <RegisterPage />
                    </PublicRoute>
                  }
                />

                {/* Portal publico do candidato (magic link) */}
                <Route path="/me/:token" element={<CandidatePortalPage />} />

                {/* Painel publico de vagas (sem auth) */}
                <Route path="/careers/:companySlug" element={<PublicCareersPage />} />
                <Route
                  path="/careers/:companySlug/:jobSlug"
                  element={<PublicJobApplyPage />}
                />

                {/* Protected routes */}
                <Route
                  path="/"
                  element={
                    <ProtectedRoute>
                      <Layout />
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<Navigate to="/dashboard" />} />
                  <Route path="dashboard" element={<DashboardPage />} />
                  <Route path="candidates" element={<CandidatesPage />} />
                  <Route path="candidates/:id" element={<CandidateDetailPage />} />
                  <Route path="search" element={<SearchPage />} />
                  <Route path="upload" element={<UploadPage />} />
                  <Route path="chat" element={<ChatPage />} />
                  <Route path="settings" element={<AdminGuard><SettingsPage /></AdminGuard>} />
                  <Route path="roles" element={<AdminGuard><RolesPage /></AdminGuard>} />
                  <Route path="profile" element={<ProfilePage />} />
                  <Route path="companies" element={<AdminGuard><CompaniesPage /></AdminGuard>} />
                  <Route path="linkedin" element={<LinkedInPage />} />
                  <Route path="database" element={<AdminGuard><DatabasePage /></AdminGuard>} />
                  <Route path="sourcing" element={<SourcingProvidersPage />} />
                  <Route path="sourcing/runs" element={<SyncRunsPage />} />
                  <Route path="candidates/:id/snapshots" element={<SnapshotTimelinePage />} />
                  <Route path="diagnostics" element={<AdminGuard><DiagnosticsPage /></AdminGuard>} />
                  <Route path="batch-import" element={<BatchImportPage />} />
                  <Route path="jobs" element={<JobsPage />} />
                  <Route path="jobs/new" element={<JobFormPage />} />
                  <Route path="jobs/:id" element={<JobDetailPage />} />
                  <Route path="jobs/:id/edit" element={<JobFormPage />} />
                </Route>

                {/* Catch-all */}
                <Route path="*" element={<Navigate to="/dashboard" />} />
              </Routes>
            </Router>
            </CompanyProvider>
          </AuthProvider>
        </ErrorBoundary>
      </NotificationProvider>
    </ThemeContextProvider>
  );
}

export default App;
