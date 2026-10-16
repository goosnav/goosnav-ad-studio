"""Check the tools a run will need before any agent spends quota on it."""
from pathlib import Path
import shutil
import subprocess


def check_dependencies(config):
    problems = []
    tools = config['tools']
    for key in ('ffmpeg', 'ffprobe', 'blender'):
        if not shutil.which(tools[key]):
            problems.append(f'tools.{key}: {tools[key]!r} not found on PATH')
    if config['output']['cta'] and config['website']:
        root = Path(tools['frame_root']) if tools['frame_root'] else None
        if not root or not (root / 'app/src/goosnav_frame').is_dir() or not Path(tools['frame_python']).is_file():
            problems.append('Goosnav Frame: set tools.frame_root and tools.frame_python (needed for the end card)')
    python = config['audio']['python']
    if not python or not Path(python).is_file():
        problems.append('audio.python: the local model environment (Kokoro voices, Whisper checks) is not configured')
    else:
        r = subprocess.run([python, '-c', 'import kokoro, soundfile, transformers, torch'],
                           capture_output=True, text=True, timeout=120)
        if r.returncode:
            problems.append(f'audio.python cannot import kokoro/soundfile/transformers/torch: {r.stderr.strip()[-300:]}')
    return problems
