import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Payments from './pages/Payments';
import Settlements from './pages/Settlements';
import Refunds from './pages/Refunds';
import Reconciliation from './pages/Reconciliation';
import BankTransactions from './pages/BankTransactions';
import Anomalies from './pages/Anomalies';
import AIInvestigator from './pages/InvestigatorPage';
import CashFlow from './pages/CashFlow';
import Settings from './pages/Settings';
import { createBusiness, getBusinesses, login, register } from './services/api';

function AccessPanel({ onAuthenticated }) {
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (creatingAccount) await register(email, password, fullName);
      const session = await login(email, password);
      onAuthenticated(session.access_token);
    } catch (err) {
      setError(err.message || 'Could not sign in.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen w-full min-w-0 bg-surface-50 flex items-center justify-center p-6">
      <form onSubmit={submit} className="card w-full max-w-md p-8 space-y-5">
        <div>
          <h1 className="text-xl font-bold text-slate-900">AI Finance Controller</h1>
          <p className="text-sm text-slate-500 mt-1">Sign in to open a business workspace.</p>
        </div>
        {creatingAccount && <label className="block text-sm text-slate-700">Full name<input className="input mt-1 w-full" value={fullName} onChange={(e) => setFullName(e.target.value)} /></label>}
        <label className="block text-sm text-slate-700">Email<input className="input mt-1 w-full" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="block text-sm text-slate-700">Password<input className="input mt-1 w-full" type="password" required minLength={creatingAccount ? 12 : 1} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
        <button className="btn-primary w-full justify-center" disabled={busy}>{busy ? 'Please wait…' : creatingAccount ? 'Create account and sign in' : 'Sign in'}</button>
        <button type="button" className="text-sm text-accent-700" onClick={() => { setCreatingAccount((value) => !value); setError(''); }}>
          {creatingAccount ? 'I already have an account' : 'Create an account'}
        </button>
      </form>
    </main>
  );
}

function WorkspacePanel({ businesses, onSelect, onCreated, onLogout }) {
  const [selectedId, setSelectedId] = useState(businesses[0]?.id || '');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try { onCreated(await createBusiness(name)); }
    catch (err) { setError(err.message || 'Could not create workspace.'); }
    finally { setBusy(false); }
  }
  return (
    <main className="min-h-screen bg-surface-50 flex items-center justify-center p-6">
      <div className="card w-full max-w-md p-8 space-y-5">
        <div className="flex justify-between"><h1 className="text-xl font-bold text-slate-900">Choose a workspace</h1><button className="text-sm text-slate-500" onClick={onLogout}>Sign out</button></div>
        {businesses.length > 0 && <div className="space-y-2"><select className="input w-full" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>{businesses.map((business) => <option key={business.id} value={business.id}>{business.name}</option>)}</select><button className="btn-primary w-full justify-center" onClick={() => onSelect(selectedId)}>Open workspace</button></div>}
        <form onSubmit={create} className="border-t border-slate-100 pt-4 space-y-3"><label className="block text-sm text-slate-700">Create a new business<input className="input mt-1 w-full" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} placeholder="Business name" /></label>{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}<button className="btn-secondary w-full justify-center" disabled={busy}>{busy ? 'Creating…' : 'Create workspace'}</button></form>
      </div>
    </main>
  );
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('access_token'));
  const [businesses, setBusinesses] = useState([]);
  const [businessId, setBusinessId] = useState(() => localStorage.getItem('business_id') || '');
  const [loadingBusinesses, setLoadingBusinesses] = useState(false);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoadingBusinesses(true);
    getBusinesses().then((rows) => {
      if (!active) return;
      setBusinesses(rows);
      const stored = localStorage.getItem('business_id');
      const selectedId = stored && rows.some((business) => business.id === stored)
        ? stored
        : rows.length === 1 ? rows[0].id : '';
      if (selectedId) localStorage.setItem('business_id', selectedId);
      else localStorage.removeItem('business_id');
      setBusinessId(selectedId);
    }).catch(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('business_id');
      setToken('');
    }).finally(() => active && setLoadingBusinesses(false));
    return () => { active = false; };
  }, [token]);

  function selectBusiness(id) {
    localStorage.setItem('business_id', id);
    setBusinessId(id);
  }
  function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('business_id');
    setToken('');
    setBusinessId('');
    setBusinesses([]);
  }

  if (!token) return <AccessPanel onAuthenticated={(value) => { localStorage.setItem('access_token', value); setToken(value); }} />;
  if (loadingBusinesses) return <main className="min-h-screen flex items-center justify-center text-slate-500">Loading workspaces…</main>;
  if (!businessId || !businesses.some((business) => business.id === businessId)) {
    return <WorkspacePanel businesses={businesses} onSelect={selectBusiness} onLogout={logout} onCreated={(business) => { setBusinesses((rows) => [...rows, business]); selectBusiness(business.id); }} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout key={businessId} businesses={businesses} businessId={businessId} onBusinessChange={selectBusiness} onLogout={logout} />}>
          <Route index element={<Dashboard />} />
          <Route path="payments" element={<Payments />} />
          <Route path="settlements" element={<Settlements />} />
          <Route path="refunds" element={<Refunds />} />
          <Route path="reconciliation" element={<Reconciliation />} />
          <Route path="bank-transactions" element={<BankTransactions />} />
          <Route path="bank-reconciliation" element={<Navigate to="/bank-transactions" replace />} />
          <Route path="anomalies" element={<Anomalies />} />
          <Route path="ai-investigator" element={<AIInvestigator />} />
          <Route path="cash-flow" element={<CashFlow />} />
          <Route path="settings" element={<Settings />} />
          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
