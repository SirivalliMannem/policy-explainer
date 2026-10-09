import { ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ExplainerPage } from './pages/ExplainerPage';
import { SettingsPage } from './pages/SettingsPage';
import { HelpPage } from './pages/HelpPage';
import { getSession } from './services/auth';

/** Workspace pages need a signed-in session; without one, go to the login page. */
function RequireSession({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!getSession()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* The app opens on the login page */}
        <Route path="/" element={<Navigate to="/login" replace />} />

        {/* Auth Route */}
        <Route path="/login" element={<LoginPage />} />

        {/* Application Workspace Routes wrapped in AppLayout */}
        <Route
          path="/app"
          element={
            <RequireSession>
              <AppLayout />
            </RequireSession>
          }
        >
          <Route index element={<Navigate to="/app/explainer" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="explainer" element={<ExplainerPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="help" element={<HelpPage />} />
        </Route>

        {/* Catch-all redirect to the login page */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
