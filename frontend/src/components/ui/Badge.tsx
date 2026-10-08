import React, { HTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

export interface BadgeProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'primary' | 'secondary' | 'success' | 'destructive' | 'outline';
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  const variants = {
    default: 'bg-muted text-muted-foreground',
    primary: 'bg-primary text-primary-foreground',
    secondary: 'bg-surface-subtle text-navy border border-primary/20',
    success: 'bg-success/10 text-success border border-success/20',
    destructive: 'bg-destructive/10 text-destructive border border-destructive/20',
    outline: 'border border-border text-foreground',
  };

  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none select-none',
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
