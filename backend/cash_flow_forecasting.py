
import pandas as pd

# Load payment and settlement data
payments = pd.read_csv("data/payment.csv")
settlements = pd.read_csv("data/settlements.csv")

# Load payment dates
payments["payment_date"] = pd.to_datetime(
    payments["payment_date"], errors="coerce"
)

# Keep successful payments
successful_payments = payments[
    payments["status"] == "Success"
].copy()

# Attach settlement amounts to successful payments
forecast_data = successful_payments.merge(
    settlements[["payment_id", "net_amount"]],
    on="payment_id",
    how="left"
)

# Remove payments without settlement records
forecast_data = forecast_data.dropna(
    subset=["payment_date", "net_amount"]
)

# Aggregate historical net settlement amounts by payment date
forecast_data["date"] = forecast_data["payment_date"].dt.date

daily_cashflow = (
    forecast_data.groupby("date")["net_amount"]
    .sum()
    .sort_index()
)

print("\nHistorical Daily Cash Inflows:")
print(daily_cashflow.tail(7).to_string())

# Forecast using the average daily inflow
if daily_cashflow.empty:
    print("\nNo historical settlement data available for forecasting.")

else:
    average_daily_inflow = daily_cashflow.mean()

    last_date = pd.Timestamp(daily_cashflow.index[-1])

    forecast_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=7,
        freq="D"
    )

    forecast = pd.DataFrame({
        "date": forecast_dates.date,
        "predicted_cash_inflow": [
            round(average_daily_inflow, 2)
        ] * 7
    })

    print("\n7-Day Cash Flow Forecast:")
    print(forecast.to_string(index=False))

    print(
        "\nExpected Total Cash Inflow:",
        round(forecast["predicted_cash_inflow"].sum(), 2)
    )

    forecast.to_csv(
        "data/cash_flow_forecast.csv",
        index=False
    )

    print("\nForecast saved to data/cash_flow_forecast.csv")
