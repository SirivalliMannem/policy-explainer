import { LayoutDashboard, Sparkles, Settings, HelpCircle } from 'lucide-react';
import { NavItem } from '../types';

export const APP_CONFIG = {
  name: 'Policy Explainer',
  tagline: 'Enterprise Insurance Intelligence',
  version: '0.1.0',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
};

export const PRIMARY_NAV_ITEMS: NavItem[] = [
  {
    title: 'Dashboard',
    href: '/app/dashboard',
    icon: LayoutDashboard,
  },
  {
    title: 'Policy Explainer',
    href: '/app/explainer',
    icon: Sparkles,
  },
];

export const SECONDARY_NAV_ITEMS: NavItem[] = [
  {
    title: 'Settings',
    href: '/app/settings',
    icon: Settings,
  },
  {
    title: 'Help',
    href: '/app/help',
    icon: HelpCircle,
  },
];
