"""LLM interpretation: turn surrounding speech + trigger into a clean Assist phrase.

Uses a local Ollama instance (OLLAMA_URL, optional OLLAMA_TOKEN). The LLM
does NOT need to know Home Assistant entity names — it only rephrases the
user's natural speech into a command phrase that HA Assist can understand.

The LLM runs ONLY when a trigger phrase is detected, never on raw audio.
"""

import json
import urllib.request

from config import OLLAMA_URL, OLLAMA_TOKEN, OLLAMA_MODEL
from prompts import INTERPRET_SYSTEM_PROMPT


def interpret(context: str, model: str | None = None) -> str:
    """Send the transcript window to Ollama; return a clean command phrase.

    Raises RuntimeError if Ollama is not configured or the request fails.
    Returns the literal string "NO_COMMAND" if the model says so (caller
    should treat that as "ignore this trigger").
    """
    if not OLLAMA_URL:
        raise RuntimeError("OLLAMA_URL not configured")
    model = model or OLLAMA_MODEL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": INTERPRET_SYSTEM_PROMPT},
            {"role": "user", "content": f"TRANSCRIPT WINDOW:\n{context}"},
        ],
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if OLLAMA_TOKEN:
        headers["Authorization"] = f"Bearer {OLLAMA_TOKEN}"
    req = urllib.request.Request(
        OLLAMA_URL.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return data["message"]["content"].strip()


def is_available() -> bool:
    """True when Ollama is configured (URL set)."""
    return bool(OLLAMA_URL)
