#!/bin/bash
# Block until a session is "almost done", then print its status and exit.
#   orchestration/watch.sh <session_dir> [pid]
# Almost done = final render >= 60 %, or assembly after a render, or delivered/failed, or the process died.
S="$1/STATUS.md"; PID="${2:-$(cat "$1/pid" 2>/dev/null)}"
seen_render=0
while true; do
  P=$(grep -m1 '^PHASE:' "$S" | awk '{print $2}')
  G=$(grep -m1 '^PROGRESS:' "$S" | sed 's/^PROGRESS:[[:space:]]*//')
  if [[ "$G" == */* ]]; then a=${G%%/*}; b=${G##*/}; b=${b%%[^0-9]*}; G=$(( b > 0 ? 100 * ${a//[^0-9]/} / b : 0 )); else G=${G//[^0-9]/}; fi
  G=${G:-0}
  case "$P" in
    RENDERING) seen_render=1; if [ "$G" -ge 60 ]; then echo "READY $1 phase=$P progress=$G"; cat "$S"; exit 0; fi;;
    ASSEMBLY) if [ $seen_render = 1 ]; then echo "READY $1 phase=$P"; cat "$S"; exit 0; fi;;
    DELIVERED|FAILED) echo "READY $1 phase=$P"; cat "$S"; exit 0;;
  esac
  if [ -n "$PID" ] && ! kill -0 "$PID" 2>/dev/null; then echo "EXITED $1 phase=$P progress=$G"; cat "$S"; exit 0; fi
  sleep 60
done
