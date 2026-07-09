# PC Client

A simple desktop app that streams your computer's microphone to the
voice-trigger server over UDP. Useful for testing the full pipeline without
any ESP32/Respeaker hardware, or as a permanent always-listening client on
a PC near where you talk.

## Features

- Minimal GUI (Tkinter — ships with Python on Windows/macOS/Linux)
- Pick the server address (IP + port, default `5000`)
- Pick which microphone to use (auto-detects all input devices)
- Start / stop streaming with one click
- Resamples the mic to **16 kHz mono 16-bit PCM** (same format the server
  expects from the ESPHome Respeaker stream)

## Install

```bash
pip install sounddevice
```

(`tkinter` is part of standard Python on Windows and macOS. On Linux you may
need `sudo apt install python3-tk` if it is missing.)

## Run

```bash
python pc_client.py
```

1. Enter the server IP (where `loop.py --udp` / the Docker `app` runs).
2. Select your microphone from the dropdown.
3. Click **Start streaming**.
4. Talk — the server will detect triggers, interpret with the LLM, and
   forward commands to Home Assistant Assist.

## Notes

- The client sends raw PCM to UDP `port` (default 5000). Make sure the
  server is listening on that port and that the firewall allows it.
- Audio is resampled on the PC side (linear interpolation), so the server
  receives ready-to-use 16 kHz mono data.
- No audio is sent anywhere except the configured server address.
