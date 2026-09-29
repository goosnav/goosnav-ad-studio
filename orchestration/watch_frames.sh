#!/bin/bash
# Block until a frames dir reaches a fraction of a total, or the render process for it disappears.
#   orchestration/watch_frames.sh <frames_dir> <total> [fraction=0.6] [process_pattern]
DIR="$1"; TOTAL="$2"; FR="${3:-0.6}"; PAT="${4:-}"
NEED=$(python3 -c "print(int($TOTAL*$FR))")
while true; do
  N=$(ls "$DIR" 2>/dev/null | grep -c '\.png$')
  if [ "$N" -ge "$NEED" ]; then echo "READY $DIR $N/$TOTAL"; exit 0; fi
  if [ -n "$PAT" ] && ! pgrep -f "$PAT" >/dev/null; then echo "RENDER GONE $DIR $N/$TOTAL"; exit 0; fi
  sleep 120
done
