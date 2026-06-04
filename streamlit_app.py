"""
streamlit_app.py — Unified Operations Command Center
LLM Data Pipeline — Enterprise Dashboard
"""
import os
import sys
import re
import json
import datetime
import subprocess
import time
import signal
from pathlib import Path
import pandas as pd
import streamlit as st
from utils.auth import verify_login, register_user
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

# ── ANSI escape code stripper ──────────────────────────────────────
_ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
def strip_ansi(text: str) -> str:
    """Remove terminal ANSI colour / formatting escape sequences."""
    return _ANSI_RE.sub('', text)

if os.path.exists(".env"):
    load_dotenv(".env")
elif os.path.exists(".env.example"):
    load_dotenv(".env.example")
else:
    load_dotenv()

st.set_page_config(page_title="Olist Operations Center", page_icon="🔮", layout="wide", initial_sidebar_state="expanded")

# ── Authentication System ────────────────────────────────────────
if "username" not in st.session_state:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>Olist LLM Pipeline</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8;'>Please log in to access your secure workspace.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        tab1, tab2 = st.tabs(["Log In", "Sign Up"])
        with tab1:
            l_email = st.text_input("Email", key="login_email")
            l_pass = st.text_input("Password", type="password", key="login_pass")
            if st.button("Log In", use_container_width=True, type="primary"):
                if verify_login(l_email, l_pass):
                    st.session_state["username"] = l_email.lower().strip()
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
        with tab2:
            s_email = st.text_input("Email", key="signup_email")
            s_pass = st.text_input("Password", type="password", key="signup_pass")
            if st.button("Sign Up", use_container_width=True, type="primary"):
                if s_email and s_pass:
                    if register_user(s_email, s_pass):
                        st.success("Account created! Please log in.")
                    else:
                        st.error("Email already registered.")
                else:
                    st.error("Please fill in both fields.")
    st.stop()

username = st.session_state["username"]


# ── Styling and Theme ───────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');

/* Apply Inter to everything EXCEPT Material Icons glyphs */
html, body, p, h1, h2, h3, h4, h5, h6, a, button, input, select, textarea {
  font-family: 'Inter', sans-serif;
}
.material-icons, span.material-icons {
  font-family: 'Material Icons' !important;
  font-weight: normal !important;
  font-style: normal !important;
  line-height: 1;
  display: inline-block;
  letter-spacing: normal;
  text-transform: none;
}

