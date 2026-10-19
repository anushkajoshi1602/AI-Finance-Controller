
import pandas as pd

# Load CSV files
settlements = pd.read_csv("data/settlements.csv")
bank_transactions = pd.read_csv("data/bank_transactions.csv")

# Create an intentional bank amount mismatch
bank_transactions.loc[0, "amount"] -= 50

# Create an intentional missing bank transaction
bank_transactions = bank_transactions.drop(index=1).reset_index(drop=True)

# Match settlements with bank transactions
reconciliation = settlements.merge(
    bank_transactions,
    on="settlement_id",
    how="outer",
    suffixes=("_settlement", "_bank"),
    indicator=True
)

results = []

for row in reconciliation.to_dict("records"):

    settlement_amount = row.get("net_amount")
    bank_amount = row.get("amount")

    if row["_merge"] == "left_only":
        status = "Missing Bank Transaction"
        difference = "N/A"

    elif row["_merge"] == "right_only":
        status = "Unmatched Bank Transaction"
        difference = "N/A"

    else:
        difference = round(settlement_amount - bank_amount, 2)

        if abs(difference) < 0.01:
            status = "Matched"
        else:
            status = "Amount Mismatch"

    results.append({
        "settlement_id": row["settlement_id"],
        "settlement_amount": settlement_amount,
        "bank_amount": bank_amount,
        "difference": difference,
        "status": status
    })

# Create results DataFrame
results_df = pd.DataFrame(results)

# Display results
print("\nBank Reconciliation Results:")
print(results_df.head(10).to_string(index=False))

print("\nBank Reconciliation Summary:")
print(results_df["status"].value_counts())

# Save results
results_df.to_csv(
    "data/bank_reconciliation_results.csv",
    index=False
)

print("\nResults saved to data/bank_reconciliation_results.csv")
