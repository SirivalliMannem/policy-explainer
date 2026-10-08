import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Shield, ChevronLeft, ChevronRight, LogOut } from 'lucide-react';
import { PRIMARY_NAV_ITEMS, SECONDARY_NAV_ITEMS } from '../../config';
import { cn } from '../../lib/utils';
import { Tooltip } from '../ui/Tooltip';
import { Separator } from '../ui/Separator';
import { clearSession, getSession } from '../../services/auth';

export interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export function Sidebar({
  isCollapsed,
  onToggleCollapse,
  isMobileOpen = false,
  onCloseMobile,
}: SidebarProps) {
  const navigate = useNavigate();
  const session = getSession();
  const email = session?.user.email || 'Signed in';
  const displayName = session?.user.name || 'Insurance Specialist';
  const initials =
    displayName
      .split(/\s+/)
      .map((w) => w[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || 'PE';

  const handleLogout = () => {
    clearSession();
    onCloseMobile?.();
    navigate('/login', { replace: true });
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-navy/40 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar container */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex h-screen shrink-0 flex-col border-r border-border bg-card transition-all duration-300 lg:sticky lg:top-0',
          isCollapsed ? 'w-16' : 'w-64',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Brand identity header */}
        <div className={cn('flex h-16 items-center px-4', isCollapsed ? 'justify-center px-2' : 'justify-between')}>
          {/* The collapsed rail is too narrow for the logo and the toggle; keep only the toggle there. */}
          <div className={cn('flex items-center gap-3 overflow-hidden', isCollapsed && 'lg:hidden')}>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-subtle text-primary border border-primary/20">
              <Shield className="h-5 w-5" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col overflow-hidden">
                <span className="truncate text-sm font-bold text-navy leading-tight">
                  Policy Explainer
                </span>
                <span className="truncate text-[11px] text-muted-foreground font-normal">
                  Insurance Intelligence
                </span>
              </div>
            )}
          </div>

          {/* Desktop collapse toggle */}
          <button
            onClick={onToggleCollapse}
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="hidden lg:flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        <Separator />

        {/* Primary Navigation */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          <nav className="space-y-1">
            {!isCollapsed && (
              <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Workspace
              </div>
            )}
            {PRIMARY_NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const linkContent = (
                <NavLink
                  key={item.href}
                  to={item.href}
                  onClick={onCloseMobile}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-surface-subtle text-primary'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      isCollapsed && 'justify-center px-2'
                    )
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {!isCollapsed && <span className="truncate">{item.title}</span>}
                </NavLink>
              );

              return isCollapsed ? (
                <Tooltip key={item.href} content={item.title} position="right" className="w-full">
                  {linkContent}
                </Tooltip>
              ) : (
                linkContent
              );
            })}
          </nav>

          <Separator />

          {/* Secondary Navigation */}
          <nav className="space-y-1">
            {!isCollapsed && (
              <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Support
              </div>
            )}
            {SECONDARY_NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const linkContent = (
                <NavLink
                  key={item.href}
                  to={item.href}
                  onClick={onCloseMobile}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-surface-subtle text-primary'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      isCollapsed && 'justify-center px-2'
                    )
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {!isCollapsed && <span className="truncate">{item.title}</span>}
                </NavLink>
              );

              return isCollapsed ? (
                <Tooltip key={item.href} content={item.title} position="right" className="w-full">
                  {linkContent}
                </Tooltip>
              ) : (
                linkContent
              );
            })}
          </nav>
        </div>

        {/* Footer: signed-in employee and logout */}
        <Separator />
        <div className="space-y-1 p-3">
          <div
            className={cn('flex items-center gap-3 rounded-lg p-2 select-none', isCollapsed && 'justify-center p-1')}
            title={isCollapsed ? `${displayName} · ${email}` : undefined}
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-subtle border border-primary/20 text-xs font-semibold text-primary">
              {initials}
            </div>
            {!isCollapsed && (
              <div className="flex flex-col overflow-hidden">
                <span className="truncate text-xs font-semibold text-navy">{displayName}</span>
                <span className="truncate text-[11px] text-muted-foreground">{email}</span>
              </div>
            )}
          </div>

          {isCollapsed ? (
            <Tooltip content="Log out" position="right" className="w-full">
              <button
                type="button"
                onClick={handleLogout}
                aria-label="Log out"
                className="flex w-full items-center justify-center rounded-lg px-2 py-2 text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600 cursor-pointer"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </Tooltip>
          ) : (
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600 cursor-pointer"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              <span>Log out</span>
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
