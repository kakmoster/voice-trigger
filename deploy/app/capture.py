"""Audio capture layer: receive raw PCM audio over UDP from an ESPHome device.

The ESP32 (running a simple firmware) streams raw 16-bit mono PCM audio at
16 kHz over UDP. This module listens on a UDP port and yields fixed-size
chunks of raw audio bytes, ready to feed into the Vosk STT engine.

No PortAudio / sound device is required — audio arrives over the network,
which makes this ideal for an always-listening setup where the microphone
lives on a separate ESPHome device.

Configuration (env vars / constructor args, no secrets):
    UDP_LISTEN_HOST   Interface to bind (default: 0.0.0.0)
    UDP_LISTEN_PORT   UDP port to listen on (default: 5000)
    CHUNK_SAMPLES     Samples per emitted chunk (default: 1600 = 0.1s @16kHz)
"""

from __future__ import annotations

import os
import socket
from typing import Iterator


class Resampler:
    """Minimal linear-interpolation resampler for 16-bit mono PCM.

    Converts audio from one sample rate to another without external
    dependencies (no numpy/scipy). Good enough for speech; not for music.

    Feed raw 16-bit mono PCM bytes via :meth:`process`; pull resampled
    16-bit mono PCM bytes via iteration / :meth:`flush`.
    """

    def __init__(self, in_rate: int, out_rate: int) -> None:
        self.in_rate = in_rate
        self.out_rate = out_rate
        self.ratio = in_rate / out_rate
        self._pos = 0.0
        self._last = 0  # last sample (for interpolation)
        self._out = bytearray()

    def _to_samples(self, data: bytes) -> list[int]:
        import struct

        count = len(data) // 2
        return list(struct.unpack(f"<{count}h", data[: count * 2]))

    def _from_samples(self, samples: list[int]) -> bytes:
        import struct

        return struct.pack(f"<{len(samples)}h", *samples)

    def process(self, data: bytes) -> bytes:
        """Resample a chunk of 16-bit mono PCM and return available output."""
        samples = self._to_samples(data)
        out: list[int] = []
        for s in samples:
            self._pos += self.ratio
            if self._pos >= 1.0:
                # interpolate between last and current sample
                frac = self._pos - 1.0
                interp = int(self._last + (s - self._last) * (1.0 - frac))
                out.append(interp)
                self._last = s
                self._pos -= 1.0
        self._out.extend(self._from_samples(out))
        result = bytes(self._out)
        self._out.clear()
        return result

    def flush(self) -> bytes:
        return b""


class UDPAudioSource:
    """Yields raw PCM audio chunks received over UDP.

    Defaults to 16-bit mono PCM. If the source device streams at a higher
    rate (e.g. Respeaker Lite at 48 kHz), set ``src_rate`` so the audio is
    resampled down to the 16 kHz that Vosk expects.

    Configuration (env vars / constructor args, no secrets):
        UDP_LISTEN_HOST   Interface to bind (default: 0.0.0.0)
        UDP_LISTEN_PORT   UDP port to listen on (default: 5000)
        CHUNK_SAMPLES     Output samples per chunk (default: 1600 = 0.1s @16kHz)
        SRC_SAMPLE_RATE   Incoming rate (default: 16000; use 48000 for Respeaker)
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        chunk_samples: int | None = None,
        src_rate: int | None = None,
    ) -> None:
        self.host = host or os.environ.get("UDP_LISTEN_HOST", "0.0.0.0")
        self.port = int(port or os.environ.get("UDP_LISTEN_PORT", "5000"))
        self.chunk_samples = int(
            chunk_samples or os.environ.get("CHUNK_SAMPLES", "1600")
        )
        self.chunk_bytes = self.chunk_samples * 2  # 16-bit samples
        self.src_rate = int(
            src_rate or os.environ.get("SRC_SAMPLE_RATE", "16000")
        )
        self.resampler = (
            Resampler(self.src_rate, 16000) if self.src_rate != 16000 else None
        )
        self._sock: socket.socket | None = None

    def _open(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.settimeout(0.5)  # allow clean shutdown between reads

    def stream(self) -> Iterator[bytes]:
        """Yield fixed-size raw PCM chunks as UDP datagrams arrive."""
        if self._sock is None:
            self._open()
        assert self._sock is not None

        buffer = bytearray()
        mode = "16 kHz" if self.resampler is None else f"{self.src_rate} Hz -> 16 kHz"
        print(f"[capture] UDP listening on {self.host}:{self.port} ({mode})")
        try:
            while True:
                try:
                    data, _addr = self._sock.recvfrom(65535)
                except socket.timeout:
                    # No data yet; keep looping (cheap heartbeat).
                    if buffer:
                        # Emit whatever we have if the buffer is large enough.
                        if len(buffer) >= self.chunk_bytes:
                            yield bytes(buffer[: self.chunk_bytes])
                            del buffer[: self.chunk_bytes]
                    continue

                # Resample incoming audio if needed (e.g. 48k -> 16k).
                if self.resampler is not None:
                    data = self.resampler.process(data)

                buffer.extend(data)
                while len(buffer) >= self.chunk_bytes:
                    yield bytes(buffer[: self.chunk_bytes])
                    del buffer[: self.chunk_bytes]
        finally:
            self.close()

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
