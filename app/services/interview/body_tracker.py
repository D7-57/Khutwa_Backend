"""
body_tracker.py — Server-side MediaPipe body language tracking.

Receives base64-encoded JPEG frames over WebSocket, runs MediaPipe Face Landmarker
+ Gesture Recognizer locally, computes signals (eye contact, smile, gestures),
and aggregates them per session.

Architecture:
    Frontend (Flutter web/mobile)
        ↓  base64 JPEG frame @ ~5fps via WebSocket
    body_tracker.process_frame()
        ↓  MediaPipe inference (CPU)
    BodyLanguageTracker (per-session registry)
        ↓  EMA + cumulative mean
    Turn endpoint: tracker.get_summary() → injected into LLM prompt + stored in attempt

The registry API (get/create/remove_tracker) is kept identical to v1
so the router code doesn't need to change.
"""

from __future__ import annotations

import base64
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.core.base_options import BaseOptions


# ─────────────────────────────────────────
#  MODEL LOADING
# ─────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parents[2]  # → app/
MODELS_DIR = BASE_DIR / "models"

_face_landmarker: mp_vision.FaceLandmarker | None = None
_gesture_recognizer: mp_vision.GestureRecognizer | None = None
_models_loaded = False
_models_load_error: str | None = None


def _load_models_lazy():
    """Load MediaPipe models on first use (avoids startup delay if no video sessions)."""
    global _face_landmarker, _gesture_recognizer, _models_loaded, _models_load_error
    if _models_loaded:
        return
    try:
        face_p = MODELS_DIR / "face_landmarker.task"
        gest_p = MODELS_DIR / "gesture_recognizer.task"
        if not face_p.exists() or not gest_p.exists():
            _models_load_error = (
                f"MediaPipe models not found at {MODELS_DIR}. "
                f"Run: python download_models.py"
            )
            print(f"[BodyTracker] {_models_load_error}", file=sys.stderr)
            return

        _face_landmarker = mp_vision.FaceLandmarker.create_from_options(
            mp_vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(face_p)),
                running_mode=mp_vision.RunningMode.IMAGE,
                num_faces=1,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=False,
                min_face_detection_confidence=0.4,
                min_face_presence_confidence=0.4,
                min_tracking_confidence=0.4,
            )
        )
        _gesture_recognizer = mp_vision.GestureRecognizer.create_from_options(
            mp_vision.GestureRecognizerOptions(
                base_options=BaseOptions(model_asset_path=str(gest_p)),
                running_mode=mp_vision.RunningMode.IMAGE,
                num_hands=2,
                min_hand_detection_confidence=0.4,
                min_hand_presence_confidence=0.4,
                min_tracking_confidence=0.4,
            )
        )
        _models_loaded = True
        print("[BodyTracker] MediaPipe models loaded successfully", file=sys.stderr)
    except Exception as e:
        _models_load_error = str(e)
        print(f"[BodyTracker] Model load failed: {e}", file=sys.stderr)


# ─────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────

GAZE_KEYS = ["eyeLookOutLeft", "eyeLookInLeft", "eyeLookOutRight", "eyeLookInRight",
             "eyeLookUpLeft", "eyeLookUpRight", "eyeLookDownLeft", "eyeLookDownRight"]
SMILE_KEYS = ["mouthSmileLeft", "mouthSmileRight"]
FROWN_KEYS = ["mouthFrownLeft", "mouthFrownRight"]
BROW_UP_KEYS = ["browInnerUp", "browOuterUpLeft", "browOuterUpRight"]

FINGER_TIPS = [4, 8, 12, 16, 20]
FINGER_PIPS = [3, 6, 10, 14, 18]
WRIST = 0
_ALL_TIPS = [4, 8, 12, 16, 20]
_ALL_MCPS = [5, 9, 13, 17]


# ─────────────────────────────────────────
#  DATA CLASSES
# ─────────────────────────────────────────

