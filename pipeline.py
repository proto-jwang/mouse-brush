"""
Batch brush-event detector pipeline.

For each video in --input-dir:
  1. Convert to 1 FPS (all frames preserved, no skipping)
  2. Burn frame index (0-based) into top-right corner  →  <stem>_labeled.mp4
  3. Upload labeled video to Gemini, detect brush-contact frame ranges (L / R)
  4. Save JSON result  →  <output-dir>/<stem>/result.json
     L and R are [start, end] frame-index ranges, or null.
  5. (optional --visualize) Save visualization video where the detected brush
     range is highlighted in red  →  <output-dir>/<stem>/<stem>_vis.mp4

Usage:
  python pipeline.py \\
      --input-dir  /path/to/videos \\
      --output-dir /path/to/results \\
      [--model gemini-3-flash-preview] \\
      [--visualize]

Requirements:
  pip install -U google-genai
  export GEMINI_API_KEY="YOUR_KEY"
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types


# ── Prompt & response schema ───────────────────────────────────────────────────

PROMPT_EN = """\
You are analyzing a scientific experiment video.

IMPORTANT: The video is stored at 1 FPS (one frame per second).
Each frame displays its index number in the TOP-RIGHT CORNER (e.g. "Frame 0", "Frame 1", ...).
Use those visible labels as the frame index — do NOT infer index from timestamps.

