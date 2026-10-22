"""Offline local speech worker. No Ad Studio imports or paid services."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')

def model_folder():
    from huggingface_hub import snapshot_download
    try:
        return Path(snapshot_download('hexgrad/Kokoro-82M', local_files_only=True,
            allow_patterns=['config.json', 'kokoro-v1_0.pth', 'voices/am_onyx.pt', 'voices/am_puck.pt']))
    except Exception as exc:
        raise RuntimeError('Local Kokoro files are missing. Run python tools/setup_voice.py once, or use --voice recorded.') from exc

def main():
    folder = model_folder()
    files = ['config.json', 'kokoro-v1_0.pth', 'voices/am_onyx.pt', 'voices/am_puck.pt']
    identity = {'model': 'hexgrad/Kokoro-82M', 'revision': folder.name,
                'files': {f: hashlib.sha256((folder/f).read_bytes()).hexdigest() for f in files},
                'runtime': {p: importlib.metadata.version(p) for p in ['kokoro', 'torch', 'numpy', 'soundfile', 'misaki']}}
    if sys.argv[1] == '--identity':
        print(json.dumps(identity))
        return
    import numpy as np
    import soundfile as sf
    import torch
    import espeakng_loader
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    EspeakWrapper.set_library(espeakng_loader.get_library_path())
    EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
    from kokoro import KModel, KPipeline
    torch.set_num_threads(2)
    torch.manual_seed(0)
    model = KModel(repo_id='hexgrad/Kokoro-82M', config=str(folder/'config.json'),
                   model=str(folder/'kokoro-v1_0.pth')).to('cpu').eval()
    pipeline = KPipeline(lang_code='a', model=model, repo_id='hexgrad/Kokoro-82M')
    requests = json.loads(Path(sys.argv[1]).read_text())
    with torch.inference_mode():
        for request in requests:
            if request['voice'] not in ['am_onyx', 'am_puck']:
                raise ValueError('Unsupported voice; choose am_onyx or am_puck')
            chunks = [a.detach().cpu().numpy() for _, _, a in pipeline(
                request['text'], voice=str(folder/'voices'/f"{request['voice']}.pt"), speed=1)]
            if not chunks:
                raise RuntimeError('Local speech returned no audio')
            audio = np.concatenate(chunks)
            audio *= min(1., .9/max(.0001, float(np.max(np.abs(audio)))))
            sf.write(request['output'], audio, 24000, subtype='PCM_16')

if __name__ == '__main__':
    main()
