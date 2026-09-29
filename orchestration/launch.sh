#!/bin/bash
# Launch one unattended Claude Code session for a lane.
#   orchestration/launch.sh <lane_file_basename> <film_id>
#   e.g. orchestration/launch.sh C_the_table the_table
# Session folders live in $STUDIO_SESSIONS (default ~/goosnav-studio-work/_sessions).
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LANE="$1"; FILM="$2"
SESS="${STUDIO_SESSIONS:-$HOME/goosnav-studio-work/_sessions}/$LANE"
mkdir -p "$SESS"
sed -e "s#{BRIEF}#$REPO/orchestration/COMMON_BRIEF.md#g" -e "s#{REPO}#$REPO#g" \
    -e "s#{SESSION}#$SESS#g" -e "s#{FILM}#$FILM#g" "$REPO/orchestration/lanes/$LANE.md" > "$SESS/PROMPT.md"
printf 'PHASE: SCRIPT\nPROGRESS: 0\nUPDATED: %s\nNOTE: launched by orchestrator\n' "$(date -Is)" > "$SESS/STATUS.md"
cd "$SESS"
setsid nohup claude -p "$(cat PROMPT.md)" --dangerously-skip-permissions --add-dir "$REPO" \
      --output-format stream-json --verbose > session.log 2> session.err < /dev/null &
sleep 2
PID=$(pgrep -n -f "^claude -p Read $REPO/orchestration/COMMON_BRIEF.md" || true)   # anchor: skip wrapper shells
echo "$PID" > "$SESS/pid"
echo "launched $LANE ($FILM) pid=$PID dir=$SESS"
