"""Executed in Frame's environment, not in the harness interpreter."""
import json
from pathlib import Path
import sys


def main():
    request=json.loads(Path(sys.argv[1]).read_text())
    sys.path.insert(0,str(Path(request['root'])/'app/src'))
    from goosnav_frame.core import export,settings
    export.export_mp4(settings.normalize(request['settings']),request['input'],Path(request['output']))


if __name__ == '__main__':main()
