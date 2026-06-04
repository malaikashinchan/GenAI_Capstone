"""
agents/nodes/schema_drift.py
Node 2 — Schema Drift Detector
Compares incoming schema vs known-good schema per Olist dataset.
LLM detects renamed columns. Drift events written to metadata/schema_drift_log.json.
"""
import json
import uuid
from datetime import datetime
from agents.state import AgentState
from tools.snowflake_mcp_tool import mcp_tool
from tools.llm_client import llm_client
from config.settings import PipelineConfig
from loguru import logger



RENAME_PROMPT = """
You are a schema comparison expert.
Old schema columns (missing from new): {old_cols}
New schema columns (not in old): {new_cols}

Identify columns that appear RENAMED (disappeared from old, similar one appeared in new).
Respond ONLY with valid JSON:
{{"renamed": [{{"old_name": "col_a", "new_name": "col_b"}}]}}
If none: {{"renamed": []}}
No explanation. No markdown. Only JSON.
"""


def _norm_type(t: str) -> str:
    t = str(t).lower()
    if "int" in t:   return "INTEGER"
    if "float" in t: return "FLOAT"
    if "object" in t or "str" in t: return "STRING"
    if "bool" in t: return "BOOLEAN"
    return t.upper()


def _detect_semantic_type(col_name: str, values: list) -> str:
    """Layer 3: Heuristic-based Smart Datatype Detection"""
    import re
    import pandas as pd
    
    col_lower = col_name.lower()
    if any(k in col_lower for k in ['date', 'time', 'at', 'timestamp']):
        return "TIMESTAMP"
    if any(k in col_lower for k in ['email']):
        return "EMAIL"
    if any(k in col_lower for k in ['phone', 'tel']):
        return "PHONE"
    
    # Try parsing sample values to determine if it's actually numeric or timestamp
    if not values:
        return "STRING"
        
    str_vals = [str(v) for v in values if pd.notna(v) and str(v).strip() != ""]
    if not str_vals:
        return "STRING"
        
    try:
        pd.to_datetime(str_vals, format="%Y-%m-%d %H:%M:%S")
        return "TIMESTAMP"
    except (ValueError, TypeError):
        pass
        
    try:
        pd.to_datetime(str_vals)
        return "TIMESTAMP"
    except (ValueError, TypeError):
        pass
    
    if all(re.match(r"^[0-9]+$", v) for v in str_vals):
        return "INTEGER"
        
    if all(re.match(r"^[0-9.]+$", v) for v in str_vals):
        return "FLOAT"
        
    return "STRING"


