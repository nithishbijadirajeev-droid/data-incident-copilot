import json, os, pathlib

def load_values():
    # Try WTH 068 settings file if present
    p = pathlib.Path(__file__).resolve().parents[1] / "Resources" / "ContosoAIAppsBackend" / "local.settings.json"
    vals = {}
    try:
        vals = json.loads(p.read_text()).get("Values", {})
    except Exception:
        vals = {}

    # Allow env to override
    vals = {
        **vals,
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT", vals.get("AZURE_OPENAI_ENDPOINT", "")),
        "AZURE_OPENAI_KEY": os.getenv("AZURE_OPENAI_KEY", vals.get("AZURE_OPENAI_KEY", "")),
        "AZURE_OPENAI_CHAT_DEPLOYMENT": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", vals.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "")),
    }
    return vals

def aoai_available():
    v = load_values()
    return bool(v.get("AZURE_OPENAI_ENDPOINT") and v.get("AZURE_OPENAI_KEY") and v.get("AZURE_OPENAI_CHAT_DEPLOYMENT"))
