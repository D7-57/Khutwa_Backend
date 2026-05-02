"""
download_models.py — One-time script to fetch MediaPipe model files.

Run this once on your backend server before starting the API:
    python download_models.py

The models are placed in app/models/ and required by body_tracker.py.
Total download: ~10 MB.
"""

import os
import sys
import urllib.request
from pathlib import Path

MODELS = {
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "gesture_recognizer.task": "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task",
}

OUT_DIR = Path(__file__).resolve().parent / "app" / "models"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading MediaPipe models to {OUT_DIR}/")

    for name, url in MODELS.items():
        target = OUT_DIR / name
        if target.exists() and target.stat().st_size > 100_000:
            print(f"  ✓ {name} already exists ({target.stat().st_size // 1024} KB) — skipping")
            continue
        try:
            print(f"  ↓ {name} ...", end="", flush=True)
            urllib.request.urlretrieve(url, target)
            kb = target.stat().st_size // 1024
            print(f" done ({kb} KB)")
        except Exception as e:
            print(f" FAILED: {e}")
            sys.exit(1)

    print("\nAll models ready. Start the backend with: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()