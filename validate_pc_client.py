"""Validate pc_client.py without a real microphone or sounddevice.

Mocks `sounddevice` and `socket.sendto` to verify:
  - device listing works
  - 48 kHz input resamples to 16 kHz output at the right ratio
  - the callback would send UDP packets to the configured host/port
"""

import sys
import types
from unittest import mock


# --- Build a fake `sounddevice` module ---------------------------------------
fake_sd = types.ModuleType("sounddevice")


class FakeInputStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._running = False

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    def close(self):
        self._running = False


def fake_query_devices():
    return [
        {"name": "Default Input", "max_input_channels": 2, "default_samplerate": 48000.0},
        {"name": "USB Mic", "max_input_channels": 1, "default_samplerate": 44100.0},
        {"name": "Output Only", "max_input_channels": 0, "default_samplerate": 48000.0},
    ]


fake_sd.InputStream = FakeInputStream
fake_sd.query_devices = fake_query_devices

sys.modules["sounddevice"] = fake_sd

# --- Import the client (after the mock is in place) --------------------------
import pc_client
from pc_client import AudioStreamer


def main():
    failures = 0

    # 1) Device listing
    devs = AudioStreamer.list_devices()
    assert len(devs) == 2, f"expected 2 input devices, got {len(devs)}"
    assert devs[0]["index"] == 0 and devs[0]["name"] == "Default Input"
    assert devs[1]["index"] == 1 and devs[1]["name"] == "USB Mic"
    print(f"[1] device listing OK ({len(devs)} input devices)")

    # 2) Resampling ratio (48k -> 16k should be ~1/3 of samples)
    streamer = AudioStreamer("127.0.0.1", 5000, device_index=0, input_rate=48000)
    # Simulate 48000 mono int16 samples (= 1 second).
    import struct
    one_sec = [1000] * 48000
    raw = struct.pack(f"<{len(one_sec)}h", *one_sec)
    out = streamer._resample(one_sec)
    n_out = len(out) // 2
    # Allow +/- 2 samples of rounding error.
    assert abs(n_out - 16000) <= 2, f"resample gave {n_out}, expected ~16000"
    print(f"[2] resample 48k->16k OK ({n_out} samples from 48000)")

    # 3) Callback sends a UDP packet to the right address
    captured = {}

    class FakeSock:
        def sendto(self, data, addr):
            captured["data"] = data
            captured["addr"] = addr

    streamer._sock = FakeSock()

    # Build a fake stereo block (0.5s @ 48k, 2ch) of signal, as a minimal
    # stand-in for a numpy ndarray (sounddevice passes real ndarrays).
    frames = 24000
    data = [[0.01 * (i % 10) / 10, 0.01 * (i % 7) / 10] for i in range(frames)]

    class FakeArray:
        def __init__(self, rows):
            self._rows = rows
            self.shape = (len(rows), len(rows[0]) if rows else 0)

        def mean(self, axis=None):
            if axis == 1:
                return [sum(r) / len(r) for r in self._rows]
            return sum(sum(r) for r in self._rows) / (self.shape[0] * self.shape[1])

        def __getitem__(self, key):
            if isinstance(key, tuple):
                row_key, col_key = key
                if col_key == 0:
                    return [r[0] for r in self._rows]
            return self._rows[key]

    indata = FakeArray(data)
    streamer._running = True
    streamer._callback(indata, frames, None, None)
    assert "data" in captured, "no UDP packet was sent"
    assert captured["addr"] == ("127.0.0.1", 5000), f"wrong addr: {captured['addr']}"
    assert len(captured["data"]) > 0, "empty packet"
    # Packet length should be ~ 0.5s * 16000 = 8000 samples = 16000 bytes
    assert abs(len(captured["data"]) - 16000) < 100, (
        f"unexpected packet size {len(captured['data'])}"
    )
    print(f"[3] UDP send OK ({len(captured['data'])} bytes -> {captured['addr']})")

    # 4) Calling callback while not running sends nothing
    streamer._running = False
    captured.clear()
    streamer._callback(indata, frames, None, None)
    assert "data" not in captured, "sent data while stopped"
    print("[4] stopped-state guard OK (no packets when not running)")

    if failures == 0:
        print("\nALL CHECKS PASSED ✅")
    else:
        print(f"\n{failures} CHECK(S) FAILED ❌")
        sys.exit(1)


if __name__ == "__main__":
    main()
