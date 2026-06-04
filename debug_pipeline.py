import json
import traceback
from pipeline.graph import build_pipeline
from config.settings import PipelineConfig

def run_debug():
    pipeline = build_pipeline()
    initial = {
        "dataset_name": PipelineConfig.ACTIVE_DATASET,
        "raw_df_path": "",
        "row_count": 0,
        "sample_rows": [],
        "schema": {},
        "pii_map": {},
        "bronze_report": {},
        "node_status": {},
        "node_errors": {},
        "current_node": "profile",
        "retry_count": {},
        "give_up": False,
        "heal_log": [],
        "bronze_issues": [],
        "schema_drift_events": [],
        "ge_rules": [],
        "llm_retry_strict": False,
        "validation_passed": False,
        "failed_checks": [],
        "clean_row_count": 0,
        "quarantine_count": 0,
        "fix_sql": "",
        "clean_df_path": "",
        "quarantine_df_path": "",
        "masked_table": "",
        "masked_row_count": 0,
        "masked_df_path": "",
        "masking_log": [],
        "gold_kpis": {},
        "gold_df_path": "",
        "lineage_run_id": "",
        "audit_written": False,
        "audit_report": "",
    }
    
    final = pipeline.invoke(initial)
    print("\n--- FINAL ERRORS ---")
    print(json.dumps(final.get("node_errors", {}), indent=2))
    print("\n--- HEAL LOG ---")
    print(json.dumps(final.get("heal_log", []), indent=2))

if __name__ == "__main__":
    run_debug()
