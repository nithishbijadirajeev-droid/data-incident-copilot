import streamlit as st
import pandas as pd
from io import StringIO
from agents.triage_agent import (
    load_metrics_from_df, score_incident,
    recommend_actions, make_ticket_payload,
    aoai_narrative
)
from utils.config import aoai_available

st.set_page_config(page_title="Data Incident Triage Copilot", page_icon="��️", layout="wide")

st.markdown(
    """
    <div style="background:linear-gradient(90deg,#0a66c2 0%,#33a3ff 100%);
                padding:16px;border-radius:14px;color:white;margin-bottom:12px;">
      <h2 style="margin:0;">🛠️ Data Incident Triage Copilot</h2>
      <p style="margin:4px 0 0;">Agentic AI for pipeline anomaly detection, severity, and actioning</p>
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar:
    st.subheader("Agent status")
    st.write("Perception: CSV/JSON metrics")
    st.write("Reasoning: Rule-based scoring")
    st.write("Action: Recommendations + ticket payload")
    st.write(f"AOAI available: {'✅' if aoai_available() else '❌'}")

tab1, tab2, tab3 = st.tabs(["Upload Metrics", "Agent Output", "Ticket"])

# ---- Tab 1: Upload ----
with tab1:
    st.subheader("Upload pipeline metrics")
    st.caption("CSV should include columns like: timestamp, pipeline, run_id, duration_min, rows_in, rows_out, fail_rate, null_rate, cost_usd")
    f = st.file_uploader("Upload CSV", type=["csv"])
    raw_df = None
    if f:
        s = f.read().decode("utf-8")
        raw_df = pd.read_csv(StringIO(s))
        st.dataframe(raw_df.head())

    pipeline_name = st.text_input("Pipeline name (for ticket/use)", value="orders_etl")

    if st.button("Run Agent", type="primary", disabled=(raw_df is None)):
        with st.spinner("Agent analyzing metrics..."):
            agg = load_metrics_from_df(raw_df)
            sev, score, findings = score_incident(agg)
            actions = recommend_actions(sev, findings)
            st.session_state["result"] = {
                "pipeline": pipeline_name,
                "agg": agg,
                "severity": sev,
                "score": score,
                "findings": findings,
                "actions": actions
            }
        st.success("Analysis complete. See Agent Output.")

# ---- Tab 2: Output ----
with tab2:
    st.subheader("Agent Output")
    res = st.session_state.get("result")
    if not res:
        st.info("Upload metrics and click Run Agent.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Severity", res["severity"])
        with c2: st.metric("Score", res["score"])
        with c3: st.metric("Findings", len(res["findings"]))
        st.write("### Findings")
        if res["findings"]:
            for fnd in res["findings"]:
                st.write(f"- {fnd}")
        else:
            st.write("_No major issues detected._")

        st.write("### Recommended actions")
        for a in res["actions"]:
            st.write(f"- {a}")

        if aoai_available():
            if st.button("🤖 Generate AOAI summary & runbook"):
                txt = aoai_narrative(res["pipeline"], res["severity"], res["findings"], res["actions"])
                st.write("### AI Narrative")
                st.markdown(txt)
        else:
            st.caption("Tip: Set AZURE_OPENAI_* to enable AI narratives.")

# ---- Tab 3: Ticket ----
with tab3:
    st.subheader("Ticket Payload (copy/paste to Jira/ServiceNow)")
    res = st.session_state.get("result")
    if not res:
        st.info("Run the agent first.")
    else:
        payload = make_ticket_payload(res["pipeline"], res["severity"], res["findings"], res["actions"])
        st.code(payload, language="json")
