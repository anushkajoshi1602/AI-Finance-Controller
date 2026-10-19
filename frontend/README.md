# AI Finance Controller — Frontend

A modern React + Vite fintech operations dashboard for the **AI Finance Controller** FastAPI backend. Designed with a midnight navy sidebar, warm white workspace, slate typography, and emerald accents.

## Features & Pages

The application provides **10 dedicated views** mapped directly to the FastAPI backend and CSV data schemas:

1. **Dashboard (`/`)** — Executive KPIs (Successful Volume, Total Transactions, Net Settlements, Total Refunds, Active Anomalies), Monthly Successful Payment Volume trend, Payment Method breakdown (`UPI`, `Netbanking`, `Card`), Discrepancy Watchlist, and Recent Payment Activity.
2. **Payments (`/payments`)** — Searchable, sortable, filterable ledger mapped to `payment_id`, `customer_id`, `payment_method`, `amount`, `status` (`Success`, `Failed`, `Pending`), `failure_reason`, and `payment_date`.
3. **Settlements (`/settlements`)** — Gateway payout ledger displaying `settlement_id`, `payment_id`, `gross_amount`, `refund_amount`, `fee` (2%), `tax` (18%), and `net_amount`.
4. **Refunds (`/refunds`)** — Customer refund reversals displaying `refund_id`, `payment_id`, `refund_amount`, and `refund_date`.
5. **Reconciliation (`/reconciliation`)** — Payment-to-settlement audit comparing `payment_amount`, `refund_amount`, `expected_settlement`, `actual_settlement`, `difference`, and `status` (`Matched`, `Mismatch`, `Missing Settlement`), plus a trigger for `POST /api/run-reconciliation`.
6. **Bank Reconciliation (`/bank-transactions`)** — Settlement-to-bank statement matching (`settlement_id`, `settlement_amount`, `bank_amount`, `difference`, `status`).
7. **Anomalies (`/anomalies`)** — Flagged discrepancies across Payment and Bank Reconciliation (`source`, `transaction_id`, `anomaly_type`, `amount_difference`, `severity`, and operational guidance).
8. **AI Investigator (`/ai-investigator`)** — Formatted Gemini root-cause analysis reports (`ai_investigation`) with graceful handling for free-tier rate limits (`429`) and temporary demand spikes (`503`).
9. **Cash Flow Forecast (`/cash-flow`)** — 7-day projected settlement inflows (`date`, `predicted_cash_inflow`), daily and cumulative trajectory charts, and daily schedule.
10. **Settings (`/settings`)** — Live `/api/health` connection diagnostics, endpoint-to-CSV schema reference, and security status.

---

## Quick Start

### 1. Configure Environment Variables

Ensure `.env` (or `.env.example`) points to your local FastAPI backend:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Run Development Server

```bash
npm run dev
```

Open **http://localhost:5173** in your browser.

### 4. Production Build & Lint

```bash
npm run lint
npm run build
```
