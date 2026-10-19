import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

const PAGE_META = {
  '/': {
    title: 'Executive Dashboard',
    subtitle: 'Consolidated KPIs, payment volume trends, and discrepancy surveillance',
  },
  '/payments': {
    title: 'Payments Ledger',
    subtitle: 'Captured, failed, and pending customer payment transactions',
  },
  '/settlements': {
    title: 'Gateway Settlements',
    subtitle: 'Imported gateway settlement gross, refunds, fees, tax, and net payouts',
  },
  '/refunds': {
    title: 'Customer Refunds',
    subtitle: 'Processed customer reversals deducted from settlement batches',
  },
  '/reconciliation': {
    title: 'Payment Reconciliation',
    subtitle: 'Expected vs. actual gateway settlement verification',
  },
  '/bank-transactions': {
    title: 'Bank Reconciliation',
    subtitle: 'Gateway settlement payouts matched against bank statement credits',
  },
  '/anomalies': {
    title: 'Detected Anomalies',
    subtitle: 'High-priority discrepancies flagged across payment and bank audits',
  },
  '/ai-investigator': {
    title: 'AI Financial Investigator',
    subtitle: 'AI investigation is not connected to business-scoped financial runs',
  },
  '/cash-flow': {
    title: 'Cash Flow Forecast',
    subtitle: '7-day projected settlement inflows based on historical net volume',
  },
  '/settings': {
    title: 'Settings & Diagnostics',
    subtitle: 'FastAPI connectivity, CSV schema bindings, and environment status',
  },
};

export default function Layout({ businesses = [], businessId, onBusinessChange, onLogout }) {
  const { pathname } = useLocation();
  const meta = PAGE_META[pathname] ?? {
    title: 'AI Finance Controller',
    subtitle: 'Financial Operations & Autonomous Reconciliation',
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-surface-50">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar title={meta.title} subtitle={meta.subtitle} />
        <div className="flex items-center justify-end gap-2 px-6 py-2 bg-white border-b border-slate-100">
          <label htmlFor="active-business" className="text-xs text-slate-500">Workspace</label>
          <select id="active-business" className="input py-1.5 text-xs" value={businessId} onChange={(event) => onBusinessChange(event.target.value)}>
            {businesses.map((business) => <option key={business.id} value={business.id}>{business.name}</option>)}
          </select>
          <button className="text-xs text-slate-500 hover:text-slate-900" onClick={onLogout}>Sign out</button>
        </div>
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
