import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 60000, // 60s timeout to accommodate full analysis runs
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    // The instance default is JSON; remove it so the browser adds the multipart boundary.
    config.headers.delete('Content-Type');
  }
  return config;
});

const businessPath = (path) => {
  const businessId = localStorage.getItem('business_id');
  if (!businessId) throw new Error('Select a business workspace first.');
  return `/api/businesses/${encodeURIComponent(businessId)}${path}`;
};

export const login = (email, password) =>
  apiClient.post('/api/auth/login', { email, password }).then((r) => r.data);
export const register = (email, password, fullName) =>
  apiClient.post('/api/auth/register', { email, password, full_name: fullName || null }).then((r) => r.data);
export const getBusinesses = () => apiClient.get('/api/businesses').then((r) => r.data);
export const createBusiness = (name) => apiClient.post('/api/businesses', { name }).then((r) => r.data.business);

export const uploadCsv = (dataset, selectedFile) => {
  const formData = new FormData();
  formData.append('file', selectedFile);
  return apiClient.post(businessPath(`/imports/${dataset}`), formData).then((r) => r.data);
};

// Response interceptor for centralized error handling (handles string and object detail payloads)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail;
    let message = 'An unexpected error occurred while communicating with the backend.';

    if (typeof detail === 'string') {
      message = detail;
    } else if (detail && typeof detail === 'object') {
      if (detail.failed_script) {
        message = `Script "${detail.failed_script}" failed: ${detail.error || 'Execution error'}`;
      } else if (detail.message) {
        message = detail.error ? `${detail.message}: ${detail.error}` : detail.message;
      } else {
        message = JSON.stringify(detail);
      }
    } else if (error.response?.data?.message) {
      message = error.response.data.message;
    } else if (error.code === 'ECONNABORTED') {
      message = 'Request timed out. The backend may still be processing the analysis.';
    } else if (!error.response) {
      message = `No response received from ${BASE_URL}. Check the server address, network connection, and browser CORS settings.`;
    } else if (error.message) {
      message = error.message;
    }

    return Promise.reject(new Error(message));
  }
);

// ── Health ──────────────────────────────────────────────────────────────────
export const getHealth = () => apiClient.get('/api/health').then((r) => r.data);

// ── Dashboard ────────────────────────────────────────────────────────────────
export const getDashboard = () => apiClient.get(businessPath('/dashboard')).then((r) => r.data);

// ── Payments ─────────────────────────────────────────────────────────────────
export const getPayments = () => apiClient.get(businessPath('/ledger/payments')).then((r) => r.data);

// ── Settlements ──────────────────────────────────────────────────────────────
export const getSettlements = () => apiClient.get(businessPath('/ledger/settlements')).then((r) => r.data);

// ── Refunds ──────────────────────────────────────────────────────────────────
export const getRefunds = () => apiClient.get(businessPath('/ledger/refunds')).then((r) => r.data);

// ── Reconciliation ───────────────────────────────────────────────────────────
export const getReconciliation = () => apiClient.get(businessPath('/reconciliation/results')).then((r) => ({
  run_id: r.data.run_id,
  results: r.data.results.map((row) => ({ ...row, payment_id: row.payment_external_id, settlement_id: row.settlement_external_id,
    expected_settlement: row.expected_settlement ?? 'Missing', actual_settlement: row.actual_settlement ?? 'Missing' })),
}));

// ── Bank Reconciliation ──────────────────────────────────────────────────────
export const getBankReconciliation = () =>
  apiClient.get(businessPath('/bank-reconciliation/results')).then((r) => r.data);

// ── Anomalies ────────────────────────────────────────────────────────────────
export const getAnomalies = () => apiClient.get(businessPath('/anomalies/results')).then((r) => ({
  run_id: r.data.run_id,
  results: r.data.results.map((row) => ({ ...row, transaction_id: row.transaction_external_id })),
}));

// ── Investigations ───────────────────────────────────────────────────────────
export const getInvestigations = () =>
  apiClient.get(businessPath('/investigations/results')).then((r) => r.data);
export const runInvestigation = () =>
  apiClient.post(businessPath('/investigations/run')).then((r) => r.data);

// ── Cash Flow Forecast ───────────────────────────────────────────────────────
export const getCashFlowForecast = () =>
  apiClient.get(businessPath('/cash-flow/results')).then((r) => ({
    run_id: r.data.run_id,
    results: r.data.results.map((row) => ({
    date: row.forecast_date,
    predicted_cash_inflow: row.predicted_cash_inflow,
    })),
  }));

// ── Actions ──────────────────────────────────────────────────────────────────
export const runReconciliation = () =>
  apiClient.post(businessPath('/reconciliation/run')).then((r) => r.data);

export const runBankReconciliation = () =>
  apiClient.post(businessPath('/bank-reconciliation/run')).then((r) => r.data);
export const runAnomalyDetection = () =>
  apiClient.post(businessPath('/anomalies/run')).then((r) => r.data);
export const runCashFlowForecast = () =>
  apiClient.post(businessPath('/cash-flow/run')).then((r) => r.data);

export const runFullAnalysis = async () => {
  const reconciliation = await runReconciliation();
  const bankReconciliation = await runBankReconciliation();
  const anomalies = await runAnomalyDetection();
  const cashFlow = await runCashFlowForecast();
  return { message: 'Business-scoped financial analysis completed', reconciliation, bankReconciliation, anomalies, cashFlow };
};

export default apiClient;
