import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Lineage", page_icon="🔗", layout="wide")
st.markdown("# 🔗 Data Lineage Visualization")
st.caption("Trace data flow from Bronze → Silver → Gold across pipeline nodes")

hist = json.load(open("metadata/batch_history.json")) if Path("metadata/batch_history.json").exists() else []
if not hist: st.info("No data yet."); st.stop()

opts = [f"Batch #{i+1} — {b['batch_id']} ({b['status']})" for i,b in enumerate(hist)]
idx = st.selectbox("Select batch:", range(len(opts)), format_func=lambda i: opts[i], index=len(opts)-1)
sel = hist[idx]

def render_mermaid(code: str):
    components.html(
        f"""
        <pre class="mermaid">
            {code}
        </pre>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
        </script>
        """,
        height=350,
    )

# ── Lineage Flow Diagram ───────────────────────────────────────
st.markdown("### 🗺️ Table-Level Lineage")
raw = sel.get("raw_rows",0); clean = sel.get("clean_rows",0); masked = sel.get("masked_rows",0)

dataset_up = sel.get("dataset", "customers").upper()
lineage_code = f"""
graph LR
    RAW["RAW_OLIST_{dataset_up}<br/>{raw} rows"] -->|Transform + Dedup| SILVER["SILVER_{dataset_up}_CLEAN<br/>{clean} rows"]
    SILVER -->|PII Masking| MASKED["SILVER_{dataset_up}_MASKED<br/>{masked} rows"]
    MASKED -->|KPI Aggregation| GOLD["GOLD_{dataset_up}_KPIS<br/>7 KPIs"]
    RAW -->|Audit Logging| AUDIT["PIPELINE_AUDIT_LOG"]
    
    style RAW fill:#92400e,color:#fef3c7
    style SILVER fill:#374151,color:#e5e7eb
    style MASKED fill:#4c1d95,color:#ddd6fe
    style GOLD fill:#854d0e,color:#fef9c3
    style AUDIT fill:#1e3a5f,color:#bfdbfe
"""
render_mermaid(lineage_code)

# ── Column-Level Lineage ───────────────────────────────────────
st.divider()
st.markdown("### 📊 Column-Level Transformations")

mlog = sel.get("masking_log", [])
if mlog:
    col_lineage = []
    for m in mlog:
        col_lineage.append({
            "Source Column": m.get("column", ""),
            "Source Table": f"RAW_OLIST_{dataset_up}",
            "Transform": m.get("action", ""),
            "Target Column": m.get("column", "").upper(),
            "Target Table": f"SILVER_{dataset_up}_MASKED"
        })
    st.dataframe(pd.DataFrame(col_lineage), use_container_width=True, hide_index=True)
else:
    st.info("No column-level masking transformations recorded for this batch.")

# ── Node Pipeline Lineage ──────────────────────────────────────
st.divider()
st.markdown("### 🔄 Node Execution Lineage")
ns = sel.get("node_status",{})
nodes = ["profile","bronze_inspector","schema_drift","pii_detector","rule_gen","validator","transform","pii_masker","gold_kpi","lineage_tracker","audit_writer"]
node_data = []
for n in nodes:
    s = ns.get(n,"—")
    icon = "✅" if s=="pass" else ("❌" if s=="fail" else "⏭")
    node_data.append({"Node":n, "Status":f"{icon} {s}", "Layer":"Bronze" if nodes.index(n)<6 else ("Silver" if nodes.index(n)<8 else ("Gold" if nodes.index(n)==8 else "Audit"))})
st.dataframe(pd.DataFrame(node_data), use_container_width=True, hide_index=True)
