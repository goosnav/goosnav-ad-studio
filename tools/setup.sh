#!/bin/bash
# One-time machine setup for goosnav-ad-studio. Safe to re-run.
#   tools/setup.sh                 # check tools, create the Piper venv, fetch default voices
#   tools/setup.sh --voice NAME    # fetch one more Piper voice (e.g. en_US-amy-medium)
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="$(cd "$REPO" && python3 -c 'from studio import config; print(config.get("cache"))')"
mkdir -p "$CACHE/voices"
fetch_voice() {   # NAME like en_US-ryan-high -> rhasspy/piper-voices path en/en_US/ryan/high/
  local n="$1"; local lang="${n%%-*}"; local rest="${n#*-}"; local spk="${rest%-*}"; local q="${rest##*-}"
  local base="https://huggingface.co/rhasspy/piper-voices/resolve/main/${lang%%_*}/$lang/$spk/$q/$n"
  [ -f "$CACHE/voices/$n.onnx" ] || curl -fsSL -o "$CACHE/voices/$n.onnx" "$base.onnx"
  [ -f "$CACHE/voices/$n.onnx.json" ] || curl -fsSL -o "$CACHE/voices/$n.onnx.json" "$base.onnx.json"
  echo "voice $n ok"
}
if [ "${1:-}" = "--voice" ]; then fetch_voice "$2"; exit 0; fi
for t in blender ffmpeg ffprobe rclone python3; do command -v $t >/dev/null && echo "ok  $t" || echo "MISSING $t"; done
python3 -c "import numpy, scipy, PIL" && echo "ok  numpy scipy pillow" || echo "MISSING: pip install numpy scipy pillow"
if [ ! -x "$CACHE/venv/bin/piper" ]; then
  python3 -m venv "$CACHE/venv" && "$CACHE/venv/bin/pip" install -q piper-tts && echo "ok  piper venv"
fi
# commercially safe voices only (see studio/vo.py SAFE_VOICES)
for v in en_US-norman-medium en_US-joe-medium en_US-john-medium en_US-bryce-medium en_US-kristin-medium en_US-ljspeech-high en_GB-cori-medium en_GB-jenny_dioco-medium; do fetch_voice $v; done
[ -f "$REPO/studio.local.json" ] || { cp "$REPO/studio.example.json" "$REPO/studio.local.json"; echo "created studio.local.json: edit the paths"; }
python3 -m studio config
