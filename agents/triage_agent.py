import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from utils.config import load_values, aoai_available

# ---------- Perception ----------
def load_metrics_from_df(df: pd.DataFrame) -> Dict[str, float]:
    """
    Expect columns like:
      timestamp, pipeline, run_id, duration_min, rows_in, rows_out, fail_rate, null_rate, cost_usd
    Only some are required; missing ones default to NaN and won't trigger rules.
    """
    agg = {}
    for col in ["duration_min","rows_in","rows_out","fail_rate","null_rate","cost_usd"]:
        if col in df.columns:
            # last 6 runs mean and last run value
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) > 0:
                agg[f"{col}_mean"] = float(series.tail(6).mean())
                agg[f"{col}_p95"]  = float(series.tail(20).quantile(0.95)) if len(series) >= 20 else float(series.max())
                agg[f"{col}_last"] = float(series.iloc[-1])
    return agg

# ---------- Reasoning (rule-based) ----------
def score_incident(agg: Dict[str, float]) -> Tuple[str, int, List[str]]:
    """
    Return (severity_label, score, findings[])
    """
    score = 0
    findings = []

    def bump(points, msg):
        nonlocal score
        score += points
        findings.append(msg)

    # rules
    if "fail_rate_last" in agg and agg["fail_rate_last"] > 0.05:
        bump(3, f"High failure rate: {agg['fail_rate_last']:.2%}")

    if all(k in agg for k in ["rows_out_last","rows_out_mean"]) and agg["rows_out_last"] < 0.6 * agg["rows_out_mean"]:
        bump(3, f"Rows out dropped vs mean: {agg['rows_out_last']:.0f} < 60% of {agg['rows_out_mean']:.0f}")

    if "null_rate_last" in agg and agg["null_rate_last"] > 0.10:
        bump(2, f"High null rate: {agg['null_rate_last']:.2%}")

    if all(k in agg for k in ["duration_min_last","duration_min_p95"]) and agg["duration_min_last"] > 1.3 * agg["duration_min_p95"]:
        bump(2, f"Run duration spiked beyond p95: {agg['duration_min_last']:.1f}m")

    if all(k in agg for k in ["cost_usd_last","cost_usd_mean"]) and agg["cost_usd_last"] > 1.5 * agg["cost_usd_mean"]:
        bump(1, f"Cost spike vs mean: ${agg['cost_usd_last']:.2f}")

    if score >= 6: sev = "HIGH"
    elif score >= 3: sev = "MEDIUM"
    else: sev = "LOW"
    return sev, score, findings

# ---------- Action ----------
BASE_PLAYBOOK = [
    "Pause downstream consumers for this pipeline until validated.",
    "Re-run latest job with DEBUG logging on a small sample.",
    "Validate upstream source schema (columns added/removed/changed).",
    "Check recent deployment changes (last 24–48h) affecting this pipeline.",
    "Backfill missing partitions once root cause is fixed."
]

def recommend_actions(severity: str, findings: List[str]) -> List[str]:
    actions = []
    if severity == "HIGH":
        actions.append("SEV-1 bridge: page on-call DataOps immediately.")
    if any("schema" in f.lower() for f in findings):
        actions.append("Run automated schema diff against baseline; enforce contracts.")
    if any("null rate" in f.lower() for f in findings):
        actions.append("Quarantine affected rows; add NULL handling or source fix.")
    if any("rows out dropped" in f.lower() for f in findings):
        actions.append("Check filters/joins; verify late-arriving data and partition pruning.")
    if any("failure rate" in f.lower() for f in findings):
        actions.append("Open error logs; identify predominant exception signature.")
    if any("duration" in f.lower() or "cost" in f.lower() for f in findings):
        actions.append("Review cluster/warehouse sizing; consider off-peak scheduling.")
    # merge with base playbook but keep unique order
    seen = set()
    merged = []
    for step in actions + BASE_PLAYBOOK:
        key = step.lower()
        if key not in seen:
            seen.add(key)
            merged.append(step)
    return merged

def make_ticket_payload(pipeline: str, severity: str, findings: List[str], actions: List[str]) -> Dict[str, Any]:
    title = f"[{severity}] Data incident in pipeline: {pipeline}"
    body = {
        "summary": title,
        "description": "\n".join([
            f"Severity: {severity}",
            "",
            "Findings:",
            *[f"- {f}" for f in findings],
            "",
            "Recommended actions:",
            *[f"- {a}" for a in actions]
        ]),
        "labels": ["dataops","incident","agentic"],
        "priority": {"HIGH":"P1","MEDIUM":"P2","LOW":"P3"}[severity]
    }
    return body

# ---------- Optional AOAI narrative ----------
def aoai_narrative(pipeline: str, severity: str, findings: List[str], actions: List[str]) -> str:
    if not aoai_available():
        return "Azure OpenAI not configured."
    from openai import AzureOpenAI
    vals = load_values()
    client = AzureOpenAI(
        api_key=vals["AZURE_OPENAI_KEY"],
        azure_endpoint=vals["AZURE_OPENAI_ENDPOINT"],
        api_version="2024-05-01-preview",
    )
    prompt = f"""
You are a DataOps incident commander. Create a concise incident summary and a 6-step runbook.

Pipeline: {pipeline}
Severity: {severity}
Key findings:
- {"\n- ".join(findings) if findings else "None"}

Recommended actions:
- {"\n- ".join(actions) if actions else "None"}

Rules:
- Summary first (3-4 lines, no fluff).
- Then 'Runbook:' with 6 numbered, imperative steps (short).
- End with 'Exit criteria:' (2 bullets).
"""
    resp = client.chat.completions.create(
        model=vals["AZURE_OPENAI_CHAT_DEPLOYMENT"],
        messages=[
            {"role":"system","content":"You are concise, operational, and pragmatic."},
            {"role":"user","content":prompt}
        ],
        temperature=0.2
    )
    return resp.choices[0].message.content.strip()
