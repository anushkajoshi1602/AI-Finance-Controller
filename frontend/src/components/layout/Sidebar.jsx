import { useState } from 'react';
import {
  LayoutDashboard,
  CreditCard,
  Landmark,
  RotateCcw,
  GitMerge,
  Building2,
  AlertTriangle,
  Bot,
  TrendingUp,
  Settings,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useHealth } from '../../hooks/useApi';
import ConnectionBadge from '../ui/ConnectionBadge';

const NAV_SECTIONS = [
  {
    heading: 'Overview',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    ],
  },
  {
    heading: 'Ledgers',
    items: [
      { to: '/payments', label: 'Payments', icon: CreditCard },
      { to: '/settlements', label: 'Settlements', icon: Landmark },
      { to: '/refunds', label: 'Refunds', icon: RotateCcw },
    ],
  },
  {
    heading: 'Audit & Controls',
    items: [
      { to: '/reconciliation', label: 'Reconciliation', icon: GitMerge },
      { to: '/bank-transactions', label: 'Bank Reconciliation', icon: Building2 },
      { to: '/anomalies', label: 'Anomalies', icon: AlertTriangle },
      { to: '/ai-investigator', label: 'AI Investigator', icon: Bot },
    ],
  },
  {
    heading: 'Planning',
    items: [
      { to: '/cash-flow', label: 'Cash Flow Forecast', icon: TrendingUp },
    ],
  },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const { status, lastChecked } = useHealth(30_000);

  return (
    <aside
      className={`
        relative flex flex-col flex-shrink-0 h-screen
        bg-navy-950 text-slate-200 shadow-sidebar border-r border-white/5
        transition-all duration-300 ease-in-out
        ${collapsed ? 'w-16' : 'w-64'}
      `}
    >
      {/* Brand Header */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-white/10 overflow-hidden">
        <div className="flex-shrink-0 w-9 h-9 bg-accent-600 rounded-xl flex items-center justify-center shadow-sm ring-1 ring-emerald-400/30">
          <ShieldCheck size={19} className="text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-white font-bold text-sm leading-tight truncate tracking-tight">
              AI Finance Controller
            </p>
            <p className="text-emerald-400/90 text-[11px] font-medium truncate mt-0.5">
              Autonomous Recon & Audit
            </p>
          </div>
        )}
      </div>

      {/* Navigation Sections */}
      <nav className="flex-1 px-2.5 py-4 space-y-4 overflow-y-auto overflow-x-hidden">
        {NAV_SECTIONS.map((section) => (
          <div key={section.heading} className="space-y-1">
            {!collapsed && (
              <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400/80 mb-1">
                {section.heading}
              </p>
            )}
            {section.items.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                title={collapsed ? label : undefined}
              >
                <Icon size={17} className="flex-shrink-0" />
                {!collapsed && <span className="truncate">{label}</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Bottom Settings & Live Connection */}
      <div className="px-2.5 pb-3.5 pt-2.5 space-y-2 border-t border-white/10 bg-navy-900/60">
        <NavLink
          to="/settings"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          title={collapsed ? 'Settings' : undefined}
        >
          <Settings size={17} className="flex-shrink-0" />
          {!collapsed && <span className="truncate">Settings</span>}
        </NavLink>

        {!collapsed && (
          <div className="px-1 pt-1">
            <ConnectionBadge status={status} lastChecked={lastChecked} compact />
          </div>
        )}
      </div>

      {/* Collapse Toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="
          absolute -right-3 top-6 z-20
          w-6 h-6 rounded-full bg-navy-800 border border-white/20
          flex items-center justify-center
          text-slate-300 hover:text-white hover:bg-accent-600
          transition-all duration-200 shadow-md
        "
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  );
}
