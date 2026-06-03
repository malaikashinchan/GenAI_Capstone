"""
config/settings.py
Centralised settings loaded from environment variables.
Supports Snowflake (production) and local CSV (dev) modes.
Dataset: Olist Brazilian E-Commerce
"""
import os
import json
from dotenv import load_dotenv

if os.path.exists(".env"):
    load_dotenv(".env")
elif os.path.exists(".env.example"):
    load_dotenv(".env.example")
else:
    load_dotenv()

# Dynamic Profile Injector
profile_config = {}
try:
    active_profile_path = "metadata/active_profile.json"
    if os.path.exists(active_profile_path):
        with open(active_profile_path) as f:
            ap = json.load(f)
            prof_name = ap.get("active_profile")
            prof_file = f"profiles/{prof_name}.json"
            if prof_name and os.path.exists(prof_file):
                with open(prof_file) as pf:
                    profile_config = json.load(pf)
except Exception:
    pass


def get_cfg(key, default=None):
    return profile_config.get(key, os.getenv(key, default))


class SnowflakeConfig:
    ACCOUNT    = get_cfg("SNOWFLAKE_ACCOUNT")
    USER       = get_cfg("SNOWFLAKE_USER")
    PASSWORD   = get_cfg("SNOWFLAKE_PASSWORD")
    WAREHOUSE  = get_cfg("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
    DATABASE   = get_cfg("SNOWFLAKE_DATABASE",  "OLIST_DB")
    SCHEMA     = get_cfg("SNOWFLAKE_SCHEMA",    "RAW")
    ROLE       = get_cfg("SNOWFLAKE_ROLE",       "SYSADMIN")


class LLMConfig:
    API_KEY    = get_cfg("ANTHROPIC_API_KEY") or get_cfg("OPENAI_API_KEY") or get_cfg("GROQ_API_KEY")
    MODEL      = get_cfg("LLM_MODEL",    "claude-sonnet-4-5")
    PROVIDER   = get_cfg("LLM_PROVIDER", "anthropic")   # 'anthropic' | 'openai' | 'groq' | 'ollama'


class PipelineConfig:
    MAX_RETRIES           = int(os.getenv("MAX_RETRIES_PER_NODE", 3))
    LOG_LEVEL             = os.getenv("LOG_LEVEL", "INFO")

    # Raw table names (Snowflake) / CSV identifiers (local)
    RAW_TABLE_CUSTOMERS   = os.getenv("RAW_TABLE_CUSTOMERS", "RAW_OLIST_CUSTOMERS")
    RAW_TABLE_ORDERS      = os.getenv("RAW_TABLE_ORDERS",    "RAW_OLIST_ORDERS")
    RAW_TABLE_PAYMENTS    = os.getenv("RAW_TABLE_PAYMENTS",  "RAW_OLIST_PAYMENTS")
    RAW_TABLE_PRODUCTS    = os.getenv("RAW_TABLE_PRODUCTS",  "RAW_OLIST_PRODUCTS")

    # Which dataset to run (customers | orders | payments | products)
    ACTIVE_DATASET        = os.getenv("ACTIVE_DATASET", "customers")

    # Output table names
    CLEAN_TABLE           = os.getenv("CLEAN_TABLE",      "SILVER_OLIST_CLEAN")
    QUARANTINE_TABLE      = os.getenv("QUARANTINE_TABLE", "BRONZE_QUARANTINE")
    MASKED_TABLE          = os.getenv("MASKED_TABLE",     "SILVER_OLIST_MASKED")
    GOLD_TABLE            = os.getenv("GOLD_TABLE",       "GOLD_OLIST_KPIS")
    LINEAGE_TABLE         = os.getenv("LINEAGE_TABLE",    "PIPELINE_LINEAGE")
    AUDIT_TABLE           = os.getenv("AUDIT_TABLE",      "PIPELINE_AUDIT_LOG")
    DRIFT_LOG_TABLE       = os.getenv("DRIFT_LOG_TABLE",  "SCHEMA_DRIFT_LOG")

    # Paths
    DATA_DIR              = os.getenv("DATA_DIR",     "data")
    OUTPUTS_DIR           = os.getenv("OUTPUTS_DIR",  "outputs")

    # Set to "true" to run without Snowflake (uses local CSVs)
    USE_LOCAL_CSV         = str(get_cfg("USE_LOCAL_CSV", os.getenv("USE_LOCAL_CSV", "true"))).lower() == "true"
