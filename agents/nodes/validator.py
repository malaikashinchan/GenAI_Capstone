"""
agents/nodes/validator.py
Node 5 — Validator
Runs LLM-generated GE rules against the dataset.
Uses Great Expectations when available; falls back to pandas-native checks.
Pass → Transform. Fail → Heal Agent.
Dataset: Olist Brazilian E-Commerce
"""
import pandas as pd
from agents.state import AgentState
from tools.snowflake_mcp_tool import mcp_tool
from config.settings import PipelineConfig
from loguru import logger

try:
    import great_expectations as ge
    HAS_GE = True
except ImportError:
    HAS_GE = False

DATASET_TABLE_MAP = {
    "customers": PipelineConfig.RAW_TABLE_CUSTOMERS,
    "orders":    PipelineConfig.RAW_TABLE_ORDERS,
    "payments":  PipelineConfig.RAW_TABLE_PAYMENTS,
    "products":  PipelineConfig.RAW_TABLE_PRODUCTS,
}


def _run_ge_validation(df: pd.DataFrame, rules: list) -> list:
    """Run validation using real Great Expectations PandasDataset."""
    failed = []
    if not HAS_GE:
        logger.warning("VALIDATOR | great-expectations package is not available. Using pandas native fallback.")
        return None

    try:
        logger.info("VALIDATOR | Running actual Great Expectations validation...")
        ge_df = ge.from_pandas(df)

        for rule in rules:
            exp_type = rule.get("expectation_type", "")
            col      = rule.get("column", "")
            kwargs   = rule.get("kwargs", {})

            if col not in df.columns:
                failed.append({
                    "expectation_type": exp_type,
                    "column": col,
                    "issue": f"Column '{col}' not found in dataset",
                    "failed_count": 0,
                })
                continue

            if hasattr(ge_df, exp_type):
                method = getattr(ge_df, exp_type)
                res = method(col, **kwargs)
                if not res.success:
                    failed_count = res.result.get("unexpected_count", 1)
                    unexpected_values = res.result.get("unexpected_values", [])
                    failed.append({
                        "expectation_type": exp_type,
                        "column": col,
                        "issue": f"GE validation failed: {failed_count} invalid values found. Sample: {unexpected_values[:5]}",
                        "failed_count": int(failed_count),
                    })
            else:
                logger.warning(f"VALIDATOR | Expectation '{exp_type}' not supported by GE PandasDataset. Skipping.")

    except Exception as e:
        logger.error(f"VALIDATOR | Great Expectations validation failed: {e}. Falling back to pandas...")
        return None

    return failed


def _run_pandas_validation(df: pd.DataFrame, rules: list) -> list:
    """Run GE-style rules using pandas. Returns list of failed check dicts."""
    failed = []

    for rule in rules:
        exp_type = rule.get("expectation_type", "")
        col      = rule.get("column", "")
        kwargs   = rule.get("kwargs", {})

        try:
            if col not in df.columns:
                failed.append({
                    "expectation_type": exp_type,
                    "column": col,
                    "issue": f"Column '{col}' not found in dataset",
                    "failed_count": 0,
                })
                continue

            if exp_type == "expect_column_values_to_not_be_null":
                null_count = int(df[col].isnull().sum())
                if null_count > 0:
                    failed.append({
                        "expectation_type": exp_type,
                        "column": col,
                        "issue": f"{null_count} null values found",
                        "failed_count": null_count,
                    })

            elif exp_type == "expect_column_values_to_be_unique":
                dup_count = int(df[col].duplicated().sum())
                if dup_count > 0:
                    failed.append({
                        "expectation_type": exp_type,
                        "column": col,
                        "issue": f"{dup_count} duplicate values found",
                        "failed_count": dup_count,
                    })

            elif exp_type == "expect_column_values_to_be_in_set":
                value_set   = kwargs.get("value_set", [])
                non_null    = df[col].dropna()
                invalid     = non_null[~non_null.astype(str).isin([str(v) for v in value_set])]
                invalid_count = len(invalid)
                if invalid_count > 0:
                    sample_bad = invalid.unique()[:5].tolist()
                    failed.append({
                        "expectation_type": exp_type,
                        "column": col,
                        "issue": f"{invalid_count} values not in allowed set {value_set[:5]}. Sample bad: {sample_bad}",
                        "failed_count": invalid_count,
                    })

            elif exp_type == "expect_column_values_to_be_between":
                min_val = kwargs.get("min_value")
                max_val = kwargs.get("max_value")
                numeric = pd.to_numeric(df[col], errors="coerce")
                out_of_range = 0
                if min_val is not None:
                    out_of_range += int((numeric < min_val).sum())
                if max_val is not None:
                    out_of_range += int((numeric > max_val).sum())
                if out_of_range > 0:
                    failed.append({
                        "expectation_type": exp_type,
                        "column": col,
                        "issue": f"{out_of_range} values outside range [{min_val}, {max_val}]",
                        "failed_count": out_of_range,
                    })

            elif exp_type == "expect_column_values_to_match_regex":
                pattern     = kwargs.get("regex", kwargs.get("pattern", ".*"))
                non_null    = df[col].dropna().astype(str)
                no_match    = non_null[~non_null.str.match(pattern)]
                no_match_count = len(no_match)
                if no_match_count > 0:
                    failed.append({
                        "expectation_type": exp_type,
                        "column": col,
                        "issue": f"{no_match_count} values don't match regex '{pattern}'",
                        "failed_count": no_match_count,
                    })

        except Exception as rule_err:
            logger.warning(f"VALIDATOR | Rule check error for {exp_type}/{col}: {rule_err}")

    return failed


