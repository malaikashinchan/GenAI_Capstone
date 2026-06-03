"""Page 1 — Pipeline Control Panel"""
import os, subprocess, json, time
import signal
import psutil
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Pipeline Control", page_icon="🎛️", layout="wide")

# ── Shared styles (consistent with main app) ────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, p, h1, h2, h3, h4, h5, h6, a, button, input, select, textarea { font-family: 'Inter', sans-serif; }
.stApp { background: #0b0b14; color: #e2e8f0; }

/* Config card grid */
.cfg-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 8px; }
.cfg-card {
  background: rgba(20,20,40,.75);
  border: 1px solid rgba(99,102,241,.15);
  border-radius: 12px;
  padding: 14px 16px;
  transition: border-color .2s;
}
.cfg-card:hover { border-color: rgba(99,102,241,.35); }
.cfg-label {
  font-size: .72rem;
  text-transform: uppercase;
  letter-spacing: 1.4px;
  color: #6366f1;
  font-weight: 700;
  margin-bottom: 5px;
}
.cfg-value {
  font-size: .98rem;
  font-weight: 700;
  color: #e2e8f0;
  font-family: 'JetBrains Mono', monospace !important;
  word-break: break-all;
}
.cfg-value.accent-purple { color: #a78bfa; }
.cfg-value.accent-green  { color: #34d399; }
.cfg-value.accent-amber  { color: #fbbf24; }

/* Section title */
.sec-title {
  font-size: 1.05rem;
  font-weight: 800;
  color: #e2e8f0;
  margin: 20px 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.sec-title span { opacity: .6; font-size: .8rem; font-weight: 500; }

/* Batch table wrapper */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 🎛️ Pipeline Control Panel")
st.caption("Generate data, trigger pipeline runs, control batch parameters")

# ── Controls ────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    rows = st.slider("Batch Size", 100, 1000, 200, 50)
with c2:
    interval = st.slider("Loop Interval (seconds)", 30, 120, 45, 15)
with c3:
    mode = st.radio("Run Mode", ["Single Batch", "Continuous Loop"], horizontal=True)

st.divider()

# Scan for custom datasets
upload_dir = Path("data/uploads")
upload_dir.mkdir(parents=True, exist_ok=True)
custom_datasets = [f.stem for f in upload_dir.glob("*.csv")]
all_datasets = ["customers", "orders", "payments", "products"] + custom_datasets

c1, c2 = st.columns([2, 1])
with c1:
    ds_sel = st.multiselect(
        "Datasets to Process", 
        all_datasets, 
        default=all_datasets
    )
with c2:
    uploaded_file = st.file_uploader("Upload Custom Dataset", type=["csv"])
    if uploaded_file is not None:
        file_path = upload_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Saved {uploaded_file.name}")
        st.rerun()

st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📊 Generate Data Only", use_container_width=True, type="secondary"):
        with st.spinner("Generating data..."):
            result = subprocess.run(["python3", "generate_data.py", "--rows", str(rows)],
                                     capture_output=True, text=True, cwd=os.getcwd(), timeout=60)
            if result.returncode == 0:
                st.success("✅ Data generated and pushed to Snowflake!")
                st.code(result.stdout[-500:], language="text")
            else:
                st.error(f"❌ Error: {result.stderr[-300:]}")

with col2:
    if st.button("🚀 Run Full Pipeline", use_container_width=True, type="primary"):
        if not ds_sel:
            st.error("Please select at least one dataset to process.")
        else:
            # If Single Batch, run exactly enough batches to cover the selected datasets once.
            if mode == "Single Batch":
                cmd = ["python3", "run_continuous.py", "--batches", str(len(ds_sel))]
            else:
                cmd = ["python3", "run_continuous.py", "--loop"]
            
            cmd.extend(["--rows", str(rows), "--interval", str(interval), "--datasets"] + ds_sel)
            
            with st.status("Running pipeline...", expanded=True) as status:
                st.write(f"Mode: {mode} | Rows: {rows} | Datasets: {', '.join(ds_sel)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd(), timeout=300)
                
                # Save to live_run.log so the main page terminal stays updated
                with open("metadata/live_run.log", "w") as f:
                    f.write(result.stdout)

            if result.returncode == 0:
                status.update(label="✅ Pipeline Complete!", state="complete")
                st.code(result.stdout[-1500:], language="text")
            else:
                status.update(label="❌ Pipeline Failed", state="error")
                st.code(result.stderr[-500:], language="text")

with col3:
    if st.button("🔄 Refresh Dashboard", use_container_width=True):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

# ── Current Configuration ────────────────────────────────────────
llm_prov = os.getenv("LLM_PROVIDER", "—")
llm_mod  = os.getenv("LLM_MODEL", "—")
sf_db    = os.getenv("SNOWFLAKE_DATABASE", "—")
sf_sch   = os.getenv("SNOWFLAKE_SCHEMA", "—")
sf_wh    = os.getenv("SNOWFLAKE_WAREHOUSE", "—")
sf_role  = os.getenv("SNOWFLAKE_ROLE", "—")

st.markdown('<div class="sec-title">⚙️ Current Configuration <span>active environment variables</span></div>',
            unsafe_allow_html=True)
st.markdown(f"""
<div class="cfg-grid">
  <div class="cfg-card">
    <div class="cfg-label">LLM Provider</div>
    <div class="cfg-value accent-purple">{llm_prov}</div>
  </div>
  <div class="cfg-card">
    <div class="cfg-label">Snowflake Database</div>
    <div class="cfg-value accent-green">{sf_db}</div>
  </div>
  <div class="cfg-card">
    <div class="cfg-label">Warehouse</div>
    <div class="cfg-value accent-amber">{sf_wh}</div>
  </div>
  <div class="cfg-card">
    <div class="cfg-label">LLM Model</div>
    <div class="cfg-value" title="{llm_mod}">{llm_mod[:32]}{'…' if len(llm_mod) > 32 else ''}</div>
  </div>
  <div class="cfg-card">
    <div class="cfg-label">Schema</div>
    <div class="cfg-value">{sf_sch}</div>
  </div>
  <div class="cfg-card">
    <div class="cfg-label">Role</div>
    <div class="cfg-value">{sf_role}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Recent Batches ──────────────────────────────────────────────
st.markdown('<div class="sec-title">📦 Recent Batches <span>last 10 runs</span></div>',
            unsafe_allow_html=True)

p = Path("metadata/batch_history.json")
if p.exists():
    hist = json.load(open(p))
    import pandas as pd
    df = pd.DataFrame(hist[-10:])
    display_cols = [c for c in
                    ["batch_id", "timestamp", "status", "raw_rows", "clean_rows",
                     "masked_rows", "heals", "duration_s"] if c in df.columns]
    # Style status column
    def colour_status(val):
        if val == "SUCCESS":
            return "color: #34d399; font-weight: 700"
        elif val == "FAILED":
            return "color: #fb7185; font-weight: 700"
        return ""

    styled = df[display_cols].style
    if "status" in display_cols:
        styled = styled.applymap(colour_status, subset=["status"])

    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("No batch history yet.")
