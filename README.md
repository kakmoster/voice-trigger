# Always-Listening HA Voice Trigger

> ⚠️ **ALPHA — DO NOT USE.**
> This project is highly experimental, incomplete, and not finished. It is
> shared only so it can be deployed directly with Docker for testing. It
> should **not** be used by anyone for anything real. No stability,
> security, or correctness is guaranteed.

## Quick start with Docker

```bash
git clone https://github.com/kakmoster/voice-trigger.git
cd voice-trigger/deploy
docker compose up -d --build
```

Then open the settings UI at `http://<host>:8080/` and:

1. Enter **Home Assistant URL** (e.g. `http://192.168.1.2:8123`)
2. Enter a **long-lived access token** (HA → Profile → Long-lived tokens)
3. (Optional) Ollama URL + token
4. Click **Test HA connection** → should say `OK - HA reachable`
5. Click **Save**
6. Click **Restart / Reload App** to apply the new settings

The web UI also has **View Debug Log** to see the app's output (model
download, STT errors, HA timeouts). Flash `esp32_udp_stream.ino` to an
ESP32-S3 with an INMP441 mic to stream audio to UDP port 5000.

See [`deploy/README.md`](deploy/README.md) for the full reference.

## How it works (end to end)

```
ESP32 mic (INMP441, I2S)
      |  raw 16 kHz mono PCM over UDP :5000
      v
capture.py  — receives UDP audio, emits fixed-size PCM chunks
      |
      v
stt.py (Vosk)  — transcribes chunks to text (Swedish small model)
      |
      v
loop.py  — feeds transcript into a rolling context buffer + trigger checker
      |
      |  trigger phrase found ("tänd", "släck", "turn on" ...)?
      v
llm.py (Ollama)  — sends the SURROUNDING speech context to a local LLM,
      |                which rephrases it into a clean command phrase that
      |                Home Assistant Assist understands. (LLM runs ONLY here,
      |                never on raw audio — cheap trigger gates it.)
      v
forwarder.py  — POSTs the LLM's phrase to HA Assist
      |
      v
Home Assistant  — Assist interprets the phrase and runs the action
                   (lights, fan, cover, climate ... it already knows entities)
```

**Why the LLM sits after the trigger, not before it:** a local LLM fast
enough to interpret free text in real time needs a GPU. By gating it behind
a cheap keyword trigger, the LLM only runs when the user likely said a
command, and only on a small transcript window — so the whole realtime path
stays on CPU. The LLM does not need to know entity names; it just rephrases
natural speech into something Assist can resolve.

## Components

| File | Role |
|------|------|
| `config.py` | Env-var config (HA_URL, HA_TOKEN, OLLAMA_URL/TOKEN/MODEL — all unset) |
| `capture.py` | UDP audio listener from the ESPHome/ESP32 device |
| `stt.py` | Vosk streaming STT engine (CPU-only, small SV model) |
| `triggers.py` | Trigger phrase list + `find_trigger()` (sv + en, accent-safe) |
| `llm.py` | Ollama client: interpret surrounding speech into an Assist phrase |
| `prompts.py` | Editable system prompt for the LLM interpreter |
| `forwarder.py` | Sends the LLM's phrase to HA Assist via REST |
| `loop.py` | Orchestrator: capture -> STT -> trigger -> LLM -> forward |
| `Dockerfile` | Container image (no local mic needed) |
| `pc_client.py` | PC desktop client: streams a PC microphone to the server over UDP (GUI) |
| `esp32_udp_stream.ino` | Reference firmware: ESP32 streams mic over UDP (legacy; prefer the ESPHome Respeaker setup) |

See also:

- **ESPHome / Respeaker Lite** streaming setup → [`esphome_components/README.md`](esphome_components/README.md)
- **PC client** (desktop microphone) → [`pc_client.md`](pc_client.md)

## Configuration (environment variables)

All secrets/config come from env vars. **Nothing is hardcoded.**

