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


class UDPAudioSource:
    """Yields raw PCM audio chunks received over UDP.

    Each yielded chunk is `CHUNK_SAMPLES * 2` bytes of 16-bit mono PCM
    (2 bytes per sample). Partial datagrams are buffered until a full
    chunk is available.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        chunk_samples: int | None = None,
    ) -> None:
        self.host = host or os.environ.get("UDP_LISTEN_HOST", "0.0.0.0")
        self.port = int(port or os.environ.get("UDP_LISTEN_PORT", "5000"))
        self.chunk_samples = int(
            chunk_samples or os.environ.get("CHUNK_SAMPLES", "1600")
        )
        self.chunk_bytes = self.chunk_samples * 2  # 16-bit samples
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
        print(f"[capture] UDP listening on {self.host}:{self.port}")
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
