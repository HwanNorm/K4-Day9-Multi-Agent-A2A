"""Thin wrapper around the Groq chat-completions API.

Every agent in this pipeline must declare a model with <=10B parameters (lab
constraint, see README section 9.1). Models are named here in code, not in
.env, per the same section.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# All models below are <=10B parameters.
MODEL_REASONING = "gemma2-9b-it"   # used by Policy Agent (needs rule reasoning)
MODEL_LIGHT = "gemma2-9b-it"       # used by lighter narration/explanation tasks


def call_llm(system_prompt: str, user_prompt: str, model: str, temperature: float = 0.0) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Add it to .env (see .env.example). "
            "Deterministic pipeline stages do not require it."
        )
    resp = requests.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
