import React, { ReactNode, useState, useRef, useEffect } from 'react';
import { cn } from '../../lib/utils';

export interface DropdownItem {
  label: string;
  icon?: ReactNode;
  onClick?: () => void;
  destructive?: boolean;
  disabled?: boolean;
}

export interface DropdownProps {
  trigger: ReactNode;
  items: (DropdownItem | 'divider')[];
  align?: 'left' | 'right';
  className?: string;
}

export function Dropdown({ trigger, items, align = 'right', className }: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  return (
    <div ref={containerRef} className="relative inline-block text-left">
      <div onClick={() => setIsOpen(!isOpen)}>{trigger}</div>

      {isOpen && (
        <div
          className={cn(
            'absolute z-50 mt-1.5 w-52 rounded-lg border border-border bg-card p-1 shadow-dropdown transition-all focus:outline-none',
            align === 'right' ? 'right-0' : 'left-0',
            className
          )}
        >
          {items.map((item, index) => {
            if (item === 'divider') {
              return <div key={index} className="my-1 h-[1px] bg-border" />;
            }
            return (
              <button
                key={index}
                disabled={item.disabled}
                onClick={() => {
                  item.onClick?.();
                  setIsOpen(false);
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors text-left',
                  item.destructive
                    ? 'text-destructive hover:bg-destructive/10'
                    : 'text-foreground hover:bg-muted',
                  item.disabled && 'opacity-50 cursor-not-allowed'
                )}
              >
                {item.icon && <span className="shrink-0">{item.icon}</span>}
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
