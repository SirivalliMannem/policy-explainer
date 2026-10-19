import React from 'react';
import { Menu } from 'lucide-react';
import { Button } from '../ui/Button';

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
    <header className="sticky top-0 z-30 flex h-[76px] w-full items-center justify-between border-b border-[#E3E8F0] bg-white px-4 sm:px-8">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenMobileMenu}
          className="lg:hidden text-muted-foreground mr-1"
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div className="flex items-center gap-3.5">
          <div className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-[12px] bg-[#0F2A43] shadow-[0_4px_12px_rgba(15,42,67,0.25)]">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F97316" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-['Instrument_Serif',Georgia,serif] text-[26px] sm:text-[30px] leading-none text-[#0F2A43] tracking-[-0.01em]">
              Policy <em className="text-[#EA580C] not-italic italic font-normal">Explainer</em>
            </span>
            <span className="text-[11.5px] font-semibold tracking-[0.14em] uppercase text-[#64748B] hidden sm:block">
              Grounded policy intelligence
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {isBackendHealthy ? (
          <div className="flex items-center gap-2 text-[13px] font-medium text-[#166534] bg-[#F0FDF4] border border-[#BBF7D0] rounded-full px-3 py-1.5 shadow-2xs">
            <span className="h-[7px] w-[7px] rounded-full bg-[#16A34A] animate-pulse" />
            <span>Engine online</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-[13px] font-medium text-red-700 bg-red-50 border border-red-200 rounded-full px-3 py-1.5 shadow-2xs">
            <span className="h-[7px] w-[7px] rounded-full bg-red-600" />
            <span>Engine offline</span>
          </div>
        )}
      </div>
    </header>
  );
}
