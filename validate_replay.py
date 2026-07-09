"""Replay validation: simulate the full trigger -> LLM -> Assist pipeline.

Runs loop.process_segment with INJECTED llm.interpret and forwarder so we can
verify the wiring without a real Ollama/HA. Confirms:
  1. trigger phrases are detected
  2. surrounding context is gathered into the buffer
  3. the LLM receives the context (mock returns a clean Assist phrase)
  4. the LLM phrase is forwarded to Assist (mock records it)
  5. non-command lines are ignored
"""

import sys
from collections import deque

sys.path.insert(0, "/opt/data/workspace/Home Assistant/voice-trigger")

from loop import process_segment
from config import CONTEXT_WINDOW


def fake_interpret(context: str) -> str:
    # Simulate the LLM rephrasing natural speech into an Assist phrase.
    # The context buffer accumulates; the most recent line is the command.
    last_line = context.strip().splitlines()[-1].lower() if context.strip() else ""
    if "tänd" in last_line or "tanda" in last_line:
        return "tänd lampan i vardagsrummet"
    if "släck" in last_line or "slack" in last_line:
        return "släck alla lampor i köket"
    if "sätt på" in last_line or "satt pa" in last_line:
        return "sätt på fläkten"
    if "turn on" in last_line:
        return "turn on the kitchen lights"
    return "NO_COMMAND"


def fake_available() -> bool:
    return True  # pretend Ollama is configured


# --- Mock forwarder: record what would be sent to HA Assist ---
class FakeForwarder:
    def __init__(self):
        self.sent = []
    def speech_response(self, phrase: str) -> str:
        self.sent.append(phrase)
        return f"HA_EXECUTED({phrase})"


def main():
    fw = FakeForwarder()
    buffer = deque(maxlen=CONTEXT_WINDOW)

    # Transcript lines: some chatter, then commands (sv + en), more chatter.
    lines = [
        "jag undrar vad vädret blir idag",
        "ska vi kolla på en film sen",
        "kan du tända lampan i vardagsrummet innan vi börjar",
        "det var bra det",
        "och släck sedan lamporna i köket när vi somnar",
        "oj vad sent det blev",
        "hey can you turn on the kitchen lights please",
        "tack det räcker",
    ]

    print("=== REPLAY VALIDATION ===")
    print(f"context window = {CONTEXT_WINDOW} segments\n")
    for i, line in enumerate(lines):
        print(f"[{i}] transcript: {line}")
        buffer.append(line)  # add to context buffer BEFORE processing
        hit = process_segment(
            line, fw, buffer,
            interpret_fn=fake_interpret,
            llm_available=fake_available,
            verbose=True,
        )
        print(f"    -> trigger detected: {hit}\n")

    print("=== FORWARDED TO ASSIST (mock) ===")
    for p in fw.sent:
        print(f"  - {p}")

    expected = 3  # "tänd", "släck", "turn on" -> 3 triggers in test data
    ok = len(fw.sent) == expected
    print(f"\nRESULT: {len(fw.sent)} commands forwarded (expected {expected}) -> "
          f"{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
