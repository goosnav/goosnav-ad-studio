"""Explicit setup download only; the renderer never downloads voice weights."""
import os
os.environ.pop('HF_HUB_OFFLINE', None)
from huggingface_hub import snapshot_download
print(snapshot_download('hexgrad/Kokoro-82M', allow_patterns=[
    'config.json', 'kokoro-v1_0.pth', 'voices/am_onyx.pt', 'voices/am_puck.pt']))
