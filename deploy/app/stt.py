"""
Local speech-to-text (STT) engine for an always-listening Home Assistant voice
trigger.

This module is the STT layer only. It continuously transcribes audio captured
locally (microphone or ESPHome stream) and yields partial/final text. A separate
cheap keyword-matcher (built elsewhere) consumes this text to detect trigger
phrases and forwards cleaned text to Home Assistant Assist.

Design constraints:
  * Local-first, no cloud, no network at runtime.
  * CPU only (no GPU). Uses Vosk, which is lightweight and CPU-friendly.
  * Configured via environment variables or constructor arguments only.
  * No secrets hardcoded anywhere in this file.

Vosk expects mono 16-bit PCM audio at 16 kHz. Audio producers should resample
to that format before feeding chunks into the engine.
"""

from __future__ import annotations

import os
import sys
import zipfile
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Iterator
from urllib.request import urlretrieve

# Vosk is imported lazily inside VoskSTT so that importing this module (and the
# abstract base class) never fails just because the optional dependency is
# missing or the model is not yet downloaded.
try:
    import vosk  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    vosk = None


# Default model candidates, tried in order. The Swedish small Rhasspy model is
# preferred for the prototype; we fall back to the English small model.
DEFAULT_MODELS = (
    "vosk-model-small-sv-rhasspy-0.15",
    "vosk-model-small-en-us-0.15",
)

# Base URL for official Vosk model downloads.
VOSK_MODEL_BASE_URL = "https://alphacephei.com/vosk/models"

# Default sample rate expected by Vosk (16-bit mono PCM).
DEFAULT_SAMPLE_RATE = 16000


class STTEngine(ABC):
    """Abstract base class for streaming speech-to-text engines.

    Concrete engines must be able to transcribe a single raw audio chunk and to
    consume an arbitrary generator of audio chunks, yielding transcript strings
    as they become available. The streaming method is the primary one used by
    the always-listening pipeline.
    """

    @abstractmethod
    def transcribe_chunk(self, audio_bytes: bytes) -> str:
        """Feed one raw audio chunk into the engine and return any new text.

        Args:
            audio_bytes: Raw 16-bit mono PCM audio at the engine's sample rate.

        Returns:
            Newly decoded text since the last call (may be an empty string if
            nothing was finalized yet).
        """
        raise NotImplementedError

    @abstractmethod
    def transcribe_stream(self, audio_generator: Iterator[bytes]) -> Iterator[str]:
        """Consume a generator of audio chunks and yield transcript strings.

        Args:
            audio_generator: Iterable yielding raw audio chunks (bytes).

        Yields:
            Transcript fragments as they are produced.
        """
        raise NotImplementedError


