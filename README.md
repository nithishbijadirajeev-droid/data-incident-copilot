# Data Incident Triage Copilot

An Agentic AI DataOps Copilot built in a Microsoft **What-The-Hack (WTH) 068** Codespace.  
It ingests pipeline run metrics (CSV), checks a simple contract, flags anomalies, scores severity,
and can optionally use **Azure OpenAI** to propose remediation steps.

## What it does
- Upload pipeline CSVs (sample files included)
- Validate required columns & basic types
- Detect issues (row drops, duration spikes, fail/null rates, cost surges)
- Severity scoring + incident summary
- (Optional) Azure OpenAI suggestions

## Run it
```bash
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
# Data Incident Copilot
An Agentic AI DataOps Copilot built with Microsoft WTH and Azure OpenAI Service.

## Quickstart
```bash
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
