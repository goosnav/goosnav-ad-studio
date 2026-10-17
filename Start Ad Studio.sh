#!/bin/sh
# Start the Goosnav Ad Studio GUI from a terminal (Linux or macOS). Works on headless servers.
#
#   ./"Start Ad Studio.sh"                start on port 8788, open a browser if there is a desktop
#   ./"Start Ad Studio.sh" --no-browser   never open a browser
#   ./"Start Ad Studio.sh" --port 9000    use another port
#   ./"Start Ad Studio.sh" --local        this computer only
#   (by default it is reachable from your local network; there is no login, so trusted networks only)
#
# Runs keep going after you close the GUI. The CLI is: python3 -m harness --help
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
HOST=0.0.0.0; PORT=8788; BROWSER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --no-browser) BROWSER=--no-browser ;;
    --port) PORT="$2"; shift ;;
    --lan) HOST=0.0.0.0 ;;
    --local) HOST=127.0.0.1 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || [ "$(uname -s)" = Darwin ] || BROWSER=--no-browser
command -v python3 >/dev/null 2>&1 || { echo "Python 3.10+ is required." >&2; exit 1; }
cd "$ROOT"
exec python3 -m harness gui --host "$HOST" --port "$PORT" $BROWSER
