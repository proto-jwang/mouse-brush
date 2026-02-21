"""
Gemini 1-FPS brush-onset detector (single event per side)

Goal:
- Given a 1 FPS video with two mice (left-side mouse and right-side mouse),
  detect the SINGLE frame index when a brush first contacts the LEFT mouse's foot (L),
  and the SINGLE frame index when a brush first contacts the RIGHT mouse's foot (R).
- Each of L and R can happen 0 or 1 time per video.

Output JSON:
{
  "L": <int or null>,
  "R": <int or null>,
  "notes": <string>
}

Prereq:
  pip install -U google-genai
  export GEMINI_API_KEY="YOUR_KEY"

Usage:
  python generate_brush_frame_indices.py --video /path/to/video.mp4 --model gemini-3-flash-preview
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional

from google import genai
from google.genai import types


PROMPT_EN = """\
You are analyzing a scientific experiment video.

IMPORTANT: The video is stored at 1 FPS (one frame per second).
Each frame displays its index number in the TOP-RIGHT CORNER (e.g. "Frame 0", "Frame 1", ...).
Use those visible labels as the frame index — do NOT infer index from timestamps.

There are two mice in the video:
- L = the mouse on the LEFT side of the frame
- R = the mouse on the RIGHT side of the frame
(Use screen-left / screen-right. Do NOT use the animal's anatomical left/right.)

A human uses a small BRUSH to stimulate the BACK LEFT FOOT of each mouse.
Each side (L and R) occurs at most once in this video: 0 or 1 event per side.

Event definition:
- The target is always the BACK LEFT FOOT of the mouse (the hind paw on the mouse's anatomical left side).
- The event frame is the frame index (read from the top-right label) where the brush is in FULL
  contact with the back left foot — meaning the brush bristles are clearly and completely pressing
  against the paw, not just touching the edge or approaching.
- If full contact spans multiple frames, report the FIRST frame where full contact is achieved.
- Do NOT count partial contact, near-miss, or approach frames.

Uncertainty rule:
- If you cannot confidently determine whether full brush-foot contact happened for L or R,
  set that field to null and explain briefly in notes. Do NOT guess.

Return strictly valid JSON matching this schema:
{
  "L": integer or null,
  "R": integer or null,
  "notes": string
}
"""


RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "L": {
            "type": "integer",
            "nullable": True,
            "description": "Frame index of first brush-foot contact for LEFT mouse (screen-left).",
        },
        "R": {
            "type": "integer",
            "nullable": True,
            "description": "Frame index of first brush-foot contact for RIGHT mouse (screen-right).",
        },
        "notes": {"type": "string"},
    },
    "required": ["L", "R", "notes"],
}


def _require_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY env var. Example:\n"
            '  export GEMINI_API_KEY="YOUR_KEY"\n'
        )
    return key


def detect_brush_events_1fps(
    video_path: str,
    model: str = "gemini-3-flash-preview",
    temperature: float = 0.0,
) -> Dict[str, Optional[int]]:
    """
    Detect 0/1 brush-onset frame index for left/right mouse in a 1-FPS video.

    Args:
        video_path: Path to a video file (mp4/avi/mov...).
        model: Gemini model name.
        temperature: Sampling temperature (use 0.0 for determinism).

    Returns:
        Dict with keys: "L" (int or None), "R" (int or None), "notes" (str).
    """
    api_key = _require_api_key()
    client = genai.Client(api_key=api_key)

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Upload video to Files API
    uploaded = client.files.upload(file=video_path)

    # Wait for the file to reach ACTIVE state
    while uploaded.state.name != "ACTIVE":
        if uploaded.state.name == "FAILED":
            raise RuntimeError(f"File processing failed: {uploaded.name}")
        print(f"Waiting for file to become ACTIVE (current: {uploaded.state.name})...", flush=True)
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)

    # Ask Gemini for structured JSON output
    resp = client.models.generate_content(
        model=model,
        contents=[uploaded, PROMPT_EN],
        config=types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )

    # Parse JSON robustly
    try:
        data = json.loads(resp.text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gemini returned non-JSON output:\n{resp.text}") from e

    # Validate minimally (schema enforcement should already help)
    out = {
        "L": data.get("L", None),
        "R": data.get("R", None),
        "notes": data.get("notes", ""),
    }

    # Normalize Python None
    if out["L"] is None:
        out["L"] = None
    if out["R"] is None:
        out["R"] = None

    # Ensure ints if present
    if out["L"] is not None and not isinstance(out["L"], int):
        raise TypeError(f'Expected "L" to be int or null, got: {type(out["L"])}')
    if out["R"] is not None and not isinstance(out["R"], int):
        raise TypeError(f'Expected "R" to be int or null, got: {type(out["R"])}')
    if not isinstance(out["notes"], str):
        out["notes"] = str(out["notes"])

    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Path to 1-FPS video file.")
    parser.add_argument("--model", default="gemini-3-flash-preview", help="Gemini model name.")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature.")
    args = parser.parse_args()

    try:
        result = detect_brush_events_1fps(
            video_path=args.video,
            model=args.model,
            temperature=args.temperature,
        )
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()