# ESPHome: Respeaker Lite UDP streaming mode

Adds a **Switch** in Home Assistant that toggles the Seeed Studio Respeaker
Lite between:

| Switch state | Behavior |
|--------------|----------|
| **OFF** (default) | Normal Voice Assistant (wake-word) operation |
| **ON** | Constant microphone streaming to the voice-trigger server over UDP |

When streaming is ON, the device resamples its 48 kHz stereo / 32-bit mic
down to **16 kHz mono / 16-bit PCM** and sends raw packets to UDP port 5000
on the voice-trigger server.

## Files

| File | Purpose |
|------|---------|
| `udp_mic_stream/__init__.py` | ESPHome Python schema for the component |
| `udp_mic_stream/udp_mic_stream.h` | C++ header |
| `udp_mic_stream/udp_mic_stream.cpp` | C++ implementation (resample + UDP send) |
| `respeaker_streaming.yaml` | Switch + component wiring to include in your config |

## How to use

1. In your Respeaker satellite YAML (the one using
   `formatBCE/Respeaker-Lite-ESPHome-integration`), add this package:

   ```yaml
   packages:
     respeaker-streaming: github://kakmoster/voice-trigger/esphome_components/respeaker_streaming.yaml@main
   ```

   Or paste the contents of `respeaker_streaming.yaml` directly.

2. Edit `target_host` in `respeaker_streaming.yaml` to point at your
   voice-trigger server's LAN IP (where `loop.py --udp` / the Docker
   `app` service listens on UDP 5000).

3. Make sure the voice-trigger server is running and listening on UDP 5000.

4. Flash the device. A new **"Streaming mode"** switch appears in Home
   Assistant. Turn it ON to stream continuously; turn it OFF to return to
   normal Voice Assistant.

## Notes

- The component only sends audio while `streaming_mode` is ON. In OFF mode
  the device behaves exactly as the stock satellite (wake-word VA).
- Resampling is a simple linear-interpolation downmix; good enough for
  speech. For higher fidelity, swap in a better resampler.
- Requires ESPHome 2026.6.0+ (same `min_version` as the base satellite
  config).
