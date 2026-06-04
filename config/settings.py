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

def get_active_profile_name():
    # 1. Background process explicit environment var
    prof = os.getenv("ACTIVE_PROFILE_NAME")
    if prof: return prof
    
    # 2. Streamlit UI session state
    try:
        import streamlit as st
        # This will error if not running inside Streamlit script context
        if "username" in st.session_state and "active_profile" in st.session_state:
            return f"{st.session_state['username']}_{st.session_state['active_profile']}"
    except:
        pass
    return None

def get_cfg(key, default=None):
    prof_name = get_active_profile_name()
    if prof_name:
        prof_file = f"profiles/{prof_name}.json"
        if os.path.exists(prof_file):
            with open(prof_file) as f:
                return json.load(f).get(key, os.getenv(key, default))
    return os.getenv(key, default)

class _SnowflakeConfig:
    @property
    def ACCOUNT(self): return get_cfg("SNOWFLAKE_ACCOUNT")
    @property
    def USER(self): return get_cfg("SNOWFLAKE_USER")
    @property
    def PASSWORD(self): return get_cfg("SNOWFLAKE_PASSWORD")
    @property
    def WAREHOUSE(self): return get_cfg("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
    @property
    def DATABASE(self): return get_cfg("SNOWFLAKE_DATABASE", "MY_DB")
    @property
    def SCHEMA(self): return get_cfg("SNOWFLAKE_SCHEMA", "PUBLIC")
    @property
    def ROLE(self): return get_cfg("SNOWFLAKE_ROLE", "SYSADMIN")
SnowflakeConfig = _SnowflakeConfig()

class _LLMConfig:
    @property
    def API_KEY(self): return get_cfg("ANTHROPIC_API_KEY") or get_cfg("OPENAI_API_KEY") or get_cfg("GROQ_API_KEY")
    @property
    def MODEL(self): return get_cfg("LLM_MODEL", "claude-sonnet-4-5")
    @property
    def PROVIDER(self): return get_cfg("LLM_PROVIDER", "anthropic")
LLMConfig = _LLMConfig()

class _PipelineConfig:
    @property
    def MAX_RETRIES(self): return int(os.getenv("MAX_RETRIES_PER_NODE", 3))
    @property
    def LOG_LEVEL(self): return os.getenv("LOG_LEVEL", "INFO")
    @property
    def RAW_TABLE_CUSTOMERS(self): return os.getenv("RAW_TABLE_CUSTOMERS", "RAW_OLIST_CUSTOMERS")
    @property
    def RAW_TABLE_ORDERS(self): return os.getenv("RAW_TABLE_ORDERS", "RAW_OLIST_ORDERS")
    @property
    def RAW_TABLE_PAYMENTS(self): return os.getenv("RAW_TABLE_PAYMENTS", "RAW_OLIST_PAYMENTS")
    @property
    def RAW_TABLE_PRODUCTS(self): return os.getenv("RAW_TABLE_PRODUCTS", "RAW_OLIST_PRODUCTS")
    @property
    def ACTIVE_DATASET(self): return os.getenv("ACTIVE_DATASET", "customers")
    @property
    def CLEAN_TABLE(self): return os.getenv("CLEAN_TABLE", "SILVER_OLIST_CLEAN")
    @property
    def QUARANTINE_TABLE(self): return os.getenv("QUARANTINE_TABLE", "BRONZE_QUARANTINE")
    @property
    def MASKED_TABLE(self): return os.getenv("MASKED_TABLE", "SILVER_OLIST_MASKED")
    @property
    def GOLD_TABLE(self): return os.getenv("GOLD_TABLE", "GOLD_OLIST_KPIS")
    @property
    def LINEAGE_TABLE(self): return os.getenv("LINEAGE_TABLE", "PIPELINE_LINEAGE")
    @property
    def AUDIT_TABLE(self): return os.getenv("AUDIT_TABLE", "PIPELINE_AUDIT_LOG")
    @property
    def DRIFT_LOG_TABLE(self): return os.getenv("DRIFT_LOG_TABLE", "SCHEMA_DRIFT_LOG")
    @property
    def DATA_DIR(self): return os.getenv("DATA_DIR", "data")
    @property
    def OUTPUTS_DIR(self): return os.getenv("OUTPUTS_DIR", "outputs")
    @property
    def USE_LOCAL_CSV(self): return str(get_cfg("USE_LOCAL_CSV", os.getenv("USE_LOCAL_CSV", "true"))).lower() == "true"
PipelineConfig = _PipelineConfig()
