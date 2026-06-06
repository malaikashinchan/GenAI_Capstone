import json
from tools.llm_client import llm_client

prompt = """
You are a privacy and data governance expert.

Dataset: customers
Schema columns and their data types (NO RAW DATA PROVIDED FOR PRIVACY):
{
  "customer_id": "VARCHAR(16777216)",
  "customer_unique_id": "VARCHAR(16777216)"
}

Classify EVERY column by PII sensitivity level:
- HIGH   → directly identifies a person (name, email, SSN, phone, address, account number)
- MEDIUM → indirectly identifies (customer_id, order_id, unique_id, zip_code)
- LOW    → contextual but not identifying (amount, city, state, category, status)
- NONE   → no privacy concern (timestamps, flags, system codes, counts)

Respond ONLY with valid JSON in this exact format:
{
  "column_name": {"pii_level": "HIGH|MEDIUM|LOW|NONE", "reason": "brief reason"},
  ...
}

Classify ALL columns. No explanation. No markdown. Only JSON.
"""

raw = llm_client.invoke(prompt).strip()
print("RAW LLM OUTPUT:")
print(raw)

import re
match = re.search(r'\{.*\}', raw, re.DOTALL)
if match:
    extracted = match.group(0)
    print("\nEXTRACTED JSON:")
    print(extracted)
    try:
        parsed = json.loads(extracted)
        print("\nPARSED SUCCESSFULLY")
    except Exception as e:
        print("\nPARSE FAILED:", e)
else:
    print("\nNO JSON MATCH FOUND")