| Variable | Default | Purpose |
|----------|---------|---------|
| `HA_URL` | _(unset)_ | Home Assistant base URL, e.g. `http://192.168.1.2:8123` |
| `HA_TOKEN` | _(unset)_ | Long-lived access token (HA profile -> Long-lived tokens) |
| `OLLAMA_URL` | _(unset)_ | Local LLM endpoint; runs AFTER a trigger to interpret speech into an Assist phrase |
| `OLLAMA_TOKEN` | _(unset)_ | Optional, if Ollama requires auth |
| `OLLAMA_MODEL` | `llama3.2:3b` | Ollama model used for interpretation |
| `UDP_LISTEN_HOST` | `0.0.0.0` | UDP bind interface |
| `UDP_LISTEN_PORT` | `5000` | UDP port for ESP32 audio |
| `CHUNK_SAMPLES` | `1600` | Samples per emitted chunk (0.1 s @16 kHz) |
| `VOSK_MODEL_NAME` | first match | Override Vosk model (e.g. `vosk-model-small-en-us-0.15`) |
| `VOSK_MODELS_DIR` | `models` | Where models are stored |
| `VOSK_SAMPLE_RATE` | `16000` | Sample rate expected by Vosk |

## Run it

### 1. Replay mode (no hardware, validates the trigger -> forward flow)

```bash
cd "workspace/Home Assistant/voice-trigger"
.venv/bin/python loop.py --replay transcript.txt
```

Each line of `transcript.txt` is treated as one transcript segment; any
line containing a trigger phrase is forwarded (or reported as
"not configured" until HA creds are set).

### 2. Live mode (ESP32 streaming over UDP)

```bash
export HA_URL=http://192.168.1.2:8123
export HA_TOKEN=<long-lived-access-token>

cd "workspace/Home Assistant/voice-trigger"
.venv/bin/python loop.py --udp
```

Flash `esp32_udp_stream.ino` to an ESP32-S3 with an INMP441 mic, set
`WIFI_SSID`, `WIFI_PASSWORD` and `SERVER_IP` in the sketch, and it will
stream audio to port 5000.

### 3. Docker

```bash
cd "workspace/Home Assistant/voice-trigger"
docker build -t voice-trigger .
docker run -d --restart unless-stopped \
  -p 5000:5000/udp \
  -e HA_URL=http://192.168.1.2:8123 \
  -e HA_TOKEN=<long-lived-access-token> \
  voice-trigger
```

The Vosk model downloads automatically on first start (one-time, needs
network). To bake it into the image, uncomment the `RUN ... download_model()`
line in the Dockerfile.

## ESP32 firmware (reference)

`esp32_udp_stream.ino` reads an I2S MEMS mic (INMP441) at 16 kHz / 16-bit
mono and sends raw PCM to the server over UDP. Pin mapping:

```
INMP441   ESP32-S3
WS        GPIO 15
SCK       GPIO 14
SD        GPIO 13
L/R       GND   (selects left channel)
```

Set `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_IP` before flashing.

## Trigger phrases

Defined in `triggers.py`. Both Swedish and English are supported, with
accent normalization so "tänd" matches "tända". Longest match wins
("sätt på" beats "sätt"). Add or edit phrases freely.

## Status

- [x] Config surface (env vars, unset)
- [x] Trigger list (sv + en) with accent normalization
- [x] Forwarder to HA Assist (REST)
- [x] Replay validation (trigger flow verified)
- [x] STT module (Vosk small SV model, loads from disk)
- [x] UDP capture layer (`capture.py`) for ESPHome/ESP32 audio
- [x] Dockerfile (no local mic required)
- [x] ESP32 reference firmware (UDP stream)
- [ ] Live end-to-end test (requires HA_URL + HA_TOKEN + ESP32)

## Notes

- No secrets in code. All config via env vars.
- Public-facing docs/comments are in English.
- LLM (Ollama) runs AFTER a trigger to rephrase the spoken context into a
  phrase HA Assist understands. It is gated by the cheap keyword trigger, so
  it never processes raw audio.
- Local-first: no cloud STT/LLM in the realtime path.
