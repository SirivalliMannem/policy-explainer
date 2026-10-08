import React from 'react';
import { Menu, ShieldCheck } from 'lucide-react';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

export interface HeaderProps {
  onOpenMobileMenu: () => void;
  title?: string;
  isBackendHealthy?: boolean;
}

export function Header({
  onOpenMobileMenu,
  title = 'Policy Explainer',
  isBackendHealthy = true,
}: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-border bg-card/80 px-4 sm:px-6 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenMobileMenu}
          className="lg:hidden text-muted-foreground"
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-base font-semibold text-navy leading-none sm:text-lg">{title}</h1>
          <p className="hidden text-xs text-muted-foreground sm:block mt-0.5">
            Grounded Policy Intelligence
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {isBackendHealthy ? (
          <Badge variant="success" className="gap-1.5 py-1">
            <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
            <span className="text-[11px] font-medium hidden sm:inline">Engine Online</span>
          </Badge>
        ) : (
          <Badge variant="destructive" className="gap-1.5 py-1">
            <span className="h-1.5 w-1.5 rounded-full bg-destructive" />
            <span className="text-[11px] font-medium hidden sm:inline">Offline</span>
          </Badge>
        )}

        <div className="flex items-center gap-2 border-l border-border pl-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-subtle border border-primary/20 text-primary">
            <ShieldCheck className="h-4 w-4" />
          </div>
        </div>
      </div>
    </header>
  );
}
