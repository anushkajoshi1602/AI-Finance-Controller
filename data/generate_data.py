import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
customers = []

for i in range(1000):
    name = fake.name()

    customer = {
        "customer_id": i + 1,
        "customer_name": name,
        "customer_email": name.lower().replace(" ", ".") + "@example.com"
    }

    customers.append(customer)

df = pd.DataFrame(customers)
df.to_csv("data/customers.csv", index=False)

payments = []

payment_method = ["UPI", "Netbanking", "Card"]

failure_reasons = [
    "Bank Error",
    "Insufficient Funds",
    "Card Expired",
    "Invalid Details",
    "Network Error"
]

for i in range(1000):
    payment = {
        "payment_id": f"p{i+1:05d}",
        "customer_id": i + 1,
        "payment_method": str(np.random.choice(payment_method)),
        "amount": np.random.randint(100, 1000),
        "status": str(np.random.choice(
            ["Success", "Failed", "Pending"],
            p=[0.85, 0.10, 0.05]
        )),
        "failure_reason": "",
        "payment_date": fake.date_time_this_year().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    if payment["status"] == "Failed":
        payment["failure_reason"] = str(
            np.random.choice(failure_reasons)
        )

    payments.append(payment)

df = pd.DataFrame(payments)
df.to_csv("data/payment.csv", index=False)

refunds = []

for payment in payments:
    if payment["status"] == "Success":

        refund_probability = np.random.random()

        if refund_probability < 0.05:

            refund = {
                "refund_id": f"R{len(refunds)+1:05d}",
                "payment_id": payment["payment_id"],
                "refund_amount": np.random.randint(
                    50,
                    payment["amount"] + 1
                ),
                "refund_date": fake.date_time_this_year().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }

            refunds.append(refund)

refund_df = pd.DataFrame(refunds)
refund_df.to_csv("data/refunds.csv", index=False)


settlements = []

for payment in payments:
    if payment["status"] == "Success":

        gross_amount = payment["amount"]

        refund_amount = sum(
            refund["refund_amount"]
            for refund in refunds
            if refund["payment_id"] == payment["payment_id"]
        )

        fee = round(gross_amount * 0.02, 2)
        tax = round(fee * 0.18, 2)

        net_amount = round(
            gross_amount - refund_amount - fee - tax,
            2
        )

        settlement = {
            "settlement_id": f"S{len(settlements)+1:05d}",
            "payment_id": payment["payment_id"],
            "gross_amount": gross_amount,
            "refund_amount": refund_amount,
            "fee": fee,
            "tax": tax,
            "net_amount": net_amount
        }

        settlements.append(settlement)

settlement_df = pd.DataFrame(settlements)
settlement_df.to_csv("data/settlements.csv", index=False)


bank_transactions = []

for settlement in settlements:

    bank_transaction = {
        "transaction_id": f"T{len(bank_transactions)+1:05d}",
        "settlement_id": settlement["settlement_id"],
        "amount": settlement["net_amount"],
        "transaction_type": "Credit",
        "transaction_date": fake.date_time_this_year().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    bank_transactions.append(bank_transaction)

bank_df = pd.DataFrame(bank_transactions)
bank_df.to_csv("data/bank_transactions.csv", index=False)