def run(state: AgentState) -> AgentState:
    state["current_node"] = "schema_drift"
    dataset  = state.get("dataset_name", PipelineConfig.ACTIVE_DATASET)
    run_id   = str(uuid.uuid4())[:8]
    incoming = state.get("schema", {})
    sample_rows = state.get("sample_rows", [])
    events   = []

    logger.info(f"SCHEMA_DRIFT | Starting Local ML Mode | dataset={dataset} | run_id={run_id}")

    # Dynamically load the previously known schema for ANY dataset (no hardcoding)
    import os, json
    schema_dir = "metadata/schemas"
    os.makedirs(schema_dir, exist_ok=True)
    schema_file = f"{schema_dir}/{dataset}_schema.json"
    
    expected = {}
    if os.path.exists(schema_file):
        try:
            with open(schema_file, "r") as f:
                expected = json.load(f)
        except Exception:
            pass

    # If this is the first time seeing this dataset, save it as the new baseline and skip drift
    if not expected:
        logger.info(f"SCHEMA_DRIFT | First time processing '{dataset}'. Saving as new baseline schema.")
        with open(schema_file, "w") as f:
            json.dump(incoming, f, indent=2)
            
        state["schema_drift_events"] = []
        state["schema_drift_run_id"] = run_id
        state["node_status"]["schema_drift"] = "pass"
        return state

    old_cols = set(expected.keys())
    new_cols = set(incoming.keys())
    now      = datetime.utcnow().isoformat()
    
    removed = list(old_cols - new_cols)
    added = list(new_cols - old_cols)
    
    renamed_map = {}
    
    # Layer 2: Semantic Rename Detection
    if removed and added:
        try:
            from sentence_transformers import SentenceTransformer
            from sentence_transformers.util import cos_sim
            
            model = SentenceTransformer('all-MiniLM-L6-v2')
            old_emb = model.encode(removed)
            new_emb = model.encode(added)
            sims = cos_sim(old_emb, new_emb)
            
            matched_old = set()
            matched_new = set()
            
            for i, old_col in enumerate(removed):
                for j, new_col in enumerate(added):
                    if sims[i][j].item() > 0.65:
                        renamed_map[old_col] = new_col
                        matched_old.add(old_col)
                        matched_new.add(new_col)
                        logger.warning(f"SCHEMA_DRIFT | RENAMED_COLUMN (ML) | {old_col} -> {new_col} (Sim: {sims[i][j].item():.2f})")
                        events.append({
                            "run_id": run_id, "dataset": dataset, 
                            "drift_type": "RENAMED_COLUMN",
                            "column_name": f"{old_col} \u2192 {new_col}",
                            "expected_type": _norm_type(expected[old_col]),
                            "actual_type": _norm_type(incoming[new_col]),
                            "type": _norm_type(incoming[new_col]),
                            "severity": "HIGH", 
                            "description": f"Column {old_col} was semantically renamed to {new_col}. Update downstream SQL transformations.",
                            "detected_at": now
                        })
            
            # ── Fallback to LLM for anything the ML model missed ──
            unmatched_removed = [c for c in removed if c not in matched_old]
            unmatched_added = [c for c in added if c not in matched_new]
            
            if unmatched_removed and unmatched_added:
                old_cols_formatted = [f"{c} ({_norm_type(expected[c])})" for c in unmatched_removed]
                new_cols_formatted = [f"{c} ({_norm_type(incoming[c])})" for c in unmatched_added]
                
                prompt = RENAME_PROMPT.format(
                    old_cols=", ".join(old_cols_formatted),
                    new_cols=", ".join(new_cols_formatted)
                )
                
                res = llm_client.call(prompt, temperature=0.0)
                clean_res = res.strip()
                if clean_res.startswith("```json"): clean_res = clean_res[7:]
                if clean_res.startswith("```"): clean_res = clean_res[3:]
                if clean_res.endswith("```"): clean_res = clean_res[:-3]
                    
                res_data = json.loads(clean_res.strip())
                for rename in res_data.get("renamed", []):
                    old_col = rename.get("old_name")
                    new_col = rename.get("new_name")
                    if old_col in unmatched_removed and new_col in unmatched_added:
                        renamed_map[old_col] = new_col
                        logger.warning(f"SCHEMA_DRIFT | RENAMED_COLUMN (LLM Fallback) | {old_col} -> {new_col}")
                        events.append({
                            "run_id": run_id, "dataset": dataset, 
                            "drift_type": "RENAMED_COLUMN",
                            "column_name": f"{old_col} \u2192 {new_col}",
                            "expected_type": _norm_type(expected[old_col]),
                            "actual_type": _norm_type(incoming[new_col]),
                            "type": _norm_type(incoming[new_col]),
                            "severity": "HIGH", 
                            "description": f"Column {old_col} was semantically renamed to {new_col}. Update downstream SQL transformations.",
                            "detected_at": now
                        })
        except Exception as e:
            logger.error(f"SCHEMA_DRIFT | Rename Detection Error: {e}")

    # Remove the renamed columns from added/removed lists so they don't double trigger
    for old_col, new_col in renamed_map.items():
        if old_col in removed: removed.remove(old_col)
        if new_col in added: added.remove(new_col)

    # Layer 1 & 4: Deterministic Diff & Template Explanations
    for col in removed:
        events.append({
            "run_id": run_id, "dataset": dataset, 
            "drift_type": "COLUMN_REMOVED",
            "column_name": col, 
            "expected_type": _norm_type(expected[col]),
            "actual_type": "—",
            "type": "—",
            "severity": "HIGH",
            "description": f"Column {col} removed. Dependent BI reports and dbt models may break.",
            "detected_at": now
        })
        logger.warning(f"SCHEMA_DRIFT | COLUMN_REMOVED | HIGH | {col}")

    for col in added:
        events.append({
            "run_id": run_id, "dataset": dataset, 
            "drift_type": "COLUMN_ADDED",
            "column_name": col, 
            "expected_type": "—",
            "actual_type": _norm_type(incoming[col]),
            "type": _norm_type(incoming[col]),
            "severity": "MEDIUM", 
            "description": f"New column {col} introduced. Verify downstream consumers can handle this field.",
            "detected_at": now
        })
        logger.info(f"SCHEMA_DRIFT | COLUMN_ADDED | MEDIUM | {col}")

    # Layer 3: Semantic Datatype Drift
    for col in (old_cols & new_cols):
        # Deterministic pandas-type drift
        if _norm_type(expected[col]) != _norm_type(incoming[col]):
            events.append({
                "run_id": run_id, "dataset": dataset, 
                "drift_type": "TYPE_CHANGED",
                "column_name": col, 
                "expected_type": _norm_type(expected[col]),
                "actual_type": _norm_type(incoming[col]),
                "type": _norm_type(incoming[col]),
                "severity": "HIGH", 
                "description": f"Column {col} changed from {_norm_type(expected[col])} to {_norm_type(incoming[col])}. Downstream operations may fail.",
                "detected_at": now
            })
            logger.warning(f"SCHEMA_DRIFT | TYPE_CHANGED | HIGH | {col}")
        else:
            # Check Semantic type if Pandas just says "STRING" (which is common for everything)
            if _norm_type(incoming[col]) == "STRING":
                vals = [r.get(col) for r in sample_rows]
                semantic = _detect_semantic_type(col, vals)
                if semantic != "STRING" and semantic != _norm_type(expected[col]):
                    events.append({
                        "run_id": run_id, "dataset": dataset, 
                        "drift_type": "SEMANTIC_TYPE_CHANGED",
                        "column_name": col, 
                        "expected_type": _norm_type(expected[col]),
                        "actual_type": semantic,
                        "type": semantic,
                        "severity": "MEDIUM", 
                        "description": f"Column {col} is a STRING in Pandas, but semantically looks like a {semantic}. Proceed with caution.",
                        "detected_at": now
                    })
                    logger.warning(f"SCHEMA_DRIFT | SEMANTIC_TYPE_CHANGED | MEDIUM | {col}")

    if events:
        try:
            mcp_tool.call("snowflake_append_json", {
                "table": PipelineConfig.DRIFT_LOG_TABLE,
                "record": {"run_id": run_id, "dataset": dataset, "events": events}
            })
        except Exception:
            pass
            
    state["schema_drift_events"] = events
    state["schema_drift_run_id"] = run_id
    state["node_status"]["schema_drift"] = "pass" if not any(e.get("severity") == "HIGH" for e in events) else "fail"
    return state
