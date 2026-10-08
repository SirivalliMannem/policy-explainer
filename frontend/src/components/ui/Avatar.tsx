import React, { HTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

export interface AvatarProps extends HTMLAttributes<HTMLDivElement> {
  src?: string;
  alt?: string;
  fallback: string;
  size?: 'sm' | 'md' | 'lg';
}

export function Avatar({ src, alt = '', fallback, size = 'md', className, ...props }: AvatarProps) {
  const sizes = {
    sm: 'h-8 w-8 text-xs',
    md: 'h-9 w-9 text-sm',
    lg: 'h-11 w-11 text-base',
  };

  return (
    <div
      className={cn(
        'relative inline-flex items-center justify-center shrink-0 overflow-hidden rounded-full bg-surface-subtle border border-primary/20 font-medium text-navy select-none',
        sizes[size],
        className
      )}
      {...props}
    >
      {src ? (
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      ) : (
        <span>{fallback.slice(0, 2).toUpperCase()}</span>
      )}
    </div>
  );
}
