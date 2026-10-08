import React, { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { checkHealth } from '../../services/api';

export function AppLayout() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isBackendHealthy, setIsBackendHealthy] = useState(true);
  const location = useLocation();

  useEffect(() => {
    let isMounted = true;
    checkHealth()
      .then((res) => {
        if (isMounted) setIsBackendHealthy(res.status === 'ok');
      })
      .catch(() => {
        if (isMounted) setIsBackendHealthy(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const getPageTitle = (path: string): string => {
    if (path.includes('/dashboard')) return 'Enterprise Dashboard';
    if (path.includes('/explainer')) return 'Policy Explainer';
    if (path.includes('/settings')) return 'Settings';
    if (path.includes('/help')) return 'Help & Documentation';
    return 'Policy Explainer';
  };

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        isCollapsed={isCollapsed}
        onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
        isMobileOpen={isMobileOpen}
        onCloseMobile={() => setIsMobileOpen(false)}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        <Header
          onOpenMobileMenu={() => setIsMobileOpen(true)}
          title={getPageTitle(location.pathname)}
          isBackendHealthy={isBackendHealthy}
        />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
