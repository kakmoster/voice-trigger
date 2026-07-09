"""Trigger phrase definitions for the always-listening voice trigger.

The trigger-check is a CHEAP keyword match, NOT an LLM. When any phrase
here appears in the live transcript, the surrounding command text is
forwarded to Home Assistant Assist (conversation API).

Both Swedish and English are supported. Add/edit phrases freely.
Matching is case-insensitive substring on normalized (lowercased,
accent-stripped) transcript text.
"""

# Swedish and English trigger phrases.
# Each entry maps to a coarse intent label used only for logging/debug.
TRIGGER_PHRASES = {
    "tänd": "turn_on",
    "släck": "turn_off",
    "sätt på": "turn_on",
    "stäng av": "turn_off",
    "sätt": "set",
    "höj": "increase",
    "sänk": "decrease",
    "mörka": "cover_close",
    "dra för": "cover_close",
    "öppna": "cover_open",
    # English
    "turn on": "turn_on",
    "turn off": "turn_off",
    "switch on": "turn_on",
    "switch off": "turn_off",
    "set": "set",
    "increase": "increase",
    "raise": "increase",
    "lower": "decrease",
    "dim": "decrease",
    "close": "cover_close",
    "open": "cover_open",
}

# Phrases that explicitly mean "stop listening for now" (optional feature)
CANCEL_PHRASES = {
    "stoppa": "cancel",
    "stop": "cancel",
}


def normalize(text: str) -> str:
    """Lowercase and strip common Swedish accents for robust matching."""
    text = text.lower()
    replacements = {
        "ä": "a", "ö": "o", "å": "a",
        "Ä": "a", "Ö": "o", "Å": "a",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def find_trigger(transcript: str):
    """Return (phrase, intent) if a trigger phrase is present, else None.

    Longest match wins so 'sätt på' beats 'sätt'.
    Both the transcript and the phrase are normalized so accented
    Swedish characters match (e.g. 'tänd' matches 'tända').
    """
    norm = normalize(transcript)
    best = None
    for phrase, intent in TRIGGER_PHRASES.items():
        if normalize(phrase) in norm:
            if best is None or len(phrase) > len(best[0]):
                best = (phrase, intent)
    return best
