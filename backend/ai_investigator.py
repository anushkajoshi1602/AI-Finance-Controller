
import os
import time
import pandas as pd
from dotenv import load_dotenv
from google import genai

# Load environment variables from the project root
load_dotenv()

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY not found. Check your project-root .env file."
    )

client = genai.Client(api_key=api_key)

# Load detected anomalies
anomalies = pd.read_csv("data/anomalies.csv")


def investigate_anomaly(row):
    anomaly = row.to_dict()

    prompt = f"""
You are an AI financial reconciliation investigator.

Analyze this financial anomaly using only the supplied evidence.

Anomaly details:
{anomaly}

Provide the following:

1. Explanation of the discrepancy.
2. Possible causes, clearly labelled as possibilities.
3. Recommended verification steps.
4. Severity: Low, Medium, or High, with a brief reason.

Rules:
- Do not claim fraud without evidence.
- Do not invent missing facts.
- If information is missing, explicitly mention it.
- Keep the investigation concise and practical.
"""

    # Retry temporary Gemini 503 errors
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )

            if response.text:
                return response.text

            return "AI returned an empty response."

        except Exception as error:
            error_message = str(error)

            is_temporary = (
                "503" in error_message
                or "UNAVAILABLE" in error_message
                or "429" in error_message
                or "RESOURCE_EXHAUSTED" in error_message
            )

            if is_temporary and attempt < 2:
                wait_seconds = 2 ** (attempt + 1)

                print(
                    f"Temporary Gemini error for "
                    f"{row['transaction_id']}. "
                    f"Retrying in {wait_seconds} seconds "
                    f"(attempt {attempt + 2}/3)..."
                )

                time.sleep(wait_seconds)

            else:
                return f"AI investigation failed: {error_message}"

    return "AI investigation failed after retries."


# Run investigations
if anomalies.empty:
    print("No anomalies available for investigation.")

else:
    print(f"Investigating {len(anomalies)} anomalies...\n")

    anomalies["ai_investigation"] = anomalies.apply(
        investigate_anomaly,
        axis=1
    )

    # Display results
    print("\nAI Finance Investigator Report:\n")
    print(anomalies.to_string(index=False))

    # Save report
    output_path = "data/investigation_report.csv"

    anomalies.to_csv(output_path, index=False)

    print(f"\nReport saved to {output_path}")
