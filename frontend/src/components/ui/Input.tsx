import { InputHTMLAttributes, forwardRef, ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, leftIcon, rightIcon, error, disabled, ...props }, ref) => {
    return (
      <div className="w-full">
        <div className="relative flex items-center">
          {leftIcon && (
            <div className="absolute left-3 text-muted-foreground pointer-events-none flex items-center">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            disabled={disabled}
            className={cn(
              'w-full h-10 px-3.5 rounded-lg border border-border bg-card text-foreground text-sm shadow-subtle placeholder:text-muted-foreground transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent',
              'disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-muted',
              leftIcon && 'pl-10',
              rightIcon && 'pr-10',
              error && 'border-destructive focus-visible:ring-destructive',
              className
            )}
            {...props}
          />
          {rightIcon && (
            <div className="absolute right-3 text-muted-foreground flex items-center">
              {rightIcon}
            </div>
          )}
        </div>
        {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
