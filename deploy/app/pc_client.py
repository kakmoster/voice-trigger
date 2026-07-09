"""PC client for the voice-trigger server.

Streams microphone audio over UDP to the voice-trigger server. The server
expects 16 kHz mono 16-bit PCM (the same format the ESPHome Respeaker
stream produces). This client captures from any local microphone,
resamples to 16 kHz, and sends raw PCM packets to the configured address.

No audio backend dependencies beyond `sounddevice` (PortAudio). The GUI
uses the standard library `tkinter`, which ships with Python on Windows.

Usage:
    python pc_client.py

Or import and use programmatically:
    from pc_client import AudioStreamer
    streamer = AudioStreamer("192.168.1.2", 5000, device_index=0)
    streamer.start()
"""

from __future__ import annotations

import socket
import struct
import threading
from typing import Optional

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - dependency check
    raise SystemExit(
        "Missing dependency: sounddevice\n"
        "Install it with:  pip install sounddevice\n"
        "(On Windows this also bundles PortAudio — no separate install needed.)"
    )

# Server-expected audio format
TARGET_RATE = 16000
TARGET_CHANNELS = 1
TARGET_WIDTH = 2  # bytes per sample (16-bit)
CHUNK_FRAMES = 8000  # ~0.5 s of input audio per callback; resampled below


class AudioStreamer:
    """Captures microphone audio and streams it to the server over UDP."""

    def __init__(
        self,
        host: str,
        port: int = 5000,
        device_index: Optional[int] = None,
        input_rate: int = 48000,
    ) -> None:
        self.host = host
        self.port = port
        self.device_index = device_index
        self.input_rate = input_rate
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._stream: Optional[sd.InputStream] = None
        self._running = False
        # Resampling state (linear interpolation 48k -> 16k).
        self._resample_pos = 0.0
        self._last_sample = 0

    @staticmethod
    def list_devices() -> list[dict]:
        """Return a list of available input devices."""
        devices = sd.query_devices()
        result = []
        for i, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                result.append(
                    {
                        "index": i,
                        "name": dev["name"],
                        "channels": dev["max_input_channels"],
                        "rate": int(dev.get("default_samplerate", 48000)),
                    }
                )
        return result

    def _resample(self, samples: list[int]) -> bytes:
        """Resample a list of 16-bit mono samples to TARGET_RATE."""
        out: list[int] = []
        ratio = TARGET_RATE / self.input_rate  # outputs per input sample
        for s in samples:
            self._resample_pos += ratio
            if self._resample_pos >= 1.0:
                frac = self._resample_pos - 1.0
                interp = int(
                    self._last_sample
                    + (s - self._last_sample) * (1.0 - frac)
                )
                out.append(interp)
                self._last_sample = s
                self._resample_pos -= 1.0
        return struct.pack(f"<{len(out)}h", *out)

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            # Status warnings (e.g. input overflow) — ignore gracefully.
            pass
        if not self._running:
            return
        # indata is float32 in [-1, 1]; convert to 16-bit PCM mono.
        # If stereo, downmix to mono by averaging channels.
        if indata.shape[1] > 1:
            mono = indata.mean(axis=1)
        else:
            mono = indata[:, 0]
        ints = [max(-32768, min(32767, int(s * 32767))) for s in mono]
        resampled = self._resample(ints)
        if resampled:
            try:
                self._sock.sendto(resampled, (self.host, self.port))
            except OSError:
                # Network error (e.g. unreachable) — keep trying.
                pass

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._resample_pos = 0.0
        self._last_sample = 0
        self._stream = sd.InputStream(
            device=self.device_index,
            samplerate=self.input_rate,
            channels=1,
            dtype="float32",
            blocksize=CHUNK_FRAMES,
            callback=self._callback,
        )
        self._stream.start()
        print(f"[pc_client] streaming -> {self.host}:{self.port} @16kHz mono")

    def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        print("[pc_client] stopped")

    @property
    def is_running(self) -> bool:
        return self._running


def _build_gui() -> None:
    """A minimal Tkinter GUI for the PC client."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("Voice Trigger — PC Microphone Client")
    root.resizable(False, False)

    # --- Server address ---
    ttk.Label(root, text="Server address").grid(
        row=0, column=0, padx=8, pady=4, sticky="w"
    )
    host_var = tk.StringVar(value="192.168.1.2")
    ttk.Entry(root, textvariable=host_var, width=20).grid(
        row=0, column=1, padx=8, pady=4
    )
    ttk.Label(root, text="Port").grid(row=0, column=2, padx=4, pady=4, sticky="w")
    port_var = tk.StringVar(value="5000")
    ttk.Entry(root, textvariable=port_var, width=7).grid(
        row=0, column=3, padx=8, pady=4
    )

    # --- Microphone selection ---
    ttk.Label(root, text="Microphone").grid(
        row=1, column=0, padx=8, pady=4, sticky="w"
    )
    devices = AudioStreamer.list_devices()
    if not devices:
        messagebox.showerror("No microphone", "No input devices found.")
        return
    device_names = [f"{d['index']}: {d['name']}" for d in devices]
    mic_var = tk.StringVar(value=device_names[0])
    ttk.Combobox(
        root, textvariable=mic_var, values=device_names, width=40, state="readonly"
    ).grid(row=1, column=1, columnspan=3, padx=8, pady=4)

    # --- Status ---
    status_var = tk.StringVar(value="Idle")
    ttk.Label(root, textvariable=status_var, foreground="gray").grid(
        row=2, column=0, columnspan=4, padx=8, pady=4
    )

    streamer: AudioStreamer | None = None

    def on_start():
        nonlocal streamer
        try:
            host = host_var.get().strip()
            port = int(port_var.get().strip())
            idx = int(mic_var.get().split(":")[0])
        except ValueError:
            messagebox.showerror("Invalid input", "Check host/port/microphone.")
            return
        dev = next((d for d in devices if d["index"] == idx), None)
        rate = dev["rate"] if dev else 48000
        streamer = AudioStreamer(host, port, device_index=idx, input_rate=rate)
        try:
            streamer.start()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Stream error", str(e))
            return
        status_var.set(f"Streaming to {host}:{port}")
        start_btn.config(state="disabled")
        stop_btn.config(state="normal")

    def on_stop():
        nonlocal streamer
        if streamer is not None:
            streamer.stop()
            streamer = None
        status_var.set("Idle")
        start_btn.config(state="normal")
        stop_btn.config(state="disabled")

    # --- Buttons ---
    start_btn = ttk.Button(root, text="Start streaming", command=on_start)
    start_btn.grid(row=3, column=1, padx=8, pady=8)
    stop_btn = ttk.Button(
        root, text="Stop", command=on_stop, state="disabled"
    )
    stop_btn.grid(row=3, column=2, padx=8, pady=8)

    root.protocol("WM_DELETE_WINDOW", lambda: (on_stop(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    _build_gui()