@dataclass
class FrameSignals:
    eye_contact: float = 0.0
    smile: float = 0.0
    frown: float = 0.0
    brow_raise: float = 0.0
    hands_up: bool = False
    raw_gesture: str = "none"
    custom_gesture: str = "none"
    face_found: bool = False
    hand_count: int = 0


@dataclass
class BodyLanguageSummary:
    """Aggregated summary returned to the router for storage + LLM prompt."""
    # Live EMA values (for client UI bars)
    eye_contact_live: float = 0.0
    smile_live: float = 0.0
    frown_live: float = 0.0
    brow_raise_live: float = 0.0
    hands_visible_live: float = 0.0
    # Cumulative means (used by LLM)
    eye_contact_pct: float = 0.0   # alias for eye_contact_mean — used by feedback page
    smile_pct: float = 0.0
    frown_pct: float = 0.0
    hands_visible_pct: float = 0.0
    # Gesture history
    gesture_history: dict = field(default_factory=dict)
    custom_gesture_history: dict = field(default_factory=dict)
    dominant_gesture: str = "none"
    dominant_custom: str = "none"
    # Meta
    frame_count: int = 0
    face_detected_pct: float = 0.0
    is_web_fallback: bool = False  # always False in this version — server-side ML works on web too

    def to_dict(self) -> dict:
        return {
            "eye_contact_pct": self.eye_contact_pct,
            "smile_pct": self.smile_pct,
            "frown_pct": self.frown_pct,
            "hands_visible_pct": self.hands_visible_pct,
            "eye_contact_live": self.eye_contact_live,
            "smile_live": self.smile_live,
            "hands_visible_live": self.hands_visible_live,
            "gesture_history": self.gesture_history,
            "custom_gesture_history": self.custom_gesture_history,
            "dominant_gesture": self.dominant_gesture,
            "dominant_custom": self.dominant_custom,
            "frame_count": self.frame_count,
            "face_detected_pct": self.face_detected_pct,
            "is_web_fallback": False,
        }

    def describe_for_llm(self) -> str:
        """Compact description for injection into AI evaluation prompt."""
        if self.frame_count < 5:
            return ""

        parts = []

        if self.face_detected_pct < 0.4:
            parts.append(f"⚠ Face only detected {self.face_detected_pct:.0%} of frames — camera positioning may be off.")

        ec = self.eye_contact_pct
        if ec > 0.72:
            parts.append(f"Strong eye contact ({ec:.0%}).")
        elif ec > 0.50:
            parts.append(f"Moderate eye contact ({ec:.0%}).")
        elif ec > 0.30:
            parts.append(f"Below-average eye contact ({ec:.0%}).")
        elif ec > 0.01:
            parts.append(f"Poor eye contact ({ec:.0%}).")

        sm = self.smile_pct
        if sm > 0.45:
            parts.append(f"Warm, positive expression (smile {sm:.0%}).")
        elif sm > 0.20:
            parts.append(f"Mild positive expression (smile {sm:.0%}).")
        elif sm > 0.01:
            parts.append(f"Mostly neutral expression (smile {sm:.0%}).")

        hv = self.hands_visible_pct
        if hv > 0.55:
            parts.append(f"Active gesturing — hands visible {hv:.0%} of the time.")
        elif hv > 0.20:
            parts.append(f"Some hand gestures used ({hv:.0%}).")
        elif hv > 0.01:
            parts.append(f"Minimal gesturing ({hv:.0%}).")

        if self.custom_gesture_history:
            sorted_custom = sorted(self.custom_gesture_history.items(), key=lambda x: -x[1])
            gesture_strs = [f"'{g}' (×{c})" for g, c in sorted_custom[:4]]
            parts.append(f"Purposeful gestures: {', '.join(gesture_strs)}.")

        notable = {k: v for k, v in self.gesture_history.items()
                   if k not in ("None", "Open_Palm") and v >= 3}
        if notable:
            sorted_n = sorted(notable.items(), key=lambda x: -x[1])
            parts.append(f"Built-in gestures: {', '.join(f'{g}(×{c})' for g, c in sorted_n[:3])}.")

        return " ".join(parts)


