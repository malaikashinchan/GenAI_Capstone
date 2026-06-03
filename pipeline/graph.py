"""
pipeline/graph.py — GEN_AI_Capstone-2
LangGraph StateGraph: 12 nodes + Heal Agent

LLM is on top of EVERY layer:
  BRONZE  1. profile          — schema, row count, sample rows
          2. bronze_inspector — LLM scans raw batch → reports every issue
          3. schema_drift     — detect schema drift vs reference
          4. pii_detector     — LLM classifies every column for PII
          5. rule_gen         — LLM generates GE validation rules
          6. validator        — runs GE rules (fail → Heal Agent)

  SILVER  7. transform        — clean / quarantine split + pandas healing
          8. pii_masker       — LLM-detected PII masked; before/after logged

  GOLD    9. gold_kpi         — LLM computes KPIs + business insights

  AUDIT  10. lineage_tracker
         11. audit_writer
         12. alert            — terminal (SUCCESS or ESCALATED)

Every node: pass → next | fail → heal_agent → LLM fix → retry (max 3) → alert
"""
from langgraph.graph import StateGraph
from agents.state import AgentState
from agents.nodes import (
    profile, bronze_inspector, schema_drift, pii_detector, rule_gen,
    validator, transform, pii_masker, gold_kpi,
    lineage_tracker, audit_writer, alert, heal_agent,
)
from loguru import logger
import os
import json

def _write_live_state(node_name: str, status: str):
    try:
        os.makedirs("metadata", exist_ok=True)
        path = "metadata/pipeline_live_state.json"
        state = {}
        if os.path.exists(path):
            with open(path) as f:
                try: state = json.load(f)
                except: pass
        
        state["active_node"] = node_name
        state["status"] = status
        
        if "nodes" not in state:
            state["nodes"] = {}
        
        # When a new run starts (at profile), reset other nodes to idle
        if node_name == "profile" and status == "running":
            state["nodes"] = {}
            
        state["nodes"][node_name] = status
        
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write live state: {e}")


def make_node(node_name, run_func):
    def wrapped(state: AgentState) -> AgentState:
        _write_live_state(node_name, "running")
        try:
            res = run_func(state)
            if node_name == "heal_agent":
                _write_live_state(node_name, "passed")
            else:
                status = res.get("node_status", {}).get(node_name, "pass")
                _write_live_state(node_name, "passed" if status == "pass" else "failed")
            return res
        except Exception as e:
            _write_live_state(node_name, "failed")
            raise e
    return wrapped


def route(state: AgentState) -> str:
    node   = state["current_node"]
    status = state["node_status"].get(node, "pass")
    logger.debug(f"ROUTER | '{node}' → '{status}'")
    return status


def route_after_heal(state: AgentState) -> str:
    if state.get("give_up", False):
        logger.error("ROUTER | give_up=True → escalating to alert")
        return "give_up"
    target = f"retry_{state['current_node']}"
    logger.info(f"ROUTER | Heal done → '{target}'")
    return target


def build_pipeline():
    graph = StateGraph(AgentState)

    # ── Register all nodes ────────────────────────────────────────
    graph.add_node("profile",          make_node("profile", profile.run))
    graph.add_node("bronze_inspector", make_node("bronze_inspector", bronze_inspector.run))   # NEW — LLM on Bronze
    graph.add_node("schema_drift",     make_node("schema_drift", schema_drift.run))
    graph.add_node("pii_detector",     make_node("pii_detector", pii_detector.run))       # LLM on Bronze
    graph.add_node("rule_gen",         make_node("rule_gen", rule_gen.run))           # LLM on Bronze
    graph.add_node("validator",        make_node("validator", validator.run))
    graph.add_node("transform",        make_node("transform", transform.run))
    graph.add_node("pii_masker",       make_node("pii_masker", pii_masker.run))         # LLM on Silver
    graph.add_node("gold_kpi",         make_node("gold_kpi", gold_kpi.run))           # LLM on Gold
    graph.add_node("lineage_tracker",  make_node("lineage_tracker", lineage_tracker.run))
    graph.add_node("audit_writer",     make_node("audit_writer", audit_writer.run))
    graph.add_node("alert",            make_node("alert", alert.run))
    graph.add_node("heal_agent",       make_node("heal_agent", heal_agent.run))         # LLM everywhere

    graph.set_entry_point("profile")

    # ── Pipeline flow: Bronze → Silver → Gold ─────────────────────
    pipeline_order = [
        # BRONZE
        ("profile",          "bronze_inspector"),
        ("bronze_inspector", "schema_drift"),
        ("schema_drift",     "pii_detector"),
        ("pii_detector",     "rule_gen"),
        ("rule_gen",         "validator"),
        ("validator",        "transform"),
        # SILVER
        ("transform",        "pii_masker"),
        ("pii_masker",       "gold_kpi"),
        # GOLD
        ("gold_kpi",         "lineage_tracker"),
        # AUDIT
        ("lineage_tracker",  "audit_writer"),
        ("audit_writer",     "alert"),
    ]

    for src, dst in pipeline_order:
        graph.add_conditional_edges(src, route, {"pass": dst, "fail": "heal_agent"})

    # ── Heal Agent router ─────────────────────────────────────────
    graph.add_conditional_edges(
        "heal_agent",
        route_after_heal,
        {
            "retry_profile":           "profile",
            "retry_bronze_inspector":  "bronze_inspector",
            "retry_schema_drift":      "schema_drift",
            "retry_pii_detector":      "pii_detector",
            "retry_rule_gen":          "rule_gen",
            "retry_validator":         "validator",
            "retry_transform":         "transform",
            "retry_pii_masker":        "pii_masker",
            "retry_gold_kpi":          "gold_kpi",
            "retry_lineage_tracker":   "lineage_tracker",
            "retry_audit_writer":      "audit_writer",
            "give_up":                 "alert",
        }
    )

    graph.add_edge("alert", "__end__")

    logger.info(
        "GRAPH | Pipeline compiled — 12 nodes + Heal Agent | "
        "LLM on every layer: Bronze → Silver → Gold"
    )
    return graph.compile()


pipeline = build_pipeline()
