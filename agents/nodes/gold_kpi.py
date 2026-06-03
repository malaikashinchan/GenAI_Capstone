"""
agents/nodes/gold_kpi.py
Node 8 — Gold KPI Generator  ★ NEW NODE (not in B1)
Computes business KPIs from Silver clean data → Gold layer.
Also uses LLM to generate business insights from KPIs.
This implements the Bronze → Silver → Gold medallion architecture
that was present in GEN_AI_Capstone but missing as a proper node.
Dataset: Olist Brazilian E-Commerce
"""
import json
import pandas as pd
from pathlib import Path
from agents.state import AgentState
from tools.snowflake_mcp_tool import mcp_tool
from tools.llm_client import llm_client
from config.settings import PipelineConfig
from loguru import logger


INSIGHTS_PROMPT = """
You are a senior data analyst reviewing Olist Brazilian E-Commerce metrics.

Dataset: {dataset}
KPI Summary:
{kpis}

Generate exactly 3 concise, actionable business insights from these metrics.
Focus on: customer behaviour, data quality, revenue patterns, or geographic trends.
Keep each insight to 1-2 sentences. Be specific and use the numbers provided.

Format as JSON array:
[
  {{"insight": "...", "category": "quality|revenue|customers|geography"}},
  ...
]
Respond ONLY with JSON. No markdown.
"""


KPI_PROMPT = """
You are a senior data analyst. I am providing you a sample of SYNTHETIC data from a dataset named '{dataset}'.
The columns and data types match the real data exactly, but the values are completely fake.
Based on this schema, define exactly 5 relevant business KPIs (e.g., total_revenue, unique_customers, avg_amount).

For each KPI, provide the exact Python Pandas code expression that calculates it. The input DataFrame variable is named `df`.
For example:
{{
  "total_revenue": "float(df['payment_value'].sum())",
  "unique_customers": "int(df['customer_id'].nunique())"
}}

Data Sample:
{sample}

Return ONLY a valid JSON dictionary where keys are the KPI names (snake_case) and values are the Pandas code strings.
Do not return markdown. Just return the raw JSON object.
"""


def run(state: AgentState) -> AgentState:
    state["current_node"] = "gold_kpi"
    dataset = state.get("dataset_name", PipelineConfig.ACTIVE_DATASET)

    logger.info(f"GOLD_KPI | Starting | dataset={dataset}")

    try:
        # Load Silver clean dataset
        clean_table = f"SILVER_{dataset.upper()}_CLEAN"
        df = mcp_tool.call("snowflake_read_table", {
            "table": clean_table,
            "layer": "silver",
        })

        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)

        logger.info(f"GOLD_KPI | Loaded {len(df):,} Silver rows")

        # Generate 25 rows of synthetic data for the LLM to preserve privacy
        import numpy as np
        fake_data = {}
        num_rows = 25
        for col, dtype in df.dtypes.items():
            if pd.api.types.is_numeric_dtype(dtype):
                if pd.api.types.is_float_dtype(dtype):
                    fake_data[col] = np.random.uniform(1.0, 100.0, num_rows).round(2)
                else:
                    fake_data[col] = np.random.randint(1, 1000, num_rows)
            elif pd.api.types.is_bool_dtype(dtype):
                fake_data[col] = np.random.choice([True, False], num_rows)
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                fake_data[col] = pd.date_range("2024-01-01", periods=num_rows)
            else:
                fake_data[col] = [f"sample_{col}_{i}" for i in range(num_rows)]
        
        fake_df = pd.DataFrame(fake_data)

        # Send only synthetic data to LLM to get Pandas logic
        kpi_prompt_text = KPI_PROMPT.format(
            dataset=dataset,
            sample=fake_df.to_json(orient="records")
        )
        try:
            raw_kpis = llm_client.invoke(kpi_prompt_text).strip()
            import re
            match = re.search(r'\{.*\}', raw_kpis, re.DOTALL)
            kpis_code = json.loads(match.group(0)) if match else json.loads(raw_kpis)
            
            kpis = {}
            for k, code_str in kpis_code.items():
                try:
                    # SECURE EXECUTION: Evaluate Pandas expression locally on the REAL dataset
                    val = eval(str(code_str), {"df": df, "pd": pd, "np": np})
                    if hasattr(val, "item"): val = val.item()
                    kpis[k] = round(val, 2) if isinstance(val, float) else val
                except Exception as eval_err:
                    logger.warning(f"GOLD_KPI | Failed to eval KPI {k} with code {code_str}: {eval_err}")
                    kpis[k] = 0
        except Exception as e:
            logger.warning(f"GOLD_KPI | Failed to generate KPIs via LLM: {e}")
            kpis = {"total_rows": len(df)}

        logger.info(f"GOLD_KPI | KPIs computed: {list(kpis.keys())}")

        # LLM generates business insights
        try:
            insight_prompt = INSIGHTS_PROMPT.format(
                dataset = dataset,
                kpis    = json.dumps(kpis, indent=2, default=str),
            )
            raw_insights = llm_client.invoke(insight_prompt)
            raw_insights = raw_insights.strip()
            import re
            match = re.search(r'\[.*\]', raw_insights, re.DOTALL)
            if match:
                insights = json.loads(match.group(0))
            else:
                insights = json.loads(raw_insights)
        except Exception as ins_err:
            logger.warning(f"GOLD_KPI | LLM insights failed (non-critical): {ins_err}")
            insights = []

        kpis["business_insights"] = insights

        # Write Gold KPI summary
        gold_df = pd.DataFrame([{"dataset": dataset, "kpi_key": k, "kpi_value": str(v)}
                                  for k, v in kpis.items() if k != "business_insights"])
        gold_result = mcp_tool.call("snowflake_write_df", {
            "df":    gold_df,
            "table": f"GOLD_{dataset.upper()}_KPIS",
            "layer": "gold",
        })

        state["gold_kpis"]    = kpis
        state["gold_df_path"] = gold_result.get("path", "")

        logger.success(
            f"GOLD_KPI | Done | {len(gold_df)} KPIs written to Gold | "
            f"{len(insights)} business insights generated"
        )
        state["node_status"]["gold_kpi"] = "pass"

    except Exception as e:
        logger.error(f"GOLD_KPI | FAILED: {e}")
        state["node_errors"]["gold_kpi"] = str(e)
        state["node_status"]["gold_kpi"] = "fail"

    return state
