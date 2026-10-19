
import pandas as pd

# Load reconciliation results
payment_results = pd.read_csv("data/reconciliation_results.csv")
bank_results = pd.read_csv("data/bank_reconciliation_results.csv")

anomalies = []

# Detect payment reconciliation anomalies
for row in payment_results.to_dict("records"):
    if row["status"] != "Matched":
        anomalies.append({
            "source": "Payment Reconciliation",
            "transaction_id": row["payment_id"],
            "anomaly_type": row["status"],
            "amount_difference": row["difference"],
            "severity": "High"
        })

# Detect bank reconciliation anomalies
for row in bank_results.to_dict("records"):
    if row["status"] != "Matched":
        anomalies.append({
            "source": "Bank Reconciliation",
            "transaction_id": row["settlement_id"],
            "anomaly_type": row["status"],
            "amount_difference": row["difference"],
            "severity": "High"
        })

# Convert to DataFrame
anomaly_df = pd.DataFrame(anomalies)

# Display anomalies
print("\nDetected Financial Anomalies:")
if anomaly_df.empty:
    print("No anomalies detected.")
else:
    print(anomaly_df.to_string(index=False))

# Display summary
print("\nAnomaly Summary:")
if anomaly_df.empty:
    print("Total anomalies: 0")
else:
    print("Total anomalies:", len(anomaly_df))
    print(anomaly_df["anomaly_type"].value_counts().to_string())

# Save results
anomaly_df.to_csv("data/anomalies.csv", index=False)

print("\nResults saved to data/anomalies.csv")