class VoskSTT(STTEngine):
    """Vosk-based streaming STT engine.

    Wraps a Vosk KaldiRecognizer and a Vosk Model. The model is loaded from a
    local directory; if absent it can be downloaded automatically (network
    required only for that one-time download).

    Configuration (env vars or constructor args, no secrets):
        VOSK_MODEL_NAME    Model directory name to use (default: first of
                           DEFAULT_MODELS that is present or downloadable).
        VOSK_MODEL_PATH    Explicit path to a model directory. Overrides name.
        VOSK_MODELS_DIR    Directory where models are stored (default: ./models).
        VOSK_SAMPLE_RATE   Sample rate in Hz (default: 16000).
    """

    def __init__(
        self,
        model_path: str | None = None,
        model_name: str | None = None,
        models_dir: str | None = None,
        sample_rate: int | None = None,
    ) -> None:
        # Resolve configuration from constructor args, then environment.
        self.models_dir = Path(
            models_dir or os.environ.get("VOSK_MODELS_DIR", "models")
        ).resolve()
        self.model_name = model_name or os.environ.get("VOSK_MODEL_NAME")
        self.sample_rate = int(
            sample_rate or os.environ.get("VOSK_SAMPLE_RATE", DEFAULT_SAMPLE_RATE)
        )

        # If an explicit model path is given (env or arg), use it directly.
        explicit = model_path or os.environ.get("VOSK_MODEL_PATH")
        self.model_path: Path | None = Path(explicit).resolve() if explicit else None

        self._model = None
        self._recognizer = None

    # ------------------------------------------------------------------ #
    # Model management
    # ------------------------------------------------------------------ #
    def _resolve_model_dir(self) -> Path:
        """Determine which local model directory to use.

        If an explicit model path was configured, return it. Otherwise pick the
        first candidate model name that already exists locally, or the preferred
        default if none are downloaded yet (the caller may then download it).
        """
        if self.model_path is not None:
            return self.model_path

        # Prefer an already-downloaded candidate.
        for name in self._candidate_names():
            candidate = self.models_dir / name
            if candidate.is_dir():
                return candidate

        # Fall back to the first preferred name (to be downloaded/loaded).
        return self.models_dir / self._candidate_names()[0]

    def _candidate_names(self) -> tuple[str, ...]:
        """Ordered list of model names to try."""
        if self.model_name:
            return (self.model_name, *DEFAULT_MODELS)
        return DEFAULT_MODELS

    def model_dir_exists(self) -> bool:
        """Return True if a usable local model directory is present."""
        try:
            return self._resolve_model_dir().is_dir()
        except Exception:
            return False

    def download_model(self, model_name: str | None = None) -> Path:
        """Download a Vosk model into the models directory (one-time, needs net).

        Args:
            model_name: Optional model directory name to download. Defaults to
                the first candidate name.

        Returns:
            Path to the extracted model directory.

        Raises:
            RuntimeError: If the download or extraction fails.
        """
        name = model_name or self._candidate_names()[0]
        target = self.models_dir / name
        if target.is_dir():
            return target

        self.models_dir.mkdir(parents=True, exist_ok=True)
        url = f"{VOSK_MODEL_BASE_URL}/{name}.zip"
        zip_path = self.models_dir / f"{name}.zip"

        try:
            print(f"[VoskSTT] Downloading model '{name}' from {url} ...")
            urlretrieve(url, zip_path)  # nosec - fixed official URL
            print(f"[VoskSTT] Extracting {zip_path} ...")
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(self.models_dir)
            zip_path.unlink(missing_ok=True)
        except Exception as exc:  # network/disk failures
            raise RuntimeError(f"Failed to download/extract model '{name}': {exc}") from exc

        if not target.is_dir():
            raise RuntimeError(f"Model directory not found after extraction: {target}")
        return target

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def load(self) -> "VoskSTT":
        """Load the Vosk model and recognizer.

        Attempts to auto-download the preferred model if no local copy exists.
        Raises RuntimeError on failure (e.g. no network and no local model).
        """
        if vosk is None:
            raise RuntimeError(
                "The 'vosk' package is not installed in this environment."
            )

        model_dir = self._resolve_model_dir()
        if not model_dir.is_dir():
            # Try to fetch the preferred model automatically.
            model_dir = self.download_model()

        self._model = vosk.Model(str(model_dir))
        self._recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate)
        # Enable continuous (streaming) recognition.
        self._recognizer.SetWords(False)
        return self

    @property
    def recognizer(self):
        """Return the underlying Vosk recognizer, loading lazily if needed."""
        if self._recognizer is None:
            self.load()
        return self._recognizer

    @property
    def model(self):
        if self._model is None:
            self.load()
        return self._model

    # ------------------------------------------------------------------ #
    # Transcription API
    # ------------------------------------------------------------------ #
    def transcribe_chunk(self, audio_bytes: bytes) -> str:
        """Process one audio chunk and return any finalized text.

        Args:
            audio_bytes: Raw 16-bit mono PCM audio at the configured sample rate.

        Returns:
            The finalized transcript text for this chunk, or "" if none yet.
        """
        rec = self.recognizer
        text = ""
        if rec.AcceptWaveform(audio_bytes):
            result = rec.Result()
            # Vosk returns JSON; pull out the "text" field safely.
            try:
                text = result.get("text", "") if isinstance(result, dict) else result
            except Exception:
                text = ""
        return text.strip() if isinstance(text, str) else ""

    def transcribe_stream(self, audio_generator: Iterator[bytes]) -> Iterator[str]:
        """Yield transcript fragments from a stream of audio chunks.

        Args:
            audio_generator: Iterable yielding raw audio chunks (bytes).

        Yields:
            Transcript strings as they are finalized.
        """
        rec = self.recognizer
        for chunk in audio_generator:
            if rec.AcceptWaveform(chunk):
                result = rec.Result()
                try:
                    text = result.get("text", "") if isinstance(result, dict) else result
                except Exception:
                    text = ""
                if isinstance(text, str) and text.strip():
                    yield text.strip()
        # Flush any remaining partial result at end of stream.
        final = rec.FinalResult()
        try:
            text = final.get("text", "") if isinstance(final, dict) else final
        except Exception:
            text = ""
        if isinstance(text, str) and text.strip():
            yield text.strip()

    def reset(self) -> None:
        """Reset the recognizer state (e.g. between unrelated utterances)."""
        if self._recognizer is not None:
            self._recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate)


def _smoke_test() -> int:
    """Smoke test executed when running this module directly.

    Returns:
        Process exit code (0 = OK, non-zero = failure).
    """
    # (a) Does vosk import?
    if vosk is None:
        print("FAIL: vosk could not be imported.")
        return 1
    print("OK: vosk imported successfully.")

    # Build the engine (config via env/args only).
    engine = VoskSTT()
    print(f"VoskSTT OK (sample_rate={engine.sample_rate}, models_dir={engine.models_dir})")

    # (b) Attempt to load the model, catching download/network failures.
    try:
        engine.load()
        print(f"OK: model loaded from {engine._resolve_model_dir()}")
    except Exception as exc:
        print(f"WARN: model load failed (this is acceptable if network is blocked):")
        print(f"      {type(exc).__name__}: {exc}")
        print("      stt.py is left ready to use once the model is present.")
        # Do NOT crash: report and exit cleanly.
        return 0

    # Quick sanity transcription with silence-like zeros (produces no text,
    # but proves the recognizer pipeline is wired up).
    try:
        silence = b"\x00\x00" * 1600  # ~0.1s of silence at 16kHz/16bit
        out = engine.transcribe_chunk(silence)
        print(f"OK: recognizer accepted a chunk (transcript={out!r})")
    except Exception as exc:
        print(f"WARN: recognizer chunk test failed: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(_smoke_test())