# ─────────────────────────────────────────
#  TRACKER (per session)
# ─────────────────────────────────────────

class BodyLanguageTracker:
    """
    Per-session body-language state.

    Two parallel aggregations:
      - EMA (exponential moving average) → smooth live values for UI bars
      - Cumulative mean (face-detected frames only) → reported to LLM
    """

    def __init__(self, ema_alpha: float = 0.15):
        self._alpha = ema_alpha

        # EMA live values
        self._ema_eye = 0.5
        self._ema_smile = 0.3
        self._ema_frown = 0.0
        self._ema_brow = 0.0
        self._ema_hands = 0.0

        # Cumulative sums (only counted when face found, except hands)
        self._sum_eye = 0.0;   self._n_eye = 0
        self._sum_smile = 0.0; self._n_smile = 0
        self._sum_hands = 0.0; self._n_hands = 0

        # Gesture counts
        self._gestures: dict[str, int] = {}
        self._custom_gestures: dict[str, int] = {}

        self._frame_count = 0
        self._face_frames = 0

    def reset(self):
        """Reset all aggregated state (called between questions)."""
        self.__init__(ema_alpha=self._alpha)

    def process_frame(self, jpeg_b64: str) -> dict:
        """
        Decode a base64 JPEG, run MediaPipe inference, update aggregations.
        Returns the live signals dict so the WebSocket can echo it back to the client.
        """
        _load_models_lazy()
        if not _models_loaded:
            return {"error": _models_load_error or "Models not loaded"}

        try:
            arr = np.frombuffer(base64.b64decode(jpeg_b64), dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None:
                return {"error": "Could not decode frame"}
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            face_res = _face_landmarker.detect(mp_img)
            gest_res = _gesture_recognizer.recognize(mp_img)
        except Exception as e:
            print(f"[BodyTracker] Frame processing error: {e}", file=sys.stderr)
            return {"error": str(e)}

        self._update(face_res, gest_res)
        s = self.get_summary()
        return {
            "eye_contact": s.eye_contact_live,
            "smile": s.smile_live,
            "frown": s.frown_live,
            "brow_raise": s.brow_raise_live,
            "hands_visible_pct": s.hands_visible_live,
            "dominant_gesture": s.dominant_gesture,
            "dominant_custom": s.dominant_custom,
            "frame_count": s.frame_count,
            "face_found_pct": s.face_detected_pct,
        }

    def _update(self, face_result, gesture_result):
        self._frame_count += 1
        fs = self._extract_frame(face_result, gesture_result)

        a = self._alpha
        self._ema_eye = a * fs.eye_contact + (1 - a) * self._ema_eye
        self._ema_smile = a * fs.smile + (1 - a) * self._ema_smile
        self._ema_frown = a * fs.frown + (1 - a) * self._ema_frown
        self._ema_brow = a * fs.brow_raise + (1 - a) * self._ema_brow
        self._ema_hands = a * (1.0 if fs.hands_up else 0.0) + (1 - a) * self._ema_hands

        if fs.face_found:
            self._face_frames += 1
            self._sum_eye += fs.eye_contact;   self._n_eye += 1
            self._sum_smile += fs.smile;        self._n_smile += 1

        self._sum_hands += 1.0 if fs.hands_up else 0.0
        self._n_hands += 1

        if fs.raw_gesture and fs.raw_gesture not in ("none", "No gesture", "None", ""):
            self._gestures[fs.raw_gesture] = self._gestures.get(fs.raw_gesture, 0) + 1
        if fs.custom_gesture and fs.custom_gesture != "none":
            self._custom_gestures[fs.custom_gesture] = self._custom_gestures.get(fs.custom_gesture, 0) + 1

    def get_summary(self) -> BodyLanguageSummary:
        def cmean(s, n):
            return round(s / n, 3) if n > 0 else 0.0

        dom_raw = max(self._gestures, key=self._gestures.get) if self._gestures else "none"
        dom_custom = max(self._custom_gestures, key=self._custom_gestures.get) if self._custom_gestures else "none"

        return BodyLanguageSummary(
            eye_contact_live=round(self._ema_eye, 3),
            smile_live=round(self._ema_smile, 3),
            frown_live=round(self._ema_frown, 3),
            brow_raise_live=round(self._ema_brow, 3),
            hands_visible_live=round(self._ema_hands, 3),
            eye_contact_pct=cmean(self._sum_eye, self._n_eye),
            smile_pct=cmean(self._sum_smile, self._n_smile),
            frown_pct=0.0,
            hands_visible_pct=cmean(self._sum_hands, self._n_hands),
            gesture_history=dict(self._gestures),
            custom_gesture_history=dict(self._custom_gestures),
            dominant_gesture=dom_raw,
            dominant_custom=dom_custom,
            frame_count=self._frame_count,
            face_detected_pct=round(self._face_frames / max(self._frame_count, 1), 3),
        )

    def _extract_frame(self, face_result, gesture_result) -> FrameSignals:
        fs = FrameSignals()

        if face_result and face_result.face_landmarks:
            fs.face_found = True
            if face_result.face_blendshapes:
                bs = {b.category_name: b.score for b in face_result.face_blendshapes[0]}
                fs.eye_contact = _eye_contact_blendshapes(bs)
                fs.smile = _smile_blendshapes(bs)
                fs.frown = float(np.mean([bs.get(k, 0) for k in FROWN_KEYS]))
                fs.brow_raise = float(np.mean([bs.get(k, 0) for k in BROW_UP_KEYS]))
            else:
                lm = face_result.face_landmarks[0]
                fs.eye_contact = _eye_contact_landmarks(lm)
                fs.smile = _smile_landmarks(lm)

        if gesture_result:
            hand_lms = gesture_result.hand_landmarks or []
            fs.hand_count = len(hand_lms)
            if gesture_result.gestures:
                top = gesture_result.gestures[0][0]
                fs.raw_gesture = top.category_name
                fs.hands_up = True
            elif hand_lms:
                fs.hands_up = True
                fs.raw_gesture = "visible"

            if hand_lms:
                fs.custom_gesture = detect_custom_gesture(hand_lms)

        return fs


# ─────────────────────────────────────────
#  SIGNAL COMPUTATION
# ─────────────────────────────────────────

def _eye_contact_blendshapes(bs: dict) -> float:
    gaze_away = sum(bs.get(k, 0) for k in GAZE_KEYS) / len(GAZE_KEYS)
    score = 1.0 - max(0.0, (gaze_away - 0.04) / 0.14)
    return float(np.clip(score, 0.0, 1.0))


def _smile_blendshapes(bs: dict) -> float:
    raw = (bs.get("mouthSmileLeft", 0) + bs.get("mouthSmileRight", 0)) / 2.0
    return float(np.clip(raw * 2.2, 0.0, 1.0))


def _eye_contact_landmarks(lm) -> float:
    try:
        LEFT_IRIS = [474, 475, 476, 477]
        RIGHT_IRIS = [469, 470, 471, 472]

        def iris_offset(iris_idx, inner, outer):
            iris_cx = float(np.mean([lm[i].x for i in iris_idx]))
            eye_cx = (lm[inner].x + lm[outer].x) / 2.0
            eye_w = abs(lm[outer].x - lm[inner].x) + 1e-6
            return abs(iris_cx - eye_cx) / (eye_w / 2.0)

        lo = iris_offset(LEFT_IRIS, 33, 133)
        ro = iris_offset(RIGHT_IRIS, 362, 263)
        return float(np.clip(1.0 - (lo + ro) / 2.0, 0.0, 1.0))
    except Exception:
        return 0.5


def _smile_landmarks(lm) -> float:
    try:
        mouth_h = abs(lm[14].y - lm[13].y) + 1e-6
        corner_avg = (lm[61].y + lm[291].y) / 2.0
        return float(np.clip((lm[14].y - corner_avg) / mouth_h, 0.0, 1.0))
    except Exception:
        return 0.3


# ─────────────────────────────────────────
#  CUSTOM GESTURE DETECTION
# ─────────────────────────────────────────

def _pt_dist(a, b) -> float:
    return float(np.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2))


