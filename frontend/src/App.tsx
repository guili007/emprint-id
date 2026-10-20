import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import VerifyPage from './pages/VerifyPage';
import IntelAlertsPage from './pages/IntelAlertsPage';
import ThreatZonesPage from './pages/ThreatZonesPage';
import NetworkGraphPage from './pages/NetworkGraphPage';
import CitizenProfilePage from './pages/CitizenProfilePage';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              <PublicRoute>
                <Login />
              </PublicRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            }
          />
          <Route
            path="/verify"
            element={
              <PrivateRoute>
                <VerifyPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/intel/alerts"
            element={
              <PrivateRoute>
                <IntelAlertsPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/intel/threats"
            element={
              <PrivateRoute>
                <ThreatZonesPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/intel/network"
            element={
              <PrivateRoute>
                <NetworkGraphPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/citizen/profile"
            element={
              <PrivateRoute>
                <CitizenProfilePage />
              </PrivateRoute>
            }
          />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
