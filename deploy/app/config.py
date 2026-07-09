"""Configuration surface for the always-listening HA voice trigger.

All secrets/config live in environment variables or a local .env file.
Nothing is hardcoded. The .env is loaded from (in order):
  1. $VOICE_TRIGGER_ENV (explicit override)
  2. ./secrets/.env next to this file
  3. ../../webapp-deployer/voice-trigger-config/secrets/.env (web UI output)

No secrets are ever written to code or committed.
"""

import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ if unset.

    Only sets variables that are not already present in the environment,
    so real env vars always win over the file.
    """
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _discover_env_paths():
    here = Path(__file__).resolve().parent
    candidates = []
    override = os.environ.get("VOICE_TRIGGER_ENV")
    if override:
        candidates.append(Path(override))
    candidates.append(here / ".env")
    candidates.append(here / "secrets" / ".env")
    # Web UI output location (voice-trigger-config lives under webapp-deployer)
    candidates.append(
        here / ".." / ".." / "webapp-deployer"
        / "voice-trigger-config" / "secrets" / ".env"
    )
    return candidates


for _p in _discover_env_paths():
    _load_env_file(_p)


# Home Assistant — long-lived access token (created in HA profile)
HA_URL = os.getenv("HA_URL", "")          # e.g. http://192.168.1.2:8123
HA_TOKEN = os.getenv("HA_TOKEN", "")      # long-lived access token

# Local LLM (Ollama) — used AFTER a trigger to interpret the spoken context
# into a clean command phrase that HA Assist understands. Not run on raw audio.
OLLAMA_URL = os.getenv("OLLAMA_URL", "")        # e.g. http://192.168.1.2:11434
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")    # optional, if Ollama has auth
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Audio capture settings (used by the capture layer, built later)
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
CHANNELS = int(os.getenv("CHANNELS", "1"))

# Trigger settings
TRIGGER_LANGUAGES = os.getenv("TRIGGER_LANGUAGES", "sv,en").split(",")
# How many recent transcript segments to keep as context for the LLM.
CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", "10"))


def is_configured() -> bool:
    """Return True only when the minimum required config is present."""
    return bool(HA_URL) and bool(HA_TOKEN)
