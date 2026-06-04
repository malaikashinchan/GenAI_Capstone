"""Page 7 — Snowflake Data Explorer"""
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Data Explorer", layout="wide")
import streamlit as st
if "username" not in st.session_state:
    st.warning("Please log in on the home page.")
    st.stop()
username = st.session_state["username"]
active_prof = st.session_state.get("active_profile", "Default")
active_prof_key = f"{username}_{active_prof}"

# ── Styles ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap');
*, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: #0b0b14; color: #e2e8f0; }

/* Metadata stat cards */
.meta-row  { display: flex; gap: 12px; margin: 16px 0 20px; flex-wrap: wrap; }
.meta-card {
  flex: 1; min-width: 160px;
  background: rgba(20,20,40,.75);
  border: 1px solid rgba(99,102,241,.15);
  border-radius: 12px;
  padding: 14px 18px;
}
.meta-label {
  font-size: .72rem;
  text-transform: uppercase;
  letter-spacing: 1.4px;
  color: #6366f1;
  font-weight: 700;
  margin-bottom: 6px;
}
.meta-value {
  font-size: 1.1rem;
  font-weight: 800;
  color: #e2e8f0;
  font-family: 'JetBrains Mono', monospace !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta-value.green  { color: #34d399; }
.meta-value.indigo { color: #818cf8; }
.meta-value.amber  { color: #fbbf24; }

/* Section heading */
.sec-title {
  font-size: 1.0rem;
  font-weight: 800;
  color: #e2e8f0;
  margin: 18px 0 6px;
}

/* Download button */
[data-testid="stDownloadButton"] button {
  background: rgba(99,102,241,.12) !important;
  border: 1px solid rgba(99,102,241,.25) !important;
  color: #818cf8 !important;
  font-weight: 700 !important;
  font-size: .82rem !important;
  border-radius: 8px !important;
}

/* Table refinement */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* Label overrides */
label { font-size: .85rem !important; font-weight: 600 !important; color: #94a3b8 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("# Data Explorer")
st.caption("Browse raw, clean, masked, and gold tables from Snowflake OR Local CSVs")

@st.cache_resource(ttl=30)
def get_sf():
    try:
        import snowflake.connector
        from config.settings import SnowflakeConfig
        return snowflake.connector.connect(
            account=SnowflakeConfig.ACCOUNT, user=SnowflakeConfig.USER,
            password=SnowflakeConfig.PASSWORD, warehouse=SnowflakeConfig.WAREHOUSE,
            database=SnowflakeConfig.DATABASE, schema=SnowflakeConfig.SCHEMA,
            role=SnowflakeConfig.ROLE)
    except:
        return None

def qry(sql):
    conn = get_sf()
    if not conn:
        return pd.DataFrame()
    try:
        c = conn.cursor()
        c.execute(sql)
        cols = [d[0] for d in c.description]
        data = c.fetchall()
        c.close()
        return pd.DataFrame(data, columns=cols)
    except:
        return pd.DataFrame()

import json
from pathlib import Path
from config.settings import PipelineConfig

def get_available_tables():
    dataset_names = set(["customers"])
    hist_path = Path(f"metadata/batch_history_{active_prof_key}.json")
    if hist_path.exists():
        try:
            with open(hist_path) as f:
                for b in json.load(f):
                    if "dataset" in b:
                        dataset_names.add(b["dataset"].upper())
        except: pass
    
    _tables = {}
    for dsu in dataset_names:
        dataset_lower = dsu.lower()
        is_custom = dataset_lower not in ["customers", "orders", "payments", "products"]
        raw_table_name = f"RAW_{dsu}" if is_custom else f"RAW_OLIST_{dsu}"
        
        _tables[f"🟤 {raw_table_name}"] = raw_table_name
        _tables[f"⚪ SILVER_{dsu}_CLEAN"] = f"SILVER_{dsu}_CLEAN"
        _tables[f"🔒 SILVER_{dsu}_MASKED"] = f"SILVER_{dsu}_MASKED"
        _tables[f"🥇 GOLD_{dsu}_KPIS"] = f"GOLD_{dsu}_KPIS"
    _tables["📋 PIPELINE_AUDIT_LOG"] = "PIPELINE_AUDIT_LOG"
    return dict(sorted(_tables.items()))

tables = get_available_tables()

col_sel, col_btn = st.columns([4, 1])
with col_sel:
    selected = st.selectbox("Select table:", list(tables.keys()))
table = tables[selected]

limit = st.slider("Row limit", 10, 500, 100, 10)

with col_btn:
    st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", type="primary", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ── Query & Display ─────────────────────────────────────────────
with st.spinner(f"Loading {table}..."):
    if PipelineConfig.USE_LOCAL_CSV:
        # Load from Local CSV

        path = None
        if table.startswith("RAW_OLIST_"):
            csv_map = {
                "RAW_OLIST_CUSTOMERS": f"{PipelineConfig.DATA_DIR}/olist_customers_dataset.csv",
                "RAW_OLIST_ORDERS":    f"{PipelineConfig.DATA_DIR}/olist_orders_dataset.csv",
                "RAW_OLIST_PAYMENTS":  f"{PipelineConfig.DATA_DIR}/olist_order_payments_dataset.csv",
                "RAW_OLIST_PRODUCTS":  f"{PipelineConfig.DATA_DIR}/olist_products_dataset.csv",
            }
            path = csv_map.get(table)
        elif table.startswith("RAW_"):
            custom_dataset = table.replace("RAW_", "").lower()
            path = f"data/uploads/{custom_dataset}.csv"
        df = pd.DataFrame()
        if path and Path(path).exists():
            df = pd.read_csv(path).head(limit)
        else:
            for layer in ["silver", "bronze", "gold", "audit"]:
                p = f"{PipelineConfig.OUTPUTS_DIR}/{layer}/{table}.csv"
                if Path(p).exists():
                    df = pd.read_csv(p).head(limit)
                    break
    else:
        # Query Snowflake
        df = qry(f"SELECT * FROM {table} LIMIT {limit}")

if not df.empty:
    # Styled metadata cards instead of st.metric()
    tbl_display = table if len(table) <= 22 else table[:22] + "…"
    st.markdown(f"""
    <div class="meta-row">
      <div class="meta-card">
        <div class="meta-label">Rows Loaded</div>
        <div class="meta-value green">{len(df):,}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">Columns</div>
        <div class="meta-value indigo">{len(df.columns)}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">Table</div>
        <div class="meta-value amber" title="{table}">{tbl_display}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Schema info — session-state toggle (avoids _arrow_right_ expander bug)
    if "_de_show_schema" not in st.session_state:
        st.session_state["_de_show_schema"] = False

    schema_btn_lbl = ("▲  Hide Schema Info" if st.session_state["_de_show_schema"] else "▼  Show Schema Info")
    if st.button(schema_btn_lbl, key="btn_schema_toggle"):
        st.session_state["_de_show_schema"] = not st.session_state["_de_show_schema"]
        st.rerun()

    if st.session_state["_de_show_schema"]:
        schema_rows = [
            {
                "Column": col,
                "Type": str(df[col].dtype),
                "Non-Null": int(df[col].notna().sum()),
                "Null %": f"{df[col].isna().mean()*100:.1f}%"
            }
            for col in df.columns
        ]
        st.dataframe(pd.DataFrame(schema_rows), use_container_width=True, hide_index=True)


    # Data table
    st.markdown('<div class="sec-title"> Data Preview</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, height=420)

    # Download
    csv = df.to_csv(index=False)
    st.download_button(f"📥 Download {table}.csv", csv, f"{table}.csv", "text/csv")
else:
    st.markdown(f"""
    <div style="background:rgba(251,113,133,.07);border:1px solid rgba(251,113,133,.2);
                border-radius:12px;padding:20px;text-align:center;margin-top:16px">
      <div style="font-size:1.5rem;margin-bottom:8px">⚠️</div>
      <div style="color:#fb7185;font-weight:700">Table Empty or Not Found</div>
      <div style="color:#94a3b8;font-size:.85rem;margin-top:4px">
        <code>{table}</code> returned no rows. Run the pipeline first or check your Snowflake connection.
      </div>
    </div>
    """, unsafe_allow_html=True)
