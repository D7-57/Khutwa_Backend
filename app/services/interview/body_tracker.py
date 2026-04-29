"""
Body language signal aggregator for interview sessions.

This module does NOT run MediaPipe directly — it receives pre-computed
signals (eye contact %, smile %, gesture names) from the WebSocket handler
that processes video frames, and aggregates them over the session.

This separation means:
  - The WebSocket handler runs MediaPipe on each frame → emits signals
  - This tracker accumulates those signals across the entire answer
  - The turn endpoint pulls the accumulated summary for AI evaluation
"""

from dataclasses import dataclass, field
from collections import deque
import threading


@dataclass
class BodyLanguageSummary:
    eye_contact_pct: float = 0.0
    smile_pct: float = 0.0
    frown_pct: float = 0.0
    hands_visible_pct: float = 0.0
    dominant_gesture: str = "none"
    gesture_counts: dict = field(default_factory=dict)
    frame_count: int = 0
    face_detected_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "eye_contact_pct": self.eye_contact_pct,
            "smile_pct": self.smile_pct,
            "frown_pct": self.frown_pct,
            "hands_visible_pct": self.hands_visible_pct,
            "dominant_gesture": self.dominant_gesture,
            "gesture_counts": self.gesture_counts,
            "frame_count": self.frame_count,
            "face_detected_pct": self.face_detected_pct,
        }

    def describe_for_llm(self) -> str:
        """Compact description for injection into AI evaluation prompt."""
        if self.frame_count < 5:
            return ""

        parts = []

        if self.face_detected_pct < 0.4:
            parts.append(f"Warning: face only detected {self.face_detected_pct:.0%} of frames.")

        ec = self.eye_contact_pct
        if ec > 0.72:
            parts.append(f"Strong eye contact ({ec:.0%}).")
        elif ec > 0.50:
            parts.append(f"Moderate eye contact ({ec:.0%}).")
        elif ec > 0.30:
            parts.append(f"Below-average eye contact ({ec:.0%}).")
        else:
            parts.append(f"Poor eye contact ({ec:.0%}).")

        sm = self.smile_pct
        if sm > 0.45:
            parts.append(f"Warm, positive expression (smile {sm:.0%}).")
        elif sm > 0.20:
            parts.append(f"Mild positive expression (smile {sm:.0%}).")
        else:
            parts.append(f"Mostly neutral expression (smile {sm:.0%}).")

        hv = self.hands_visible_pct
        if hv > 0.55:
            parts.append(f"Active gesturing ({hv:.0%} hands visible).")
        elif hv > 0.20:
            parts.append(f"Some hand gestures ({hv:.0%}).")
        else:
            parts.append(f"Minimal gesturing ({hv:.0%}).")

        if self.gesture_counts:
            sorted_g = sorted(self.gesture_counts.items(), key=lambda x: -x[1])[:3]
            g_str = ", ".join(f"'{g}' (x{c})" for g, c in sorted_g)
            parts.append(f"Gestures: {g_str}.")

        return " ".join(parts)


class BodyLanguageTracker:
    """
    Thread-safe accumulator for body language signals.

    The WebSocket pushes signals per-frame via `record_frame()`.
    The turn endpoint calls `get_summary()` to pull aggregated data,
    then `reset()` to start fresh for the next question.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._frames = 0
        self._face_frames = 0
        self._sum_eye = 0.0
        self._sum_smile = 0.0
        self._sum_frown = 0.0
        self._sum_hands = 0.0
        self._gestures: dict[str, int] = {}

    def record_frame(
        self,
        eye_contact: float = 0.0,
        smile: float = 0.0,
        frown: float = 0.0,
        hands_visible: bool = False,
        face_detected: bool = False,
        gesture: str = "none",
    ):
        """Called by WebSocket handler for each processed frame."""
        with self._lock:
            self._frames += 1
            if face_detected:
                self._face_frames += 1
                self._sum_eye += eye_contact
                self._sum_smile += smile
                self._sum_frown += frown
            if hands_visible:
                self._sum_hands += 1.0
            if gesture and gesture != "none":
                self._gestures[gesture] = self._gestures.get(gesture, 0) + 1

    def get_summary(self) -> BodyLanguageSummary:
        """Get aggregated summary. Safe to call from any thread."""
        with self._lock:
            n = self._frames
            nf = self._face_frames
            if n == 0:
                return BodyLanguageSummary()

            def safe_mean(s, d):
                return round(s / d, 3) if d > 0 else 0.0

            gestures = dict(self._gestures)
            dominant = max(gestures, key=gestures.get) if gestures else "none"

            return BodyLanguageSummary(
                eye_contact_pct=safe_mean(self._sum_eye, nf),
                smile_pct=safe_mean(self._sum_smile, nf),
                frown_pct=safe_mean(self._sum_frown, nf),
                hands_visible_pct=safe_mean(self._sum_hands, n),
                dominant_gesture=dominant,
                gesture_counts=gestures,
                frame_count=n,
                face_detected_pct=safe_mean(nf, n),
            )

    def reset(self):
        """Reset for the next question. Called after turn evaluation."""
        with self._lock:
            self._frames = 0
            self._face_frames = 0
            self._sum_eye = 0.0
            self._sum_smile = 0.0
            self._sum_frown = 0.0
            self._sum_hands = 0.0
            self._gestures.clear()


# ── In-memory session tracker registry ──
# Maps session_id (str) → BodyLanguageTracker
# Created when session starts with mode=video, destroyed on session end

_session_trackers: dict[str, BodyLanguageTracker] = {}


def get_tracker(session_id: str) -> BodyLanguageTracker | None:
    return _session_trackers.get(session_id)


def create_tracker(session_id: str) -> BodyLanguageTracker:
    tracker = BodyLanguageTracker()
    _session_trackers[session_id] = tracker
    return tracker


def remove_tracker(session_id: str):
    _session_trackers.pop(session_id, None)
