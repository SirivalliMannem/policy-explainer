import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ExplainerPage } from './pages/ExplainerPage';
import { SettingsPage } from './pages/SettingsPage';
import { HelpPage } from './pages/HelpPage';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Temporary minimal landing root */}
        <Route path="/" element={<LandingPage />} />

        {/* Auth Route */}
        <Route path="/login" element={<LoginPage />} />

        {/* Application Workspace Routes wrapped in AppLayout */}
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Navigate to="/app/explainer" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="explainer" element={<ExplainerPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="help" element={<HelpPage />} />
        </Route>

        {/* Catch-all redirect to root */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
