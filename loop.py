"""Main loop: STT -> trigger -> LLM interpret -> forward to HA Assist.

Pipeline:
  UDP audio (ESPHome) -> Vosk STT -> transcript segments
  On a trigger phrase: gather surrounding context -> Ollama interprets it
  into a clean command phrase -> forward that phrase to HA Assist.

The LLM runs ONLY when a trigger is detected (cheap keyword match), never on
raw audio. The LLM does not need to know entity names — Assist handles that.

Run modes:
  python loop.py --replay transcript.txt   # validate flow without audio
  python loop.py --udp                      # live: UDP audio from ESPHome device
"""

import argparse
import sys
from collections import deque

from triggers import find_trigger
from forwarder import AssistForwarder
from config import CONTEXT_WINDOW


def process_segment(
    text,
    forwarder,
    buffer,
    verbose=True,
    interpret_fn=None,
    llm_available=None,
):
    """Check one transcript segment for a trigger and act on it.

    On a trigger, the surrounding context (rolling buffer) is sent to the
    LLM, which returns a clean command phrase. That phrase is forwarded to
    HA Assist. If no LLM is configured/available, the raw text is forwarded.

    `interpret_fn` / `llm_available` default to the real Ollama client but
    can be injected (e.g. for tests).

    Returns True if a trigger was detected (regardless of outcome).
    """
    hit = find_trigger(text)
    if not hit:
        return False
    phrase, intent = hit
    if verbose:
        print(f"[trigger] '{phrase}' -> intent={intent}")

    # Surrounding speech = everything currently in the rolling buffer.
    context = "\n".join(list(buffer))

    # Resolve the LLM callables (default: real Ollama client).
    if interpret_fn is None or llm_available is None:
        from llm import interpret, is_available as _avail
        interpret_fn = interpret_fn or interpret
        llm_available = llm_available if llm_available is not None else _avail

    # Interpret with the LLM; fall back to raw text if Ollama is unavailable.
    command = text
    try:
        if llm_available():
            command = interpret_fn(context)
            if command == "NO_COMMAND":
                if verbose:
                    print("[llm] NO_COMMAND — ignoring")
                return True
            if verbose:
                print(f"[llm] -> {command}")
        else:
            if verbose:
                print("[llm] not configured — forwarding raw text")
    except Exception as e:  # Ollama down / bad response
        if verbose:
            print(f"[llm] error ({e}) — forwarding raw text")

    try:
        reply = forwarder.speech_response(command)
        if verbose:
            print(f"[assist] -> {reply}")
    except RuntimeError as e:
        # Config may be unset during early testing; report and continue.
        if verbose:
            print(f"[assist] skipped (not configured): {e}")
    return True


def run_replay(path, forwarder):
    """Replay a transcript file line-by-line to validate the flow."""
    print(f"[loop] replay mode: {path}")
    buffer = deque(maxlen=CONTEXT_WINDOW)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            buffer.append(line)
            process_segment(line, forwarder, buffer)


def run_udp(forwarder):
    """Live mode: UDP audio from ESPHome -> STT -> trigger -> LLM -> Assist."""
    from stt import VoskSTT
    from capture import UDPAudioSource

    engine = VoskSTT()
    engine.load()  # download/load model up front; fail fast if unavailable
    source = UDPAudioSource()

    buffer = deque(maxlen=CONTEXT_WINDOW)
    print("[loop] UDP live mode started")
    for text in engine.transcribe_stream(source.stream()):
        if not text:
            continue
        buffer.append(text)
        process_segment(text, forwarder, buffer)


def main():
    parser = argparse.ArgumentParser(description="Always-listening voice trigger loop")
    parser.add_argument("--replay", metavar="FILE", help="replay a transcript file")
    parser.add_argument("--udp", action="store_true", help="live UDP audio mode (ESPHome)")
    args = parser.parse_args()

    forwarder = AssistForwarder()

    if args.replay:
        run_replay(args.replay, forwarder)
    elif args.udp:
        run_udp(forwarder)
    else:
        print("Usage: python loop.py --replay FILE | --udp")
        sys.exit(1)


if __name__ == "__main__":
    main()
