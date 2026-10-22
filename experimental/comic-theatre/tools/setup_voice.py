"""One-time portable voice setup: python tools/setup_voice.py. Requires Python 3.10–3.12."""
import os
from pathlib import Path
import subprocess
import sys
import venv

root = Path(__file__).resolve().parents[1]
if sys.version_info[:2] < (3, 10) or sys.version_info[:2] > (3, 12):
    raise SystemExit('Use Python 3.10, 3.11 or 3.12 for the local voice environment.')
env_dir = root / '.venv'
venv.EnvBuilder(with_pip=True).create(env_dir)
python = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(root/'voices/requirements.txt')], check=True)
subprocess.run([str(python), '-m', 'spacy', 'download', 'en_core_web_sm'], check=True)
subprocess.run([str(python), str(root/'tools/download_voice.py')], check=True)
print('Local voice setup complete. Normal renders now use these cached files offline.')
