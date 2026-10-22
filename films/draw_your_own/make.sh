#!/usr/bin/env bash
# DRAW YOUR OWN (Book Two ad): rebuild every stage, from voices to the framed final MP4.
#   films/draw_your_own/make.sh [OUTPUT_DIR]
# WORK (default ~/goosnav-studio-work/draw_your_own) holds takes, blends and frames.
# Finished stages are kept: delete a stage's output under WORK to redo it.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="${WORK:-$HOME/goosnav-studio-work/draw_your_own}"
OUT="${1:-$HOME/Desktop/business/studio/output/films/draw_your_own}"
AUDIO_PY="$(python3 -c "import json;print(json.load(open('$REPO/harness.local.json'))['audio']['python'])")"
cd "$REPO"
mkdir -p "$WORK"
[ -f "$WORK/voice/manifest.json" ] || "$AUDIO_PY" -m harness.voice "$HERE/voices.json" "$WORK/voice"
python3 "$HERE/sound.py" "$HERE/cut.json" "$WORK"
blender -b --python-exit-code 1 --python "$HERE/scene.py" -- "$WORK/blocking.blend"
blender -b "$WORK/blocking.blend" --python-exit-code 1 --python "$HERE/animate.py" -- \
    "$HERE/cut.json" "$WORK" "$WORK/scene.blend"
python3 - "$WORK" <<'PY'
import json, sys
w = sys.argv[1]
t = json.load(open(f'{w}/audio/timeline.json'))
json.dump({'fps': t['fps'], 'rigs': {'READER': 'READER', 'PAL': 'PAL'},
           'lines': [{'speaker': l['speaker'], 'text': l['text'], 'start': l['start_sample'] / t['sample_rate'],
                      'end': l['end_sample'] / t['sample_rate']} for l in t['dialogue']]},
          open(f'{w}/scene_check_request.json', 'w'))
PY
blender -b "$WORK/scene.blend" --python-exit-code 1 --python harness/scene_check.py -- \
    "$WORK/scene_check_request.json" "$WORK/scene_check.json"
python3 -c "import json,sys;p=json.load(open('$WORK/scene_check.json'))['problems'];print(p);sys.exit(1 if p else 0)"
blender -b "$WORK/scene.blend" --python-exit-code 1 --python "$HERE/render.py" -- "$HERE/cut.json" "$WORK/frames"
python3 "$HERE/finish.py" "$HERE/cut.json" "$WORK" "$OUT"