def run(state: AgentState) -> AgentState:
    state["current_node"] = "validator"
    dataset  = state.get("dataset_name", PipelineConfig.ACTIVE_DATASET)
    table    = DATASET_TABLE_MAP.get(dataset, PipelineConfig.RAW_TABLE_CUSTOMERS)
    ge_rules = state.get("ge_rules", [])

    logger.info(f"VALIDATOR | Starting | dataset={dataset} | rules={len(ge_rules)}")

    if not ge_rules:
        logger.error("VALIDATOR | No GE rules found in state — cannot validate")
        state["node_errors"]["validator"] = "No GE rules in state"
        state["node_status"]["validator"] = "fail"
        return state

    try:
        # Fetch data via MCP
        df = mcp_tool.call("snowflake_fetch_data", {"table": table})

        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)

        logger.info(f"VALIDATOR | Loaded {len(df)} rows for validation")

        # Run validation
        failed_checks = _run_ge_validation(df, ge_rules)
        if failed_checks is None:
            failed_checks = _run_pandas_validation(df, ge_rules)

        total_rows        = max(len(df), 1)
        total_issues      = sum(f.get("failed_count", 0) for f in failed_checks)
        # Check the worst single column instead of summing across all rules
        max_failure_rate  = max(
            (f.get("failed_count", 0) / total_rows for f in failed_checks),
            default=0.0
        )

        if failed_checks and max_failure_rate > 0.15:
            # ── SEVERE: >15% bad rows → trigger healing ──
            logger.warning(
                f"VALIDATOR | FAILED (SEVERE) | {len(failed_checks)} rule(s) failed | "
                f"worst column={max_failure_rate:.1%} of rows | total issues={total_issues:,}"
            )
            for f in failed_checks:
                logger.warning(f"  ✗ {f['column']} [{f['expectation_type']}]: {f['issue']}")
            state["failed_checks"]             = failed_checks
            state["validation_passed"]         = False
            state["node_status"]["validator"]  = "fail"
            state["node_errors"]["validator"]  = (
                f"{len(failed_checks)} GE checks failed | worst column: {max_failure_rate:.1%} rows "
                f"affected | Failed columns: {[f['column'] for f in failed_checks]}"
            )

        elif failed_checks:
            # ── MINOR: <15% of rows → pass with warnings, let quarantine handle it ──
            logger.warning(
                f"VALIDATOR | PASS-WITH-WARNINGS | {len(failed_checks)} minor rule(s) | "
                f"max single-column failure rate={max_failure_rate:.1%} (<15%) "
                f"— transform will quarantine affected rows"
            )
            for f in failed_checks:
                logger.info(f"  ⚠ {f['column']} [{f['expectation_type']}]: {f['issue']} (minor)")
            state["validation_passed"]         = False   # tells transform to quarantine
            state["failed_checks"]             = failed_checks
            state["node_status"]["validator"]  = "pass"

        else:
            logger.success(
                f"VALIDATOR | PASSED | All {len(ge_rules)} rules passed on {len(df):,} rows"
            )
            state["validation_passed"]       = True
            state["failed_checks"]           = []
            state["node_status"]["validator"] = "pass"

    except Exception as e:
        logger.error(f"VALIDATOR | FAILED: {e}")
        state["node_errors"]["validator"] = str(e)
        state["node_status"]["validator"] = "fail"

    return state
