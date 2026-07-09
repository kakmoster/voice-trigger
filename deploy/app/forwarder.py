"""Forwarder: send a cleaned command phrase to Home Assistant Assist.

Uses the Home Assistant conversation API (REST). The LLM is intentionally
out of this path — Assist already understands entities, rooms and aliases.

Requires HA_URL and HA_TOKEN from config (env vars). No secrets hardcoded.
"""

import json
import urllib.request
import urllib.error

from config import HA_URL, HA_TOKEN


class AssistForwarder:
    """Sends a natural-language command to HA Assist and returns the reply."""

    def __init__(self, ha_url: str = None, ha_token: str = None):
        self.ha_url = (ha_url or HA_URL).rstrip("/")
        self.ha_token = ha_token or HA_TOKEN

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }

    def send(self, text: str, agent_id: str = None) -> dict:
        """Forward `text` to Assist. Returns the parsed JSON response.

        Raises RuntimeError if config is missing or the request fails.
        """
        if not self.ha_url or not self.ha_token:
            raise RuntimeError("HA_URL and HA_TOKEN must be set (env vars).")

        payload = {"text": text}
        if agent_id:
            payload["agent_id"] = agent_id

        url = f"{self.ha_url}/api/conversation/process"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers=self._headers(), method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HA Assist error {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Could not reach HA at {self.ha_url}: {e.reason}")

    def speech_response(self, text: str, agent_id: str = None) -> str | None:
        """Return the spoken reply text from Assist, if any."""
        result = self.send(text, agent_id)
        try:
            return result["response"]["speech"]["plain"]["speech"]
        except (KeyError, TypeError):
            return None