def _two_hand_proximity(h1, h2) -> dict:
    wrist_dist = _pt_dist(h1[WRIST], h2[WRIST])
    min_tip_dist = min(_pt_dist(h1[t1], h2[t2]) for t1 in _ALL_TIPS for t2 in _ALL_TIPS)

    def palm_center(h):
        xs = [h[i].x for i in _ALL_MCPS]
        ys = [h[i].y for i in _ALL_MCPS]
        return float(np.mean(xs)), float(np.mean(ys))

    cx1, cy1 = palm_center(h1)
    cx2, cy2 = palm_center(h2)
    palm_dist = float(np.sqrt((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2))

    def avg_tips_to_palm(tips_hand, palm_cx, palm_cy):
        dists = [np.sqrt((tips_hand[t].x - palm_cx) ** 2 + (tips_hand[t].y - palm_cy) ** 2) for t in _ALL_TIPS]
        return float(np.mean(dists))

    avg_tips_to_palms = (avg_tips_to_palm(h1, cx2, cy2) + avg_tips_to_palm(h2, cx1, cy1)) / 2

    return {
        "wrist_dist": wrist_dist,
        "min_tip_dist": min_tip_dist,
        "palm_dist": palm_dist,
        "avg_tips_to_palms": avg_tips_to_palms,
    }


def detect_custom_gesture(hand_landmarks_list: list) -> str:
    if not hand_landmarks_list:
        return "none"

    if len(hand_landmarks_list) >= 2:
        h1, h2 = hand_landmarks_list[0], hand_landmarks_list[1]
        p = _two_hand_proximity(h1, h2)

        together = (
            p["wrist_dist"] < 0.20 or
            p["min_tip_dist"] < 0.06 or
            p["palm_dist"] < 0.18 or
            p["avg_tips_to_palms"] < 0.15
        )
        spread = p["wrist_dist"] > 0.50 and p["avg_tips_to_palms"] > 0.35

        if together:
            return "hands_together"
        if spread:
            return "hands_spread"

    lm = hand_landmarks_list[0]
    extended = _count_extended_fingers(lm)
    n_extended = sum(extended)

    if n_extended == 1 and extended[1]:
        if lm[8].y < lm[6].y - 0.02:
            return "emphasis_point"
        return "counting_1"
    if n_extended == 2 and extended[1] and extended[2]:
        return "counting_2"
    if n_extended == 3 and extended[1] and extended[2] and extended[3]:
        return "counting_3"
    if n_extended == 4 and not extended[0]:
        return "counting_4"

    return "none"


def _count_extended_fingers(lm) -> list[bool]:
    extended = []
    palm_x = lm[9].x
    extended.append(abs(lm[4].x - palm_x) > abs(lm[2].x - palm_x))
    for tip_idx, pip_idx in zip(FINGER_TIPS[1:], FINGER_PIPS[1:]):
        extended.append(lm[tip_idx].y < lm[pip_idx].y - 0.02)
    return extended


# ─────────────────────────────────────────
#  REGISTRY (per-session lookup)
# ─────────────────────────────────────────

_trackers: dict[str, BodyLanguageTracker] = {}


def get_tracker(session_id: str) -> BodyLanguageTracker | None:
    return _trackers.get(session_id)


def create_tracker(session_id: str) -> BodyLanguageTracker:
    t = BodyLanguageTracker()
    _trackers[session_id] = t
    return t


def remove_tracker(session_id: str):
    _trackers.pop(session_id, None)