"""
Tone analyzer: speech rate, filler words, hedging, confidence markers.
Pure text analysis from Whisper transcript + recording duration.
No audio processing libraries needed.
"""

import re
from dataclasses import dataclass
import numpy as np


FILLER_WORDS = {
    "um", "uh", "uhh", "umm", "like", "you know", "basically", "actually",
    "literally", "right", "okay", "so", "well", "kind of", "sort of", "i mean",
}

CONFIDENCE_WORDS = {
    "definitely", "certainly", "clearly", "absolutely", "confident", "sure",
    "exactly", "precisely", "specifically", "successfully", "achieved", "proven",
    "demonstrated", "led", "built", "created", "improved", "increased", "delivered",
}

HEDGE_WORDS = {
    "maybe", "perhaps", "might", "could", "possibly", "probably", "somewhat",
    "fairly", "i think", "i guess", "i believe", "i feel", "i suppose",
    "not sure", "kind of", "sort of", "a bit", "a little", "trying to",
    "attempting", "hoping", "might be",
}


@dataclass
class ToneAnalysis:
    speech_rate_wpm: float = 0.0
    filler_count: int = 0
    filler_ratio: float = 0.0
    hedge_count: int = 0
    hedge_ratio: float = 0.0
    confidence_count: int = 0
    total_words: int = 0
    duration_seconds: float = 0.0
    tone_label: str = "unknown"
    tone_score: float = 0.5  # 0=nervous, 1=confident
    tone_details: str = ""

    def to_dict(self) -> dict:
        return {
            "speech_rate_wpm": self.speech_rate_wpm,
            "filler_count": self.filler_count,
            "filler_ratio": self.filler_ratio,
            "hedge_count": self.hedge_count,
            "hedge_ratio": self.hedge_ratio,
            "confidence_count": self.confidence_count,
            "total_words": self.total_words,
            "duration_seconds": self.duration_seconds,
            "tone_label": self.tone_label,
            "tone_score": self.tone_score,
            "tone_details": self.tone_details,
        }

    def describe_for_llm(self) -> str:
        """Compact description for injection into AI evaluation prompt."""
        if self.tone_label == "insufficient data":
            return ""
        return (
            f"Vocal tone: {self.tone_label} (confidence: {self.tone_score:.0%}). "
            f"{self.tone_details}"
        )


def analyze_tone(transcript: str, duration_seconds: float) -> ToneAnalysis:
    """Analyze speaking tone from transcript text + recording duration."""
    if not transcript.strip() or duration_seconds < 1:
        return ToneAnalysis(tone_label="insufficient data", tone_details="No speech detected.")

    text_lower = transcript.lower()
    words = re.findall(r"\b\w+\b", text_lower)
    sentences = [s.strip() for s in re.split(r'[.!?]+', transcript.strip()) if s.strip()]

    total_words = len(words)
    if total_words == 0:
        return ToneAnalysis(tone_label="insufficient data")

    wpm = (total_words / duration_seconds) * 60

    filler_count = sum(
        len(re.findall(r'\b' + re.escape(fw) + r'\b', text_lower))
        for fw in FILLER_WORDS
    )
    filler_ratio = filler_count / total_words

    hedge_count = sum(
        len(re.findall(r'\b' + re.escape(hw) + r'\b', text_lower))
        for hw in HEDGE_WORDS
    )
    hedge_ratio = hedge_count / total_words

    conf_count = sum(
        len(re.findall(r'\b' + re.escape(cw) + r'\b', text_lower))
        for cw in CONFIDENCE_WORDS
    )

    # tone score: 0=nervous, 1=confident
    if 110 <= wpm <= 165:
        wpm_score = 1.0
    elif wpm < 110:
        wpm_score = max(0.0, wpm / 110)
    else:
        wpm_score = max(0.3, 1.0 - (wpm - 165) / 100)

    filler_penalty = min(0.5, filler_ratio * 8)
    hedge_penalty = min(0.4, hedge_ratio * 5)
    conf_bonus = min(0.2, (conf_count / total_words) * 4)

    tone_score = float(np.clip(wpm_score - filler_penalty - hedge_penalty + conf_bonus, 0.0, 1.0))

    # label
    if tone_score >= 0.78:
        label = "Confident & energetic" if wpm > 155 else "Calm & confident"
    elif tone_score >= 0.55:
        label = "Composed but hesitant" if hedge_ratio > 0.06 else "Steady & composed"
    elif tone_score >= 0.35:
        if filler_ratio > 0.05:
            label = "Nervous (many filler words)"
        elif wpm < 95:
            label = "Nervous (slow, halting pace)"
        else:
            label = "Slightly uncertain"
    else:
        label = "Very nervous / low confidence"

    # detail string
    details = []
    wpm_desc = "ideal" if 110 <= wpm <= 165 else ("too fast" if wpm > 165 else "slow")
    details.append(f"Speech rate: {wpm:.0f} wpm ({wpm_desc}).")
    if filler_count > 0:
        details.append(f"Filler words: {filler_count}x ({filler_ratio:.1%} of speech).")
    if hedge_count > 0:
        details.append(f"Hedging language: {hedge_count}x ({hedge_ratio:.1%}).")
    if conf_count > 0:
        details.append(f"Confidence markers: {conf_count}x.")

    return ToneAnalysis(
        speech_rate_wpm=round(wpm, 1),
        filler_count=filler_count,
        filler_ratio=round(filler_ratio, 4),
        hedge_count=hedge_count,
        hedge_ratio=round(hedge_ratio, 4),
        confidence_count=conf_count,
        total_words=total_words,
        duration_seconds=round(duration_seconds, 1),
        tone_label=label,
        tone_score=round(tone_score, 3),
        tone_details=" ".join(details),
    )
