"""
agents/nodes/pii_detector.py
Node 3 — PII Detector
LLM reads schema + sample rows and classifies every column by PII sensitivity.
Result written to pii_map in State for the masking node.
Dataset: Olist Brazilian E-Commerce
"""
import json
from agents.state import AgentState
from tools.llm_client import llm_client
from loguru import logger
import pandas as pd


PII_DETECT_PROMPT = """
You are a privacy and data governance expert.

Dataset: {dataset}
Schema columns and their data types (NO RAW DATA PROVIDED FOR PRIVACY):
{schema}

Classify EVERY column by PII sensitivity level:
- HIGH   → directly identifies a person (name, email, SSN, phone, address, account number)
- MEDIUM → indirectly identifies (customer_id, order_id, unique_id, zip_code)
- LOW    → contextual but not identifying (amount, city, state, category, status)
- NONE   → no privacy concern (timestamps, flags, system codes, counts)

Respond ONLY with valid JSON in this exact format:
{{
  "column_name": {{"pii_level": "HIGH|MEDIUM|LOW|NONE", "reason": "brief reason"}},
  ...
}}

Classify ALL columns. No explanation. No markdown. Only JSON.
"""


import re

_analyzer = None
def get_analyzer():
    global _analyzer
    if _analyzer is None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine_instance = provider.create_engine()
            _analyzer = AnalyzerEngine(nlp_engine=nlp_engine_instance, supported_languages=["en"])
        except Exception as e:
            from loguru import logger
            logger.warning(f"Presidio load failed: {e}")
            pass
    return _analyzer

def run(state: AgentState) -> AgentState:
    state["current_node"] = "pii_detector"
    dataset     = state.get("dataset_name", "customers")
    schema      = state.get("schema", {})
    sample_rows = state.get("sample_rows", [])

    logger.info(f"PII_DETECTOR | Starting Cascade | dataset={dataset} | columns={list(schema.keys())}")

    pii_map = {}
    unclassified_schema = {}
    analyzer = get_analyzer()

    try:
        # STEP 1, 2, & 3: Cascade execution per column
        for col, dtype in schema.items():
            col_lower = col.lower()
            classified = False
            
            # Step 1: Column Name Heuristics
            if any(k in col_lower for k in ['email', 'ssn', 'password', 'name', 'phone']):
                pii_map[col] = {"pii_level": "HIGH", "reason": "Column name heuristic (direct identifier)"}
                classified = True
            elif any(k in col_lower for k in ['id', 'zip', 'plate']):
                pii_map[col] = {"pii_level": "MEDIUM", "reason": "Column name heuristic (indirect identifier)"}
                classified = True
                
            if classified:
                continue

            # Check raw values for Regex/Presidio
            col_values = [str(r.get(col, "")) for r in sample_rows if pd.notna(r.get(col, ""))]
            
            # Step 2: Local Regex Rules
            email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
            for val in col_values:
                if email_regex.match(val):
                    pii_map[col] = {"pii_level": "HIGH", "reason": "Regex match: Email"}
                    classified = True
                    break
            
            if classified:
                continue
                
            # Step 3: Local Presidio NLP Detection
            if analyzer:
                for val in col_values:
                    results = analyzer.analyze(text=val, entities=None, language='en')
                    if results:
                        best_entity = results[0].entity_type
                        if best_entity in ['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'CREDIT_CARD', 'US_SSN', 'IP_ADDRESS']:
                            pii_map[col] = {"pii_level": "HIGH", "reason": f"Presidio NLP: {best_entity}"}
                            classified = True
                            break
                        elif best_entity in ['LOCATION', 'URL']:
                            pii_map[col] = {"pii_level": "MEDIUM", "reason": f"Presidio NLP: {best_entity}"}
                            classified = True
                            break

            if not classified:
                # Add to LLM fallback queue
                unclassified_schema[col] = dtype

        # Step 4: LLM Fallback (Schema-Only)
        if unclassified_schema:
            logger.info(f"PII_DETECTOR | LLM Fallback required for {len(unclassified_schema)} columns: {list(unclassified_schema.keys())}")
            prompt = PII_DETECT_PROMPT.format(
                dataset     = dataset,
                schema      = json.dumps(unclassified_schema, indent=2)
            )

            raw = llm_client.invoke(prompt).strip()
            
            # Robustly extract JSON block using regex
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                raw = match.group(0)
                
            raw = raw.strip()
            llm_map = json.loads(raw)
            
            # Robust mapping: LLM might return list or flat dict
            if isinstance(llm_map, list):
                # LLM returned [{"column_name": "x", "pii_level": "LOW"}]
                for item in llm_map:
                    if isinstance(item, dict):
                        col = item.get("column_name", item.get("column"))
                        if col in unclassified_schema:
                            pii_map[col] = {"pii_level": item.get("pii_level", "NONE")}
            elif isinstance(llm_map, dict):
                for k, v in llm_map.items():
                    if k in unclassified_schema:
                        if isinstance(v, dict):
                            pii_map[k] = v
                        elif isinstance(v, str):
                            # LLM returned {"col": "LOW"}
                            pii_map[k] = {"pii_level": v, "reason": "LLM fallback"}
            
            # Ensure everything in pii_map has a pii_level that can be .get()
            for k in pii_map:
                if not isinstance(pii_map[k], dict):
                    pii_map[k] = {"pii_level": "NONE", "reason": "Invalid LLM struct"}

        high   = [c for c, v in pii_map.items() if v.get("pii_level") == "HIGH"]
        medium = [c for c, v in pii_map.items() if v.get("pii_level") == "MEDIUM"]
        low    = [c for c, v in pii_map.items() if v.get("pii_level") == "LOW"]

        logger.success(
            f"PII_DETECTOR | Cascade Done | HIGH={high} | MEDIUM={medium} | LOW={low}"
        )

        state["pii_map"] = pii_map
        state["node_status"]["pii_detector"] = "pass"

    except Exception as e:
        logger.error(f"PII_DETECTOR | FAILED: {e}")
        state["node_errors"]["pii_detector"] = str(e)
        state["node_status"]["pii_detector"] = "fail"

    return state
