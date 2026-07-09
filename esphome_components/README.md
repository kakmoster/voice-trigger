# ESPHome: Respeaker Lite UDP streaming mode

Adds a **Switch** in Home Assistant that toggles the Seeed Studio Respeaker
Lite between:

| Switch state | Behavior |
|--------------|----------|
| **OFF** (default) | Normal Voice Assistant (wake-word) operation |
| **ON** | Constant microphone streaming to the voice-trigger server over UDP |

When streaming is ON, the device downmixes its mic (48 kHz stereo / 32-bit)
to **16-bit mono** and sends raw PCM packets to UDP port 5000 on the
voice-trigger server, which resamples 48 kHz -> 16 kHz on its side.

## No custom firmware / component

This uses **only stock ESPHome components** (`udp` + `microphone.on_data`).
No external C++ code, no custom component to compile.

## How to use

### 1. Patch your base microphone (one-time)

In your Respeaker satellite YAML (the one using
`formatBCE/Respeaker-Lite-ESPHome-integration`), find the `microphone:`
block that defines `id: i2s_mics` and add an `on_data` trigger inside it:

```yaml
microphone:
  - platform: i2s_audio
    id: i2s_mics
    # ... existing settings (i2s_din_pin, sample_rate, etc.) ...
    on_data:
      then:
        - if:
            condition:
              switch.is_on: streaming_mode
            then:
              - udp.write:
                  id: udp_stream_hub
                  data: !lambda |-
                    std::vector<uint8_t> out;
                    const int16_t *s = reinterpret_cast<const int16_t*>(x.data());
                    size_t n = x.size() / sizeof(int16_t);
                    for (size_t i = 0; i < n; i += 2) {
                      int32_t mono = (int32_t)s[i] + (int32_t)s[i+1];
                      int16_t m = (int16_t)(mono / 2);
                      out.push_back((uint8_t)(m & 0xFF));
                      out.push_back((uint8_t)((m >> 8) & 0xFF));
                    }
                    return out;
```

### 2. Include the streaming package

Add this to your satellite YAML:

```yaml
packages:
  respeaker-streaming: github://kakmoster/voice-trigger/esphome_components/respeaker_streaming.yaml@main
```

Or paste the contents of `respeaker_streaming.yaml` directly (it defines
`udp:` + the `streaming_mode` switch).

### 3. Point at your server

Edit `target_host` — wait, there is no `target_host` in this version.
The `udp.write` in step 1 sends to the broadcast/default address. To target
a specific server IP, set `addresses:` under `udp:` in
`respeaker_streaming.yaml`:

```yaml
udp:
  id: udp_stream_hub
  addresses:
    - "192.168.1.2"   # <-- your voice-trigger server IP
```

### 4. Flash & use

Flash the device. A new **"Streaming mode"** switch appears in Home
Assistant. Turn it ON to stream continuously; turn it OFF to return to
normal Voice Assistant.

## Notes

- The device only sends audio while `streaming_mode` is ON. In OFF mode it
  behaves exactly as the stock satellite (wake-word VA).
- The server must be running and listening on UDP 5000 (see `loop.py --udp`
  or the Docker `app` service).
- The mic hardware still runs at 48 kHz; the server does the 48k -> 16k
  resampling. The `on_data` lambda only does stereo->mono + 32->16 bit
  normalization.
- Requires ESPHome 2026.6.0+ (same `min_version` as the base satellite).
