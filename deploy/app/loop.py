"""Main loop: STT -> trigger-check -> forward to HA Assist.

This module wires the pieces together. It is intentionally thin:
- Audio capture (UDP from ESPHome) produces raw PCM
- STT transcribes it to text
- triggers.find_trigger() does the cheap keyword match
- forwarder.AssistForwarder sends the cleaned phrase to HA Assist

Run modes:
  python loop.py --replay transcript.txt   # validate trigger->forward without audio
  python loop.py --udp                      # live: UDP audio from ESPHome device

No LLM is used in this path.
"""

import argparse
import sys

from triggers import find_trigger
from forwarder import AssistForwarder


def process_segment(text: str, forwarder: AssistForwarder, verbose: bool = True):
    """Check one transcript segment for a trigger and forward if found.

    Returns True if a command was forwarded.
    """
    hit = find_trigger(text)
    if not hit:
        return False
    phrase, intent = hit
    if verbose:
        print(f"[trigger] '{phrase}' -> intent={intent}")
    # Forward the whole segment; Assist interprets the exact command.
    try:
        reply = forwarder.speech_response(text)
        if verbose:
            print(f"[assist] -> {reply}")
    except RuntimeError as e:
        # Config may be unset during early testing; report and continue.
        if verbose:
            print(f"[assist] skipped (not configured): {e}")
    return True


def run_replay(path: str, forwarder: AssistForwarder):
    """Replay a transcript file line-by-line to validate the flow."""
    print(f"[loop] replay mode: {path}")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                process_segment(line, forwarder)


def run_udp(forwarder: AssistForwarder):
    """Live mode: UDP audio from ESPHome -> STT -> trigger -> forward."""
    from stt import VoskSTT
    from capture import UDPAudioSource

    engine = VoskSTT()
    engine.load()  # download/load model up front; fail fast if unavailable
    source = UDPAudioSource()

    print("[loop] UDP live mode started")
    # Wrap the UDP byte stream into the STT streaming transcriber.
    audio_chunks = source.stream()
    for text in engine.transcribe_stream(audio_chunks):
        if text:
            process_segment(text, forwarder)


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