/* Classy Obsidian & Gold Theme */
.stApp{background:#09090b; color:#f4f4f5}
section[data-testid="stSidebar"]{background:#09090b!important; border-right: 1px solid rgba(212,175,55,.12)}
h1,h2,h3,h4,h5,h6{color:#fafafa!important; font-weight:800!important}
.hero{text-align:center;padding:1.5rem 0 0.5rem; background: linear-gradient(180deg, rgba(212,175,55,0.06) 0%, rgba(9,9,11,0) 100%); border-bottom: 1px solid rgba(212,175,55,0.08); margin-bottom: 1rem}
.hero h1{font-size:2.8rem;font-weight:900!important;background:linear-gradient(135deg,#cba328,#f3e5ab,#d4af37);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0}
.hero p{color:#a1a1aa;font-size:1rem;margin-top:.3rem; letter-spacing: 0.5px}

/* Sidebar expander polish */
section[data-testid="stSidebar"] [data-testid="stExpander"] details summary {
  color: #d4af37 !important; font-weight: 600 !important; font-size: .87rem !important;
  background: rgba(212,175,55,.05) !important; border-radius: 8px !important;
  padding: 8px 10px !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] details summary:hover {
  background: rgba(212,175,55,.09) !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] details {
  border: 1px solid rgba(212,175,55,.15) !important; border-radius: 10px !important; margin-bottom: 8px !important;
}

.metric-card{background:rgba(24,24,27,.5); border:1px solid rgba(212,175,55,.12); border-radius:14px; padding:16px 14px; text-align:center; box-shadow: 0 4px 20px rgba(0,0,0,0.2)}
.metric-card .val{font-size:2rem; font-weight:900; line-height:1.1; margin-bottom:4px}
.metric-card .lbl{font-size:.7rem; color:#71717a; text-transform:uppercase; letter-spacing:1.5px; font-weight:700}
.purple{color:#cba328} .indigo{color:#d4af37} .green{color:#34d399} .amber{color:#fbbf24} .rose{color:#fb7185} .white{color:#fafafa}

.terminal-header{background:#18181b; border:1px solid rgba(212,175,55,0.15); border-bottom:none; border-radius:8px 8px 0 0; padding:6px 12px; display:flex; align-items:center; gap:6px}
.terminal-dot{width:10px; height:10px; border-radius:50%}
.term-red{background:#fb7185} .term-yell{background:#fbbf24} .term-green{background:#34d399}
.terminal-title{font-family:'JetBrains Mono',monospace; font-size:.72rem; color:#71717a; margin-left:8px; font-weight:600}
.terminal-body{font-family:'JetBrains Mono',monospace!important; font-size:.8rem!important; background:#09090b!important; border:1px solid rgba(212,175,55,0.15)!important; border-radius:0 0 8px 8px!important; padding:12px!important; color:#d4af37!important; height: 260px; overflow-y: auto}

.card{background:rgba(24,24,27,.5); border:1px solid rgba(212,175,55,.08); border-radius:12px; padding:16px; margin-bottom:12px}
.chip{display:inline-block;padding:3px 12px;border-radius:99px;font-size:.72rem;font-weight:700}
.chip-ok{background:rgba(52,211,153,.12);color:#34d399}
.chip-fail{background:rgba(251,113,133,.12);color:#fb7185}
.chip-run{background:rgba(212,175,55,.12);color:#d4af37; animation: blinker 1.5s linear infinite}
@keyframes blinker { 50% { opacity: 0.5; } }

/* Self-Heal cards */
.heal-card{background:rgba(24,24,27,.7);border:1px solid rgba(251,191,36,.15);border-radius:14px;padding:0;margin-bottom:18px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.25)}
.heal-header{background:linear-gradient(90deg,rgba(251,191,36,.12),rgba(251,191,36,.04));padding:12px 16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;border-bottom:1px solid rgba(251,191,36,.12)}
.heal-body{padding:0 16px 16px}
.heal-badge{background:rgba(251,191,36,.18);color:#fbbf24;padding:3px 12px;border-radius:99px;font-size:.72rem;font-weight:800;letter-spacing:.5px}
.heal-node{background:rgba(212,175,55,.12);color:#d4af37;padding:3px 10px;border-radius:99px;font-size:.72rem;font-weight:700}
.heal-retry{background:rgba(243,229,171,.1);color:#f3e5ab;padding:3px 10px;border-radius:99px;font-size:.72rem;font-weight:700}
.heal-error-type{color:#fb7185;font-size:.78rem;font-weight:700;margin-left:auto}
.heal-section-label{font-size:.72rem;text-transform:uppercase;letter-spacing:1.5px;color:#71717a;font-weight:700;margin:12px 0 6px}
</style>
""", unsafe_allow_html=True)

# ── Dynamic Profiles Management ──────────────────────────────────
os.makedirs("profiles", exist_ok=True)
os.makedirs("metadata", exist_ok=True)


def load_profiles(user):
    prof_file = Path(f"profiles/{user}_profiles.json")
    if prof_file.exists():
        return json.load(open(prof_file))
    return {"Default": {
        "LLM_PROVIDER": "groq",
        "LLM_MODEL": "llama-3.3-70b-versatile",
        "GROQ_API_KEY": "",
        "SNOWFLAKE_ACCOUNT": "",
        "SNOWFLAKE_USER": "",
        "SNOWFLAKE_PASSWORD": "",
        "SNOWFLAKE_DATABASE": "MY_DB",
        "SNOWFLAKE_SCHEMA": "PUBLIC",
        "SNOWFLAKE_WAREHOUSE": "COMPUTE_WH",
        "USE_LOCAL_CSV": "false"
    }}


def save_profiles(user, profiles_dict):
    with open(f"profiles/{user}_profiles.json", "w") as f:
        json.dump(profiles_dict, f, indent=2)


profiles = load_profiles(username)


# Sidebar: Select Profile
st.sidebar.markdown("""
<div style="padding:4px 2px 6px">
  <div style="font-size:.65rem;text-transform:uppercase;letter-spacing:1.5px;
              color:#6366f1;font-weight:800;margin-bottom:6px">👤 Workspace</div>
</div>
""", unsafe_allow_html=True)
selected_profile = st.sidebar.selectbox("Active Profile", list(profiles.keys()), label_visibility="collapsed")

# Show active profile badge
st.sidebar.markdown(f"""
<div style="background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.2);
            border-radius:8px;padding:8px 10px;margin:4px 0 10px;font-size:.8rem">
  <span style="color:#a5b4fc;font-weight:700">Active:</span>
  <span style="color:#e2e8f0;margin-left:6px">{selected_profile}</span>
</div>
""", unsafe_allow_html=True)

st.session_state["active_profile"] = selected_profile

# Write out the selected profile configuration to profiles/{username}_{name}.json for config/settings to fetch
# This guarantees that the background process will only load the active user's active profile!
active_profile_key = f"{username}_{selected_profile}"
with open(f"profiles/{active_profile_key}.json", "w") as f:
    json.dump(profiles[selected_profile], f, indent=2)

# Sidebar: Profile configuration overrides — toggle button (avoids broken expander arrows)
if "_show_settings" not in st.session_state:
    st.session_state["_show_settings"] = False

settings_lbl = ("▲  Profile Settings" if st.session_state["_show_settings"] else "▼  Profile Settings")
if st.sidebar.button(settings_lbl, use_container_width=True, key="btn_toggle_settings"):
    st.session_state["_show_settings"] = not st.session_state["_show_settings"]
    st.rerun()

if st.session_state["_show_settings"]:
    prof_data = profiles[selected_profile]
    with st.sidebar:
        prov = st.selectbox("LLM Provider", ["groq", "ollama", "openai", "anthropic"],
                            index=["groq", "ollama", "openai", "anthropic"].index(prof_data.get("LLM_PROVIDER", "groq")),
                            key="prov_sel")
        model = st.text_input("LLM Model", prof_data.get("LLM_MODEL", "llama-3.3-70b-versatile"), key="model_inp")
        gkey  = st.text_input("API Key", prof_data.get("GROQ_API_KEY", ""), type="password", key="gkey_inp")
        st.markdown("---")
        local_csv = st.checkbox("Local CSV Mode (No Snowflake)",
                                value=(prof_data.get("USE_LOCAL_CSV", "false").lower() == "true"), key="lcsv_chk")
        sf_acc  = st.text_input("Snowflake Account",  prof_data.get("SNOWFLAKE_ACCOUNT",  ""),        disabled=local_csv, key="sf_acc")
        sf_user = st.text_input("Snowflake User",     prof_data.get("SNOWFLAKE_USER",     ""),        disabled=local_csv, key="sf_user")
        sf_pass = st.text_input("Password",           prof_data.get("SNOWFLAKE_PASSWORD", ""), type="password", disabled=local_csv, key="sf_pass")
        sf_db   = st.text_input("Database",           prof_data.get("SNOWFLAKE_DATABASE", "MY_DB"),   disabled=local_csv, key="sf_db")
        sf_sch  = st.text_input("Schema",             prof_data.get("SNOWFLAKE_SCHEMA",   "PUBLIC"),  disabled=local_csv, key="sf_sch")
        sf_wh   = st.text_input("Warehouse",          prof_data.get("SNOWFLAKE_WAREHOUSE","COMPUTE_WH"), disabled=local_csv, key="sf_wh")
        sf_role = st.text_input("Role",               prof_data.get("SNOWFLAKE_ROLE",     "SYSADMIN"), disabled=local_csv, key="sf_role")
        if st.button("Save Profile", use_container_width=True, type="primary", key="btn_save_prof"):
            profiles[selected_profile] = {
                "LLM_PROVIDER": prov, "LLM_MODEL": model, "GROQ_API_KEY": gkey,
                "SNOWFLAKE_ACCOUNT": sf_acc, "SNOWFLAKE_USER": sf_user,
                "SNOWFLAKE_PASSWORD": sf_pass, "SNOWFLAKE_DATABASE": sf_db,
                "SNOWFLAKE_SCHEMA": sf_sch, "SNOWFLAKE_WAREHOUSE": sf_wh,
                "SNOWFLAKE_ROLE": sf_role,
                "USE_LOCAL_CSV": "true" if local_csv else "false"
            }
            save_profiles(username, profiles)
            st.success("Saved!")
            st.rerun()

st.sidebar.markdown("<div style='margin:4px 0'></div>", unsafe_allow_html=True)

# Sidebar: Create new profile — toggle button
if "_show_newprof" not in st.session_state:
    st.session_state["_show_newprof"] = False

newprof_lbl = ("▲  New Profile" if st.session_state["_show_newprof"] else "▼  New Profile")
if st.sidebar.button(newprof_lbl, use_container_width=True, key="btn_toggle_newprof"):
    st.session_state["_show_newprof"] = not st.session_state["_show_newprof"]
    st.rerun()

if st.session_state["_show_newprof"]:
    with st.sidebar:
        new_name = st.text_input("Profile Name", "", key="new_prof_name")
        if st.button("Create", use_container_width=True, key="btn_create_prof") and new_name:
            if new_name not in profiles:
                profiles[new_name] = profiles["Default"].copy()
                save_profiles(username, profiles)
                st.success(f"{new_name} created!")
                st.rerun()

# Sidebar: Quick status pills
st.sidebar.divider()
prov_val  = profiles[selected_profile].get('LLM_PROVIDER', '—')
db_val    = profiles[selected_profile].get('SNOWFLAKE_DATABASE') \
            if profiles[selected_profile].get('USE_LOCAL_CSV') == 'false' else 'Local CSV'
st.sidebar.markdown(f"""
<div style="font-size:.72rem;color:#64748b;font-weight:700;text-transform:uppercase;
            letter-spacing:1px;margin-bottom:8px">Pipeline Status</div>
<div style="display:flex;flex-direction:column;gap:5px">
  <div style="background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.15);
              border-radius:7px;padding:6px 10px;font-size:.78rem">
    <span style="color:#818cf8;font-weight:700">LLM</span>
    <span style="color:#e2e8f0;float:right">{prov_val}</span>
  </div>
  <div style="background:rgba(52,211,153,.06);border:1px solid rgba(52,211,153,.12);
              border-radius:7px;padding:6px 10px;font-size:.78rem">
    <span style="color:#34d399;font-weight:700">DB</span>
    <span style="color:#e2e8f0;float:right">{db_val}</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Pure-HTML/CSS Pipeline Graph Renderer ─────────────────────────


def render_live_pipeline_graph(active_node, node_states):
    """Render a full-width, scrollable, CSS-only animated pipeline node diagram."""

    # Node definitions in order
    main_nodes = [
        ("profile",           "1", "Profile Loader",    "🗂️"),
        ("pii_detector",      "2", "PII Detector",      "🔒"),
        ("schema_drift",      "3", "Schema Drift",      "📐"),
        ("bronze_inspector",  "4", "Bronze Inspector",  "🔍"),
        ("rule_gen",          "5", "Rule Generator",    "📋"),
        ("validator",         "6", "GE Validator",      "✅"),
        ("transform",         "7", "Transform",         "⚙️"),
        ("pii_masker",        "8", "PII Masker",        "🛡️"),
        ("gold_kpi",          "9", "Gold KPI",          "🥇"),
        ("lineage_tracker",   "10", "Lineage Tracker",  "🔗"),
        ("audit_writer",      "11", "Audit Writer",     "📝"),
        ("alert",             "12", "Alert Engine",     "🚨"),
    ]

    def node_style(key):
        if key == active_node or node_states.get(key) == "running":
            return "node-running"
        if node_states.get(key) == "passed":
            return "node-passed"
        if node_states.get(key) == "failed":
            return "node-failed"
        if node_states.get("heal_agent") == "running" and key == "validator":
            return "node-healing"
        return "node-idle"

    heal_cls = node_style("heal_agent") if "heal_agent" in (active_node or "") or node_states.get("heal_agent") else "node-idle"
    if node_states.get("heal_agent") == "running":
        heal_cls = "node-healing"
    elif node_states.get("heal_agent") == "passed":
        heal_cls = "node-passed"

    # Build main nodes HTML
    nodes_html = ""
    for key, num, label, icon in main_nodes:
        cls = node_style(key)
        is_running = "running" in cls
        pulse = "<span class='pulse-ring'></span>" if is_running else ""
        nodes_html += f"""
        <div class="pnode {cls}" title="{label}">
          {pulse}
          <div class="pnode-icon">{icon}</div>
          <div class="pnode-num">{num}</div>
          <div class="pnode-label">{label}</div>
        </div>
        <div class="arrow">&#8594;</div>"""
    # Remove last arrow, add heal loop
    nodes_html = nodes_html.rsplit("<div class=\"arrow\">&#8594;</div>", 1)[0]

    html_code = f"""
    <!DOCTYPE html><html><head>
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, sans-serif; }}
      body {{ background: #0b0b14; padding: 16px 12px 8px; }}

      /* Legend */
      .legend {{ display:flex; gap:14px; margin-bottom:14px; flex-wrap:wrap; }}
      .leg {{ display:flex; align-items:center; gap:6px; font-size:.72rem; color:#94a3b8; font-weight:600; }}
      .leg-dot {{ width:10px;height:10px;border-radius:50%; }}
      .ld-idle{{ background:#374151; }} .ld-run{{ background:#3b82f6; }}
      .ld-pass{{ background:#10b981; }} .ld-fail{{ background:#ef4444; }}
      .ld-heal{{ background:#f59e0b; }}

      /* Flow row */
      .flow {{ display:flex; align-items:center; flex-wrap:nowrap;
               overflow-x:auto; gap:0; padding-bottom:8px;
               scrollbar-width:thin; scrollbar-color:#374151 transparent; }}
      .flow::-webkit-scrollbar{{ height:4px; }}
      .flow::-webkit-scrollbar-track{{ background:transparent; }}
      .flow::-webkit-scrollbar-thumb{{ background:#374151; border-radius:4px; }}

      /* Node base */
      .pnode {{ position:relative; min-width:82px; min-height:82px; border-radius:12px;
                display:flex; flex-direction:column; align-items:center;
                justify-content:center; gap:3px; padding:10px 8px;
                border:2px solid; cursor:default; flex-shrink:0; transition: box-shadow .3s; }}
      .pnode-icon {{ font-size:1.3rem; line-height:1; }}
      .pnode-num  {{ font-size:.6rem; font-weight:800; opacity:.6; letter-spacing:.5px; }}
      .pnode-label {{ font-size:.68rem; font-weight:700; text-align:center;
                      line-height:1.2; color:inherit; }}

      /* States */
      .node-idle    {{ background:#12121f; border-color:#374151; color:#9ca3af; }}
      .node-running {{ background:#1e3a8a; border-color:#60a5fa; color:#fff;
                       box-shadow:0 0 18px rgba(96,165,250,.45); }}
      .node-passed  {{ background:#064e3b; border-color:#10b981; color:#6ee7b7; }}
      .node-failed  {{ background:#7f1d1d; border-color:#ef4444; color:#fca5a5;
                       box-shadow:0 0 14px rgba(239,68,68,.3); }}
      .node-healing {{ background:#78350f; border-color:#f59e0b; color:#fde68a;
                       box-shadow:0 0 14px rgba(245,158,11,.35); }}

      /* Pulse ring for running */
      .pulse-ring {{ position:absolute; top:-5px; right:-5px;
                     width:14px; height:14px; border-radius:50%;
                     background:#60a5fa; opacity:.9;
                     animation: ping 1.2s ease-in-out infinite; }}
      @keyframes ping {{ 0%{{transform:scale(1);opacity:.8}} 100%{{transform:scale(2.2);opacity:0}} }}

      /* Arrows */
      .arrow {{ color:#374151; font-size:1.1rem; padding:0 4px; flex-shrink:0; align-self:center; margin-top:-14px; }}

      /* Heal loop section */
      .heal-row {{ display:flex; align-items:center; gap:10px; margin-top:14px;
                   padding:10px 14px; border-radius:12px;
                   background:rgba(245,158,11,.07); border:1px dashed rgba(245,158,11,.25); }}
      .heal-label {{ font-size:.75rem; color:#f59e0b; font-weight:700; }}
      .heal-desc  {{ font-size:.7rem; color:#92400e; }}
      .hl-node {{ min-width:100px; }}
      .heal-arrows {{ display:flex; flex-direction:column; align-items:center; gap:2px; color:#f59e0b; font-size:.8rem; }}
    </style>
    </head><body>

    <div class="legend">
      <div class="leg"><div class="leg-dot ld-idle"></div>Waiting</div>
      <div class="leg"><div class="leg-dot ld-run"></div>Running</div>
      <div class="leg"><div class="leg-dot ld-pass"></div>Passed</div>
      <div class="leg"><div class="leg-dot ld-fail"></div>Failed</div>
      <div class="leg"><div class="leg-dot ld-heal"></div>Healing</div>
    </div>

    <div class="flow">
      {nodes_html}
    </div>

    <div class="heal-row">
      <div class="pnode {heal_cls} hl-node">
        <div class="pnode-icon">🔧</div>
        <div class="pnode-label">Heal Agent</div>
      </div>
      <div class="heal-arrows">
        <span title="fail → heal">&#8592; fail</span>
        <span title="heal → retry">retry &#8594;</span>
      </div>
      <div style="font-size:.75rem;color:#94a3b8;line-height:1.5">
        <div style="color:#f59e0b;font-weight:700">Self-Healing Loop</div>
        On validation failure, Groq LLM generates a SQL/code fix<br>
        and automatically retries the Validator node.
      </div>
    </div>

    </body></html>
    """
    components.html(html_code, height=280, scrolling=True)



# ── Shared Data Loaders ───────────────────────────────────────────
def load_hist():
    # Get active profile batch history
    prof_suffix = f"{username}_{selected_profile}"
    gp = Path(f"metadata/batch_history_{prof_suffix}.json")
    if gp.exists():
        return json.load(open(gp))
    return []


hist = load_hist()


# Connect to Snowflake Helper
def get_sf():
    cfg = profiles[selected_profile]
    if cfg.get("USE_LOCAL_CSV") == "true":
        return None
    try:
        import snowflake.connector
        return snowflake.connector.connect(
            account=cfg.get("SNOWFLAKE_ACCOUNT"),
            user=cfg.get("SNOWFLAKE_USER"),
            password=cfg.get("SNOWFLAKE_PASSWORD"),
            warehouse=cfg.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
            database=cfg.get("SNOWFLAKE_DATABASE", "MY_DB"),
            schema=cfg.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
            role=profiles[selected_profile].get("SNOWFLAKE_ROLE", "SYSADMIN")
        )
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


# ── Hero ──────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🔮  Operations Command Center</h1>
  <p>Autonomous Quality Healing & Lineage Engine · Llama 3.3 70B & Great Expectations</p>
</div>
""", unsafe_allow_html=True)

# ── Dynamic Auto-Refresh Trigger (Runs only when active process is on)
running_pid = st.session_state.get("pipeline_process_pid")
if running_pid:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=1500, key="pipeline_refresh")

# Check background process completion
if running_pid:
    # Check if PID is still alive
    try:
        os.kill(running_pid, 0)
        is_running = True
    except OSError:
        is_running = False
        # Process completed! Let's clean up
        st.session_state["pipeline_process_pid"] = None
        # Copy newly created batch history item to profile history
        hist_path = f"metadata/batch_history_{username}_{selected_profile}.json"
        p = Path(hist_path)
        if p.exists():
            new_hist = json.load(open(p))
            if new_hist:
                latest_run = new_hist[-1]
                # Read profile hist
                p_hist = load_hist()
                p_hist.append(latest_run)
                with open(f"metadata/{selected_profile}_batch_history.json", "w") as pf:
                    json.dump(p_hist, pf, indent=2, default=str)
        st.success("🎉 Background pipeline processing run completed successfully!")
        st.rerun()
else:
    is_running = False

# Load live graph state
live_state = {}
if Path("metadata/pipeline_live_state.json").exists():
    try:
        live_state = json.load(open("metadata/pipeline_live_state.json"))
    except:
        pass

# ── Top KPIs Rows ─────────────────────────────────────────────────
latest_run = hist[-1] if hist else {}
k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    st.markdown(f"""<div class="metric-card"><div class="val purple">{len(hist)}</div><div class="lbl">Batches</div></div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="metric-card"><div class="val white">{latest_run.get('raw_rows', 0):,}</div><div class="lbl">Raw Rows</div></div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""<div class="metric-card"><div class="val green">{latest_run.get('clean_rows', 0):,}</div><div class="lbl">Clean Silver</div></div>""", unsafe_allow_html=True)
with k4:
    st.markdown(f"""<div class="metric-card"><div class="val rose">{latest_run.get('quarantine', 0):,}</div><div class="lbl">Quarantine</div></div>""", unsafe_allow_html=True)
with k5:
    st.markdown(f"""<div class="metric-card"><div class="val amber">{latest_run.get('heals', 0)}</div><div class="lbl">Self Heals</div></div>""", unsafe_allow_html=True)
with k6:
    status_class = "chip-run" if is_running else ("chip-ok" if latest_run.get('status') == "SUCCESS" else "chip-fail")
    status_label = "RUNNING" if is_running else latest_run.get('status', 'IDLE')
    st.markdown(f"""<div class="metric-card"><div class="val"><span class="chip {status_class}">{status_label}</span></div><div class="lbl">Engine State</div></div>""",
                unsafe_allow_html=True)

# ── Main Control Dashboard ───────────────────────────────
st.markdown("### Dynamic Pipeline Operations Flow")
active_n = live_state.get("active_node", "") if is_running else ""
node_sts = live_state.get("nodes", {}) if is_running else {}
render_live_pipeline_graph(active_n, node_sts)

st.divider()
st.markdown("### Control Panel")
with st.expander("Trigger Agentic Run", expanded=False):
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    custom_datasets = [f.stem for f in upload_dir.glob("*.csv")]
    all_datasets = ["customers", "orders", "payments", "products"] + custom_datasets

    c1, c2, c3 = st.columns(3)
    with c1:
        c_dataset = st.selectbox("Dataset", all_datasets)
    c_rows = st.slider("Batch Size", 100, 1000, 200, 50)

btn1, btn2 = st.columns(2)
with btn1:
    if st.button(" Trigger Agentic Run", use_container_width=True, type="primary", disabled=is_running):
        # Clean up old state
        if Path("metadata/pipeline_live_state.json").exists():
            try:
                os.remove("metadata/pipeline_live_state.json")
            except:
                pass
        env = os.environ.copy()
        env["ACTIVE_PROFILE_NAME"] = f"{username}_{selected_profile}"
    
        # Scope the log file to this specific user+profile
        log_path = f"metadata/live_run_{username}_{selected_profile}.log"
        with open(log_path, "w") as log_f:
            proc = subprocess.Popen(
                [sys.executable, "run_continuous.py", "--once", "--rows", str(c_rows), "--datasets", c_dataset],
                env=env,
                stdout=log_f,
                stderr=log_f,
                cwd=os.getcwd()
            )
        st.session_state["pipeline_process_pid"] = proc.pid
        st.rerun()

with btn2:
    if st.button("🛑 Emergency Stop", use_container_width=True, type="secondary", disabled=not is_running):
        try:
            pid = st.session_state["pipeline_process_pid"]
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
        except:
            pass
        st.session_state["pipeline_process_pid"] = None
        st.rerun()

# ── Dynamic Scrolling Command Terminal ─────────────────────────────
st.markdown("### Live Agent Communication Streams")
st.markdown("""
<div class="terminal-header">
  <div class="terminal-dot term-red"></div>
  <div class="terminal-dot term-yell"></div>
  <div class="terminal-dot term-green"></div>
  <span class="terminal-title">agentic_pipeline_runner.log</span>
</div>
""", unsafe_allow_html=True)

log_box = st.empty()

# Stream background log — strip ANSI colour codes before display
log_path = Path(f"metadata/live_run_{username}_{selected_profile}.log")
if log_path.exists():
    try:
        with open(log_path, errors="replace") as lf:
            lines = lf.readlines()
            raw = "".join(lines[-30:])
            log_content = strip_ansi(raw).strip()
            log_box.code(log_content or "Agent pipeline initialized. Awaiting commands...", language="text")
    except Exception:
        log_box.code("Awaiting pipeline activation...", language="text")
else:
    log_box.code("Awaiting pipeline activation...", language="text")

# ── Analytical Tabs (Unified tabs instead of fragmented pages) ─────
st.divider()
st.markdown("### Detail Intelligence Workspace")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Performance Analytics",
    "PII Governance",
    "Schema Evolution",
    "Self-Healing Audit",
    "Raw Run History",
    "Snowflake Explorer"
])

with tab1:
    if hist:
        st.markdown("#### Per-Batch Performance Overview")
        hdf = pd.DataFrame(hist)
        hdf["label"] = [f"#{i+1} ({x[:8]})" for i, x in enumerate(hdf["batch_id"])]

        g1, g2 = st.columns(2)
        with g1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=hdf["label"], y=hdf["raw_rows"], name="Bronze (Raw)", marker_color="#fbbf24"))
            fig.add_trace(go.Bar(x=hdf["label"], y=hdf["clean_rows"], name="Silver (Clean)", marker_color="#94a3b8"))
            fig.add_trace(
                go.Bar(x=hdf["label"], y=hdf.get("masked_rows", hdf["clean_rows"]), name="PII Masked",
                       marker_color="#818cf8"))
            fig.update_layout(title="Volume Flow through Pipeline Layers (Log Scale)", barmode="group", height=320,
                              yaxis_type="log",
                              template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        with g2:
            colors = ["#34d399" if s == "SUCCESS" else "#fb7185" for s in hdf["status"]]
            fig2 = go.Figure(go.Bar(x=hdf["label"], y=hdf["duration_s"], marker_color=colors, text=hdf["status"],
                                     textposition="auto"))
            fig2.update_layout(title="Batch Processing Duration & Success Rate", height=320, template="plotly_dark",
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Performance stats will generate after the first pipeline run.")

with tab2:
    st.markdown("#### PII Classification & Obfuscation Audits")
    if latest_run and "masking_log" in latest_run and latest_run["masking_log"]:
        mlog = latest_run["masking_log"]
        st.markdown(f"**Dataset**: `{latest_run.get('dataset')}` | **Batch ID**: `{latest_run.get('batch_id')}`")
        for m in mlog:
            with st.container(border=True):
                icon = "🔴" if m.get('level') == 'HIGH' else "🟡"
                st.markdown(f"**{icon} Column `{m.get('column')}` — {m.get('level')} PII**")
                
                c1, c2 = st.columns(2)
                with c1:
                    st.caption(f"**Reason:** {m.get('reason')}")
                with c2:
                    st.caption(f"**Action:** `{m.get('action')}`")

                tdf = pd.DataFrame({
                    "Sample Raw Data (Bronze)": m.get("sample_before", []),
                    "Sample Obfuscated Data (Silver)": m.get("sample_after", [])
                })
                st.dataframe(tdf, use_container_width=True)
    else:
        st.info("No PII masking logs available for the latest batch.")

with tab3:
    st.markdown("#### Schema Evolution & Drift Alerts")
    if latest_run and "schema_drift_events" in latest_run and latest_run["schema_drift_events"]:
        drifts = latest_run["schema_drift_events"]
        st.warning(f"⚠️ {len(drifts)} Schema drift alerts triggered in the current batch!")
        for d in drifts:
            with st.container(border=True):
                icon = "🟡" if d.get('severity') == 'MEDIUM' else "🔴"
                st.markdown(f"**{icon} [{d.get('severity')}] {d.get('drift_type')}**")
                st.markdown(f"**Column:** `{d.get('column_name')}` &nbsp;&nbsp;|&nbsp;&nbsp; **Field Type:** `{d.get('type')}`")
                st.info(f"**Explanation:** {d.get('description')}")
    else:
        st.success("✅ Schema remains consistent. Zero schema drift events detected in the latest run.")

with tab4:
    st.markdown("#### 🔧 Universal Self-Healing Action Log")
    if latest_run and "heal_log" in latest_run and latest_run["heal_log"]:
        heals = latest_run["heal_log"]
        # Summary banner
        st.markdown(f"""
        <div style="background:linear-gradient(90deg,rgba(251,191,36,.1),rgba(251,191,36,.03));
                    border:1px solid rgba(251,191,36,.25);border-radius:12px;padding:14px 18px;
                    margin-bottom:20px;display:flex;align-items:center;gap:14px">
          <span style="font-size:1.6rem">⚡</span>
          <div>
            <div style="color:#fbbf24;font-weight:800;font-size:1rem">{len(heals)} Self-Healing Action{'s' if len(heals)!=1 else ''} Executed</div>
            <div style="color:#94a3b8;font-size:.82rem;margin-top:2px">AI autonomously recovered from data quality failures in this batch</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        for i, h in enumerate(heals):
            node      = h.get('node', 'Unknown')
            retry     = h.get('retry_num', 1)
            err_type  = h.get('error_type', 'Unknown Error')
            err_msg   = h.get('error_msg', '')
            fix       = h.get('fix', '')

            st.markdown(f"""
            <div class="heal-card">
              <div class="heal-header">
                <span class="heal-badge">Heal #{i+1}</span>
                <span class="heal-node">📦 {node}</span>
                <span class="heal-retry">↩ Retry #{retry}</span>
                <span class="heal-error-type">🔴 {err_type}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown('<div class="heal-section-label">Error Message</div>', unsafe_allow_html=True)
                st.code(err_msg or "(no message)", language="text")
            with col_b:
                st.markdown('<div class="heal-section-label">Generated SQL / Code Patch Applied</div>', unsafe_allow_html=True)
                st.code(fix or "(no patch)", language="sql")
    else:
        st.markdown("""
        <div style="background:rgba(52,211,153,.07);border:1px solid rgba(52,211,153,.2);
                    border-radius:14px;padding:28px;text-align:center;margin-top:8px">
          <div style="font-size:2.4rem;margin-bottom:10px">✅</div>
          <div style="color:#34d399;font-weight:800;font-size:1.05rem">Zero Active Failures</div>
          <div style="color:#94a3b8;font-size:.85rem;margin-top:4px">No self-healing actions were required for the latest batch run.</div>
        </div>
        """, unsafe_allow_html=True)

with tab5:
    st.markdown("#### Raw Batch Executions Log")
    if hist:
        df_hist = pd.DataFrame(hist)
        display_cols = [c for c in
                        ["batch_num", "batch_id", "timestamp", "status", "raw_rows", "clean_rows", "heals",
                         "duration_s"] if c in df_hist.columns]
        st.dataframe(df_hist[display_cols].iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("Run history empty.")

with tab6:
    st.markdown("#### Snowflake Data Browser")
    
    # Dynamically find available tables
    datasets = set(["customers"])
    if hist:
        for b in hist:
            if "dataset" in b:
                datasets.add(b["dataset"].lower())
                
    tables = {}
    for ds in datasets:
        dsu = ds.upper()
        tables[f"🟤 RAW_OLIST_{dsu}"] = f"RAW_OLIST_{dsu}"
        tables[f"⚪ SILVER_{dsu}_CLEAN"] = f"SILVER_{dsu}_CLEAN"
        tables[f"🔒 SILVER_{dsu}_MASKED"] = f"SILVER_{dsu}_MASKED"
        tables[f"🥇 GOLD_{dsu}_KPIS"] = f"GOLD_{dsu}_KPIS"
    tables["📋 PIPELINE_AUDIT_LOG"] = "PIPELINE_AUDIT_LOG"
    tables = dict(sorted(tables.items()))
    
    sel_tbl = st.selectbox("Database Table to query:", list(tables.keys()))
    t_name = tables[sel_tbl]
    l_limit = st.slider("Max rows", 10, 200, 50, 10)

    if st.button("🔍 Execute Query", type="primary"):
        with st.spinner("Fetching data..."):
            is_local_csv = profiles.get(selected_profile, {}).get("USE_LOCAL_CSV", "false").lower() == "true"
            df_sf = pd.DataFrame()
            
            if is_local_csv:
                # Local CSV fallback
                csv_map = {
                    "RAW_OLIST_CUSTOMERS": "data/olist_customers_dataset.csv",
                    "RAW_OLIST_ORDERS":    "data/olist_orders_dataset.csv",
                    "RAW_OLIST_PAYMENTS":  "data/olist_order_payments_dataset.csv",
                    "RAW_OLIST_PRODUCTS":  "data/olist_products_dataset.csv",
                }
                path = csv_map.get(t_name)
                if path and Path(path).exists():
                    df_sf = pd.read_csv(path).head(l_limit)
                else:
                    for layer in ["silver", "bronze", "gold", "audit"]:
                        p = f"outputs/{layer}/{t_name}.csv"
                        if Path(p).exists():
                            df_sf = pd.read_csv(p).head(l_limit)
                            break
            else:
                df_sf = qry(f"SELECT * FROM {t_name} LIMIT {l_limit}")
                
            if not df_sf.empty:
                st.metric("Total Records Queried", len(df_sf))
                st.dataframe(df_sf, use_container_width=True)
            else:
                st.warning("Table is currently empty or does not exist.")

st.markdown("---")
st.markdown('<div style="text-align:center;color:#4b5563;font-size:.78rem">🔮 Operations Center · Multi-Agent StateGraph Engine · Groq & Snowflake</div>', unsafe_allow_html=True)
