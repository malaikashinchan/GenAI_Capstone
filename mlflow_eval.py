import json
import mlflow
from sklearn.metrics import accuracy_score, f1_score
from agents.nodes.pii_detector import detect_pii_local, get_analyzer
from agents.nodes.schema_drift import _detect_semantic_type

def run_mlflow_evaluation():
    # 1. Setup MLflow tracking
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Olist_Agent_Evaluation")

    print("\n🚀 Starting MLflow Evaluation Run...\n")

    # 2. Load Ground Truth Data
    with open("data/eval_ground_truth.json", "r") as f:
        ground_truth = json.load(f)

    pii_tests = ground_truth["pii_tests"]
    schema_tests = ground_truth["schema_tests"]

    # 3. Evaluate PII Detector (Presidio + Regex)
    print("Evaluating PII Detector...")
    analyzer = get_analyzer()
    
    y_true_pii = []
    y_pred_pii = []

    for test in pii_tests:
        col = test["column"]
        sample = test["sample"]
        expected = test["expected_pii"]
        
        pii_level = detect_pii_local(col, sample, analyzer)
        
        # Binary classification: PII (True) if level is HIGH or MEDIUM, else False
        is_pii = pii_level in ["HIGH", "MEDIUM"]
        
        y_true_pii.append(1 if expected else 0)
        y_pred_pii.append(1 if is_pii else 0)

    pii_f1 = f1_score(y_true_pii, y_pred_pii)
    pii_acc = accuracy_score(y_true_pii, y_pred_pii)
    print(f"✅ PII F1 Score: {pii_f1:.4f}")
    print(f"✅ PII Accuracy: {pii_acc:.4f}\n")

    # 4. Evaluate Schema Drift (Semantic Engine)
    print("Evaluating Schema Drift Semantic Engine...")
    y_true_schema = []
    y_pred_schema = []

    for test in schema_tests:
        col = test["column"]
        sample = test["sample"]
        expected = test["expected_type"]
        
        detected_type = _detect_semantic_type(col, sample)
        
        y_true_schema.append(expected)
        y_pred_schema.append(detected_type)

    schema_acc = accuracy_score(y_true_schema, y_pred_schema)
    print(f"✅ Schema Semantic Accuracy: {schema_acc:.4f}\n")

    # 5. Calculate Empirical Operational Metrics from History
    print("Evaluating Historical Pipeline Telemetry...")
    import os
    
    mttr = 0.0
    sh_success_rate = 0.0
    rec_success_rate = 0.0
    total_runs = 0
    
    if os.path.exists("metadata/batch_history.json"):
        with open("metadata/batch_history.json", "r") as f:
            try:
                hist_data = json.load(f)
                total_runs = len(hist_data)
                healed_runs = [r for r in hist_data if r.get('heals', 0) > 0]
                healed_success = [r for r in healed_runs if r.get('status') == 'SUCCESS']
                
                if healed_runs:
                    mttr = sum(r.get('duration_s', 0) for r in healed_success) / len(healed_success) if healed_success else 0
                    sh_success_rate = (len(healed_success) / len(healed_runs)) * 100
                    
                if total_runs > 0:
                    permanent_failures = total_runs - len([r for r in hist_data if r.get('status') == 'SUCCESS'])
                    rec_success_rate = 100 - ((permanent_failures / total_runs) * 100)
            except Exception:
                pass
                
    print(f"✅ Self-Healing Success Rate: {sh_success_rate:.1f}%")
    print(f"✅ Recovery Success Rate: {rec_success_rate:.1f}%")
    print(f"✅ Mean Time To Recovery (MTTR): {mttr:.1f}s\n")

    # 6. Log everything to MLflow
    with mlflow.start_run(run_name="ground_truth_eval"):
        # Ground Truth Metrics
        mlflow.log_metric("pii_f1_score", pii_f1)
        mlflow.log_metric("pii_accuracy", pii_acc)
        mlflow.log_metric("schema_semantic_accuracy", schema_acc)
        
        # Operational Metrics
        mlflow.log_metric("self_healing_success_rate", sh_success_rate)
        mlflow.log_metric("recovery_success_rate", rec_success_rate)
        mlflow.log_metric("mean_time_to_recovery_sec", mttr)
        
        # Log parameters/sizes
        mlflow.log_param("num_pii_tests", len(pii_tests))
        mlflow.log_param("num_schema_tests", len(schema_tests))
        mlflow.log_param("total_historical_runs", total_runs)

    print(f"🎉 Evaluation Complete! Metrics logged successfully to MLflow.")
    print("Run `mlflow ui` in your terminal and visit http://localhost:5000 to view the results.")

if __name__ == "__main__":
    run_mlflow_evaluation()
