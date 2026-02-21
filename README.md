# Mouse Brush

Automated detection of brush-stimulation events in two-mouse experiment videos using Google Gemini.

## Demo

https://github.com/user-attachments/assets/3133d97f-0f17-4ca2-9beb-503e0e67b106

> Detected brush frames are highlighted in **red**; all other frames use white labels.

## Overview

This tool processes videos from a neuroscience experiment in which a researcher uses a small brush to stimulate the back left foot of two mice (left mouse = L, right mouse = R). It:

1. Re-encodes each input video to 1 FPS (preserving every original frame)
2. Burns a visible frame index label into the top-right corner of each frame
3. Uploads the labeled video to the Gemini API for visual analysis
4. Returns the first frame index at which full brush–paw contact occurs for each mouse (`L` / `R`)
5. Optionally generates a visualization video with detected frames highlighted in red

## Files

| File | Description |
|------|-------------|
| `pipeline.py` | **Main script.** Batch-processes a directory of videos in parallel. |
| `generate_brush_frame_indices.py` | Single-video detector; also importable as a library. |
| `prepare_video.sh` | Shell helper to convert one video to 1 FPS with frame labels burned in. |

## Requirements

- Python 3.9+
- `ffmpeg` and `ffprobe` (must be on `PATH`)
- Google Gemini API access

```bash
pip install -U google-genai
export GEMINI_API_KEY="YOUR_KEY"
```

## Quick Start

### Batch pipeline (recommended)

```bash
python pipeline.py \
    --input-dir  /path/to/videos \
    --output-dir /path/to/results \
    --visualize \
    --n-brushed-frames 5
```

For each video the pipeline creates a sub-folder under `--output-dir` containing:

```
<output-dir>/
  <video-stem>/
    <video-stem>_labeled.mp4   # 1-FPS video with frame indices burned in
    result.json                 # detection result
    <video-stem>_vis.mp4        # visualization video (if --visualize)
```

`result.json` format:

```json
{
  "video": "group_1.mp4",
  "L": 42,
  "R": 87,
  "notes": "Clear contact visible for both sides."
}
```

`L` / `R` are integer frame indices (0-based) or `null` if no event was detected.

### Single video

```bash
python generate_brush_frame_indices.py \
    --video /path/to/video_1fps.mp4 \
    --model gemini-2.0-flash
```

### Shell helper (prepare one video manually)

```bash
chmod +x prepare_video.sh
./prepare_video.sh input.mp4
# produces input_1fps_labeled.mp4
```

## CLI Reference

### `pipeline.py`

| Argument | Default | Description |
|----------|---------|-------------|
| `--input-dir` | *(required)* | Directory of input video files |
| `--output-dir` | *(required)* | Root output directory |
| `--model` | `gemini-3-flash-preview` | Gemini model name |
| `--temperature` | `0.0` | Sampling temperature (0 = deterministic) |
| `--visualize` | off | Save visualization video with detected frames highlighted |
| `--n-brushed-frames` | `5` | Frames after brush onset to highlight in red |
| `--vis-fps` | `10` | FPS of output visualization video |
| `--workers` | `4` | Number of videos processed in parallel |

### `generate_brush_frame_indices.py`

| Argument | Default | Description |
|----------|---------|-------------|
| `--video` | *(required)* | Path to a 1-FPS labeled video |
| `--model` | `gemini-3-flash-preview` | Gemini model name |
| `--temperature` | `0.0` | Sampling temperature |

## Supported Video Formats

`.mp4`, `.avi`, `.mov`, `.mkv`, `.m4v`

## Notes

- Frame indices are **0-based** and read directly from the burned-in label, not inferred from timestamps.
- The model identifies **full brush-paw contact** only — partial contact or approach frames are ignored.
- If the model cannot confidently determine an event, it returns `null` and explains in the `notes` field.
- The pipeline retries Gemini API calls on transient 503/429 errors with exponential backoff.
