import pandas as pd

# Load CSV files
payments = pd.read_csv("data/payment.csv")
refunds = pd.read_csv("data/refunds.csv")
settlements = pd.read_csv("data/settlements.csv")
bank_transactions = pd.read_csv("data/bank_transactions.csv")

# Create an intentional settlement amount mismatch
settlements.loc[0, "net_amount"] -= 100

# Create an intentional missing settlement
missing_payment_id = settlements.loc[1, "payment_id"]
settlements = settlements.drop(index=1).reset_index(drop=True)

print("Payments:", len(payments))
print("Refunds:", len(refunds))
print("Settlements:", len(settlements))
print("Bank Transactions:", len(bank_transactions))

reconciliation = []

# Reconcile existing settlements
for settlement in settlements.to_dict("records"):

    payment = payments[
        payments["payment_id"] == settlement["payment_id"]
    ]

    if not payment.empty:

        payment_amount = payment.iloc[0]["amount"]

        refund_amount = refunds[
            refunds["payment_id"] == settlement["payment_id"]
        ]["refund_amount"].sum()

        expected_amount = round(
            payment_amount
            - refund_amount
            - settlement["fee"]
            - settlement["tax"],
            2
        )

        actual_amount = settlement["net_amount"]

        status = (
            "Matched"
            if abs(expected_amount - actual_amount) < 0.01
            else "Mismatch"
        )

        reconciliation.append({
            "payment_id": settlement["payment_id"],
            "payment_amount": payment_amount,
            "refund_amount": refund_amount,
            "expected_settlement": expected_amount,
            "actual_settlement": actual_amount,
            "difference": round(expected_amount - actual_amount, 2),
            "status": status
        })

# Detect the intentionally missing settlement
missing_payment = payments[
    payments["payment_id"] == missing_payment_id
]

if not missing_payment.empty:

    payment_amount = missing_payment.iloc[0]["amount"]

    refund_amount = refunds[
        refunds["payment_id"] == missing_payment_id
    ]["refund_amount"].sum()

    reconciliation.append({
        "payment_id": missing_payment_id,
        "payment_amount": payment_amount,
        "refund_amount": refund_amount,
        "expected_settlement": "Missing",
        "actual_settlement": "Missing",
        "difference": "N/A",
        "status": "Missing Settlement"
    })

# Convert results to DataFrame
reconciliation_df = pd.DataFrame(reconciliation)

# Display first 10 records
print("\nReconciliation Results:")
print(reconciliation_df.head(10).to_string(index=False))

# Display summary
print("\nReconciliation Summary:")
print(reconciliation_df["status"].value_counts())

# Save results
reconciliation_df.to_csv(
    "data/reconciliation_results.csv",
    index=False
)

print("\nResults saved to data/reconciliation_results.csv")