There are two mice in the video:
- L = the mouse on the LEFT side of the frame
- R = the mouse on the RIGHT side of the frame
(Use screen-left / screen-right. Do NOT use the animal's anatomical left/right.)

A human uses a small BRUSH to stimulate the left hind paw of each mouse.
Each side (L and R) must be brushed EXACTLY ONCE per video. This is the expected normal case.

Event definition:
- The target is always the left hind paw of the mouse (the hind paw on the mouse's anatomical left side).
- Report a [start, end] frame-index RANGE for each brush contact:
    • start = the first frame (read from the top-right label) where the brush bristles are clearly
      and completely pressing against the paw (full contact begins).
    • end   = the last frame where full brush-paw contact is maintained.
- Do NOT count partial contact, near-miss, or approach frames.

Validity rule — set the field to null and explain in notes if ANY of the following is true:
- The mouse is never brushed (0 events detected for that side).
- The mouse is brushed MORE THAN ONCE (2+ distinct brush contacts detected for that side).
- You cannot confidently determine whether exactly one full brush-foot contact occurred.
Do NOT guess. Only return a range when you are confident there is exactly one clear event.

Return strictly valid JSON matching this schema:
{
  "L": [start_frame, end_frame] or null,
  "R": [start_frame, end_frame] or null,
  "notes": string
}
"""

_RANGE_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {"type": "integer"},
    "minItems": 2,
    "maxItems": 2,
    "description": "[start_frame, end_frame] of full brush-paw contact.",
}

RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "L": {
            **_RANGE_SCHEMA,
            "nullable": True,
            "description": "[start, end] frame range of brush contact for LEFT mouse (screen-left), or null.",
        },
        "R": {
            **_RANGE_SCHEMA,
            "nullable": True,
            "description": "[start, end] frame range of brush contact for RIGHT mouse (screen-right), or null.",
        },
        "notes": {"type": "string"},
    },
    "required": ["L", "R", "notes"],
}

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}

# ── ffmpeg helpers ─────────────────────────────────────────────────────────────

def _run_ffmpeg(args: List[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed:\n{result.stderr.decode(errors='replace')[-2000:]}"
        )


def _get_orig_fps(video_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    fps_str = result.stdout.decode().strip()  # e.g. "30/1"
    return float(Fraction(fps_str))


# Base drawtext options shared by labeled and visualization renders.
# %{n} is ffmpeg's frame-counter expansion (0-based).
_DT_BASE = (
    "drawtext=text='Frame %{n}'"
    ":start_number=0"
    ":x=W-tw-20:y=20"
    ":fontsize=48"
    ":box=1:boxcolor=black@0.6:boxborderw=8"
)


def _make_1fps(src: str, dst: str, orig_fps: float) -> None:
    """Re-encode src at 1 FPS keeping every original frame (setpts slowdown)."""
    _run_ffmpeg([
        "-i", src,
        "-vf", f"setpts={orig_fps}*PTS",
        "-r", "1",
        dst,
    ])


def _make_labeled(src_1fps: str, dst: str) -> None:
    """Burn white 'Frame N' label into every frame."""
    _run_ffmpeg(["-i", src_1fps, "-vf", _DT_BASE + ":fontcolor=white", dst])


def _highlight_expr(
    L_range: Optional[List[int]], R_range: Optional[List[int]]
) -> Optional[str]:
    """
    Build an ffmpeg expression that evaluates to >0 for any highlighted frame.

    Highlighted = [L_range[0], L_range[1]] union [R_range[0], R_range[1]].
    Commas inside between() are escaped as \\, so the filtergraph parser
    forwards them correctly to the expression evaluator.
    """
    parts: List[str] = []
    if L_range is not None:
        parts.append(f"between(n\\,{L_range[0]}\\,{L_range[1]})")
    if R_range is not None:
        parts.append(f"between(n\\,{R_range[0]}\\,{R_range[1]})")
    return "+".join(parts) if parts else None


def _make_visualization(
    src_1fps: str,
    dst: str,
    L_range: Optional[List[int]],
    R_range: Optional[List[int]],
    vis_fps: int = 10,
) -> None:
    """
    Create visualization video from the unlabeled 1-fps source:
      - Normal frames              → white 'Frame N' label
      - Brush-contact range frames → red 'Frame N' label
    Output is re-encoded at vis_fps so each original frame is held for vis_fps display frames.
    """
    hi = _highlight_expr(L_range, R_range)
    if hi is None:
        # No events detected — just white labels, same as labeled video
        vf = _DT_BASE + ":fontcolor=white"
    else:
        # Two drawtext passes: white for non-highlighted, red for highlighted.
        # not(expr) in ffmpeg = 1 when expr==0, i.e. frame is NOT highlighted.
        white = _DT_BASE + f":fontcolor=white:enable=not({hi})"
        red   = _DT_BASE + f":fontcolor=red:enable={hi}"
        vf = f"{white},{red}"

    _run_ffmpeg(["-i", src_1fps, "-vf", f"setpts=PTS/{vis_fps},{vf}", "-r", str(vis_fps), dst])


# ── Gemini detection ───────────────────────────────────────────────────────────

def _detect_brush_events(
    video_path: str,
    client: genai.Client,
    model: str,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    uploaded = client.files.upload(file=video_path)

    # Poll until ACTIVE (timeout after 5 minutes)
    deadline = time.time() + 300
    while uploaded.state.name != "ACTIVE":
        if uploaded.state.name == "FAILED":
            raise RuntimeError(f"Gemini file processing failed: {uploaded.name}")
        if time.time() > deadline:
            raise RuntimeError(f"Timed out waiting for Gemini file to become ACTIVE: {uploaded.name}")
        print(f"    Waiting for Gemini file to become ACTIVE "
              f"(current: {uploaded.state.name})...", flush=True)
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)

    # Retry generate_content on transient 503 / 429 errors with exponential backoff
    max_retries = 5
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[uploaded, PROMPT_EN],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                ),
            )
            break
        except Exception as exc:
            err_str = str(exc)
            is_retryable = "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            if is_retryable and attempt < max_retries - 1:
                wait = 2 ** attempt * 5  # 5, 10, 20, 40 seconds
                print(f"    Gemini unavailable (attempt {attempt+1}/{max_retries}), retrying in {wait}s ...", flush=True)
                time.sleep(wait)
            else:
                raise

    # Best-effort cleanup of the uploaded file
    try:
        client.files.delete(name=uploaded.name)
    except Exception:
        pass

    try:
        data = json.loads(resp.text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gemini returned non-JSON:\n{resp.text}") from e

    result: Dict[str, Any] = {
        "L": data.get("L"),
        "R": data.get("R"),
        "notes": data.get("notes", ""),
    }

    # Type validation
    for key in ("L", "R"):
        val = result[key]
        if val is not None:
            if (
                not isinstance(val, list)
                or len(val) != 2
                or not all(isinstance(v, int) for v in val)
            ):
                raise TypeError(
                    f'Expected "{key}" to be [int, int] or null, got {val!r}'
                )
    if not isinstance(result["notes"], str):
        result["notes"] = str(result["notes"])

    return result


# ── Per-video pipeline ─────────────────────────────────────────────────────────

def _process_video(
    video_path: Path,
    output_dir: Path,
    client: genai.Client,
    model: str,
    temperature: float,
    visualize: bool,
    vis_fps: int = 10,
) -> None:
    stem = video_path.stem
    out_sub = output_dir / stem
    out_sub.mkdir(parents=True, exist_ok=True)

    tmp_1fps    = out_sub / f"{stem}_1fps_tmp.mp4"
    labeled_mp4 = out_sub / f"{stem}_labeled.mp4"
    vis_mp4     = out_sub / f"{stem}_vis.mp4"
    result_json = out_sub / "result.json"

    tag = f"[{stem}]"
    print(f"\n{'='*60}\n{tag} Processing: {video_path.name}", flush=True)

    try:
        # Step 1 — Convert to 1 FPS if needed
        orig_fps = _get_orig_fps(str(video_path))
        print(f"{tag} Original FPS : {orig_fps}")
        if orig_fps == 1.0:
            print(f"{tag} [1/3] Already 1 FPS — skipping conversion.", flush=True)
            src_1fps = str(video_path)
        else:
            print(f"{tag} [1/3] Converting to 1 FPS ...", flush=True)
            _make_1fps(str(video_path), str(tmp_1fps), orig_fps)
            src_1fps = str(tmp_1fps)

        # Step 2 — Burn white frame-index labels (for Gemini upload)
        print(f"{tag} [2/3] Burning frame labels ...", flush=True)
        _make_labeled(src_1fps, str(labeled_mp4))

        # Step 3 — Gemini detection
        print(f"{tag} [3/3] Uploading to Gemini & detecting ...", flush=True)
        result = _detect_brush_events(str(labeled_mp4), client, model, temperature)
        print(f"{tag} L={result['L']}  R={result['R']}")
        print(f"{tag} Notes: {result['notes']}")

        # Save JSON
        result["video"] = video_path.name
        result_json.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"{tag} Saved: {result_json}")

        # Optional visualization
        if visualize:
            print(f"{tag} [vis] Generating visualization video ({vis_fps} FPS) ...", flush=True)
            _make_visualization(
                src_1fps, str(vis_mp4),
                result["L"], result["R"], vis_fps,
            )
            print(f"{tag} Saved: {vis_mp4}")

    finally:
        # Always clean up intermediates
        if tmp_1fps.exists():
            tmp_1fps.unlink()
        if labeled_mp4.exists():
            labeled_mp4.unlink()


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch brush-event detector: 1-FPS conversion + Gemini detection."
    )
    parser.add_argument(
        "--input-dir", required=True,
        help="Directory containing input video files.",
    )
    parser.add_argument(
        "--output-dir", required=True,
        help="Root directory for all outputs (one sub-folder per video).",
    )
    parser.add_argument(
        "--model", default="gemini-3.1-pro-preview",
        help="Gemini model name (default: gemini-3.1-pro-preview).",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.0,
        help="Sampling temperature (default: 0.0).",
    )
    parser.add_argument(
        "--visualize", action="store_true",
        help="Save a visualization video highlighting detected brush ranges in red.",
    )
    parser.add_argument(
        "--vis-fps", type=int, default=10,
        help="FPS of the output visualization video (default: 10).",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of videos to process in parallel (default: 4).",
    )
    args = parser.parse_args()

    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.is_dir():
        print(f"[ERROR] --input-dir not found: {input_dir}", file=sys.stderr)
        sys.exit(1)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect video files (sorted)
    videos = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not videos:
        print(f"[ERROR] No video files found in {input_dir}", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(videos)} video(s) in {input_dir}")

    # Gemini client
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] Missing GEMINI_API_KEY env var.", file=sys.stderr)
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    # Process videos in parallel, collecting errors without aborting the batch
    errors: List[str] = []
    print(f"Processing {len(videos)} video(s) with {args.workers} parallel worker(s).")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_video = {
            executor.submit(
                _process_video,
                video_path, output_dir,
                client, args.model, args.temperature,
                args.visualize, args.vis_fps,
            ): video_path
            for video_path in videos
        }
        for future in concurrent.futures.as_completed(future_to_video):
            video_path = future_to_video[future]
            try:
                future.result()
            except Exception as exc:
                msg = f"{video_path.name}: {exc}"
                print(f"[ERROR] {msg}", file=sys.stderr)
                errors.append(msg)

    # Summary
    print(f"\n{'='*60}")
    n_ok = len(videos) - len(errors)
    print(f"Done. {n_ok}/{len(videos)} video(s) succeeded.")
    if errors:
        print("Failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
