
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.auth_routes import get_current_user, router as auth_router
from backend.business_routes import router as business_router
from backend.db.models import User
from backend.reconciliation_routes import router as reconciliation_router
from backend.anomaly_routes import router as anomaly_router
from backend.cash_flow_routes import router as cash_flow_router
from backend.financial_read_routes import router as financial_read_router
from backend.bank_reconciliation_routes import router as bank_reconciliation_router
from backend.investigation_routes import router as investigation_router

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

app = FastAPI(
    title="AI Finance Controller API",
    description="Financial reconciliation, anomaly detection, "
                "AI investigation, and cash-flow forecasting.",
    version="1.0.0",
)
app.include_router(auth_router)
app.include_router(business_router)
from backend.csv_import_routes import router as csv_import_router
app.include_router(csv_import_router)
app.include_router(reconciliation_router)
app.include_router(anomaly_router)
app.include_router(cash_flow_router)
app.include_router(financial_read_router)
app.include_router(bank_reconciliation_router)
app.include_router(investigation_router)


# Allow the local frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_csv(filename: str):
    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found. Run its backend module first."
        )

    try:
        df = pd.read_csv(file_path)
        df = df.astype(object).where(pd.notna(df), None)
        return df.to_dict(orient="records")

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read {filename}: {error}"
        )


def require_legacy_financial_access(user: User = Depends(get_current_user)) -> None:
    """Fail closed until legacy shared CSV data has an explicit business scope."""
    raise HTTPException(
        status_code=503,
        detail="Legacy financial data is unavailable until business-scoped processing is enabled",
    )


@app.get("/")
def home():
    return {
        "message": "AI Finance Controller API is running",
        "docs": "/docs"
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/dashboard")
def dashboard(_access: None = Depends(require_legacy_financial_access)):
    payments = load_csv("payment.csv")
    settlements = load_csv("settlements.csv")
    refunds = load_csv("refunds.csv")
    anomalies = load_csv("anomalies.csv")

    successful_payments = [
        payment for payment in payments
        if payment.get("status") == "Success"
    ]

    total_payment_amount = sum(
        float(payment.get("amount") or 0)
        for payment in successful_payments
    )

    total_refunds = sum(
        float(refund.get("refund_amount") or 0)
        for refund in refunds
    )

    total_settlements = sum(
        float(settlement.get("net_amount") or 0)
        for settlement in settlements
    )

    return {
        "total_payments": len(payments),
        "successful_payments": len(successful_payments),
        "total_payment_amount": round(total_payment_amount, 2),
        "total_refunds": round(total_refunds, 2),
        "total_settlements": round(total_settlements, 2),
        "total_anomalies": len(anomalies),
    }


@app.get("/api/payments")
def get_payments(_access: None = Depends(require_legacy_financial_access)):
    return load_csv("payment.csv")


@app.get("/api/settlements")
def get_settlements(_access: None = Depends(require_legacy_financial_access)):
    return load_csv("settlements.csv")


@app.get("/api/refunds")
def get_refunds(_access: None = Depends(require_legacy_financial_access)):
    return load_csv("refunds.csv")


@app.get("/api/reconciliation")
def get_reconciliation(_access: None = Depends(require_legacy_financial_access)):
    return load_csv("reconciliation_results.csv")


@app.get("/api/bank-reconciliation")
def get_bank_reconciliation(_access: None = Depends(require_legacy_financial_access)):
    return load_csv("bank_reconciliation_results.csv")


@app.get("/api/anomalies")
def get_anomalies(_access: None = Depends(require_legacy_financial_access)):
    return load_csv("anomalies.csv")


@app.get("/api/investigations")
def get_investigations(_access: None = Depends(require_legacy_financial_access)):
    return load_csv("investigation_report.csv")


@app.get("/api/cash-flow-forecast")
def get_cash_flow_forecast(_access: None = Depends(require_legacy_financial_access)):
    return load_csv("cash_flow_forecast.csv")

import subprocess
import sys


@app.post("/api/run-reconciliation")
def run_reconciliation(_access: None = Depends(require_legacy_financial_access)):
    script_path = BASE_DIR / "backend" / "reconciliation.py"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Reconciliation failed",
                "error": result.stderr
            }
        )

    return {
        "message": "Reconciliation completed successfully",
        "output": result.stdout
    }

@app.post("/api/run-full-analysis")
def run_full_analysis(_access: None = Depends(require_legacy_financial_access)):
    scripts = [
        "reconciliation.py",
        "bank_reconciliation.py",
        "anomaly_detection.py",
        "ai_investigator.py",
        "cash_flow_forecasting.py",
    ]

    results = []

    for script in scripts:
        script_path = BASE_DIR / "backend" / script

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "failed_script": script,
                    "error": result.stderr
                }
            )

        results.append({
            "script": script,
            "status": "success",
            "output": result.stdout
        })

    return {
        "message": "Full financial analysis completed",
        "results": results
    }
