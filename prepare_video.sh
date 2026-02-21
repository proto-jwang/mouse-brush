#!/usr/bin/env bash
# prepare_video.sh
# Convert a video to 1 FPS (keeping ALL frames) and burn frame index into top-right corner.
#
# Usage:
#   ./prepare_video.sh <input.mp4>
#
# Output:
#   <basename>_1fps_labeled.mp4  (same directory as input)

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input.mp4>" >&2
    exit 1
fi

INPUT="$1"
if [[ ! -f "$INPUT" ]]; then
    echo "Error: file not found: $INPUT" >&2
    exit 1
fi

DIR="$(dirname "$INPUT")"
BASE="$(basename "$INPUT" .mp4)"
OUTPUT="${DIR}/${BASE}_1fps_labeled.mp4"
TMP="${DIR}/${BASE}_1fps_tmp.mp4"

# Step 1: detect original fps
ORIG_FPS=$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=r_frame_rate \
    -of default=noprint_wrappers=1:nokey=1 "$INPUT")
# e.g. "30/1" -> need numerator for setpts multiplier
MULTIPLIER=$(python3 -c "from fractions import Fraction; print(float(Fraction('$ORIG_FPS')))")

echo "Input : $INPUT"
echo "FPS   : $ORIG_FPS  (${MULTIPLIER}x slowdown)"
echo "Output: $OUTPUT"

# Step 2: slow to 1 FPS, keeping every frame
ffmpeg -y -i "$INPUT" \
    -vf "setpts=${MULTIPLIER}*PTS" \
    -r 1 \
    "$TMP"

# Step 3: burn frame index (0-based) into top-right corner
ffmpeg -y -i "$TMP" \
    -vf "drawtext=text='Frame %{n}':start_number=0\
:x=W-tw-20:y=20\
:fontsize=48:fontcolor=white\
:box=1:boxcolor=black@0.6:boxborderw=8" \
    "$OUTPUT"

rm -f "$TMP"

TOTAL=$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=nb_frames \
    -of default=noprint_wrappers=1:nokey=1 "$OUTPUT")
echo "Done: $TOTAL frames -> $OUTPUT"


# 帮我拓展一下这个脚本，实现以下功能 
# 1. 批处理：提供一个 --input-dir 的argument，里面存的都是视频文件
# 2. 对每一个文件进行如下操作：
#     a. 慢速到1 FPS，保持每一帧
#     b. 在右上角标注帧索引（0-based）
# 3. 将视频文件上传gemini，并进行/Users/ruoyuwang/mouse_brush/generate_brush_frame_indices.py 中的效果
# 4. 将结果保存至 --output-dir 指定的目录下
# 5. 增加一个optional的visualization功能，保存output video，在视频中标注出gemini检测到的brush frame（如果有的话），及其之后的
# --n-brushed-frames帧，（默认值为5）右上角的帧索引用红色字体标注出来

python pipeline.py \
      --input-dir  ./mt2_data/ \
      --output-dir ./mt2_results \
      --visualize \
      --n-brushed-frames 5