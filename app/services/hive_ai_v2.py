# app/services/hive_ai.py
import json
from typing import Dict, List, Any
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
import os

env_path = Path("api/.env")
load_dotenv(dotenv_path=env_path)

client = OpenAI(base_url="https://api.thehive.ai/api/v3/", api_key=os.getenv("HIVE_AI_API_KEY"))

# Categories we want in our DB (you can add more later)
CATEGORIES = ["allergy", "liver", "pregnancy", "overdose", "driving_or_machinery", "cardiovascular", "other"]

def _warnings_prompt(warnings: List[str]) -> str:
    text = "\n\n".join([str(x) for x in warnings if x])
    return f"""
You are given FDA drug label warning text. Extract and rewrite side effects into short, plain-English sentences grouped by category.

Return ONLY valid JSON with this shape (no commentary):
{{
  "warnings_key": {{
    "allergy": [ "..." ],
    "liver": [ "..." ],
    "pregnancy": [ "..." ],
    "overdose": [ "..." ],
    "driving_or_machinery": [ "..." ],
    "cardiovascular": [ "..." ],
    "other": [ "..." ]
  }},
  "warnings_simple": [ "..." ]  // flat list of all sentences
}}

Rules:
- Do not invent effects; only use what appears.
- Normalize spacing; end each sentence with a period.
- Omit empty categories.
- Keep each sentence <= 180 chars, customer-friendly.
- If the text contains lists without punctuation, convert to comma-separated sentences.

SOURCE:
---
{text}
---
"""

async def summarize_warnings_to_keys(warnings: List[str]) -> Dict[str, Any]:
    if not warnings:
        return {"warnings_key": {}, "warnings_simple": []}

    resp = client.chat.completions.create(
        model="hive/vision-language-model",
        messages=[{"role": "user", "content": _warnings_prompt(warnings)}],
        temperature=0.2,
        max_tokens=1200,
    )
    raw = resp.choices[0].message.content.strip()
    try:
        data = json.loads(raw)
        wk = data.get("warnings_key") or {}
        ws = data.get("warnings_simple") or []
        # sanitize types
        wk = {k: [str(x).strip() for x in v if str(x).strip()] for k, v in wk.items() if isinstance(v, list)}
        ws = [str(x).strip() for x in ws if str(x).strip()]
        return {"warnings_key": wk, "warnings_simple": ws}
    except Exception:
        # fallback: nothing from Hive
        return {"warnings_key": {}, "warnings_simple": []}
