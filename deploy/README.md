# Deploy: Voice Trigger Docker Compose

One deployable package that runs the whole always-listening voice trigger
stack. Home Assistant and Ollama run **separately** on your LAN — this stack
only connects to them (you configure their URLs/tokens in the web UI).

## What it runs

| Service | Image | Port | Role |
|---------|-------|------|------|
| `app` | Python (Vosk STT + UDP capture + loop) | `5000/udp` | Listens to microphone audio, transcribes, triggers HA Assist |
| `webui` | PHP/Apache (settings UI) | `8080` | Configure HA URL/token + Ollama URL/token |

The web UI writes settings to a shared `secrets/.env` volume that the `app`
container reads at startup. No secrets are in code or images.

## Setup

```bash
cd deploy
cp .env.example ../secrets/.env     # or let the web UI create it
docker compose up -d --build
```

Open the settings UI at `http://<this-host>:8080/` and:

1. Enter **Home Assistant URL** (e.g. `http://192.168.1.2:8123`)
2. Enter a **long-lived access token** (HA → Profile → Long-lived tokens)
3. (Optional) Ollama URL + token
4. Click **Test HA connection** → should say `OK - HA reachable`
5. Click **Save**
6. Click **Restart / Reload App** to apply the new settings

The web UI (port 8080) also provides:

- **Restart / Reload App** — restarts the `app` container so new settings apply.
- **View Debug Log** — shows the `app` container's recent output (model
  download progress, STT errors, HA connection timeouts). Use it to see
  if anything goes wrong.

Both buttons call `docker compose` from inside the web UI container (the
host Docker socket is mounted read-only-ish into it).

## Hardware (audio source)

The `app` service listens on UDP port 5000 for raw 16 kHz mono PCM. Feed it
audio from any of:

- **ESPHome Respeaker Lite** — see [`../esphome_components/README.md`](../esphome_components/README.md)
  (sets a switch in HA to stream the mic constantly)
- **PC client** — run `pc_client.py` on a computer with a microphone

## Notes

- The Vosk model downloads once into the `models/` volume (~770 MB).
- `secrets/` is mounted read-only into `app` and blocked from web access in `webui`.
- Nothing is pushed to GitHub; all credentials stay in `secrets/.env`.
