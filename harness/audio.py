"""Optional local audio runners. Heavy imports stay out of the controller."""
import argparse
import array
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import wave


class AudioDefect(ValueError):
    """A measured synthesis defect, distinct from a missing runtime or model."""


def _number(value, name, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be a finite number in [{low}, {high}]')


def validate_request(request, *, require_reference=True):
    if not isinstance(request, dict):
        raise ValueError('Audio request must be an object')
    provider = request.get('provider')
    if provider not in ('kokoro', 'chatterbox', 'stable-audio'):
        raise ValueError('provider must be kokoro, chatterbox or stable-audio; no automatic voice fallback')
    key = 'prompt' if provider == 'stable-audio' else 'text'
    if not isinstance(request.get(key), str) or not request[key].strip():
        raise ValueError(f'{provider} requires nonempty {key}')
    if len(request[key]) > 10000:
        raise ValueError('Audio request exceeds 10,000 characters; generate separate takes')
    for name, default, low, high in (('seed', 0, 0, 2**32-1), ('threads', 4, 1, 256)):
        value = request.get(name, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    for name in ('polish', 'local_files_only'):
        if name in request and type(request[name]) is not bool:
            raise ValueError(f'{name} must be boolean')
    if provider == 'stable-audio':
        return request
    _number(request.get('speed', 1.0), 'speed', .25, 4)
    voice = request.get('voice', 'af_heart' if provider == 'kokoro' else 'default')
    if not isinstance(voice, str) or not voice:
        raise ValueError('voice must be a nonempty ID')
    if provider == 'kokoro':
        if not re.fullmatch(r'[a-z]{2}_[a-z0-9_]+', voice):
            raise ValueError('Use one Kokoro voice ID, for example af_heart')
        if request.get('language', voice[0]) != voice[0]:
            raise ValueError('Kokoro language must match the voice ID prefix')
        if any(k in request for k in ('reference', 'exaggeration', 'cfg')):
            raise ValueError('Kokoro does not support reference, exaggeration or cfg')
    else:
        if request.get('speed', 1.0) != 1:
            raise ValueError('Chatterbox does not expose a speed control; use phrasing/pauses')
        if 'language' in request:
            raise ValueError('This Chatterbox adapter supports its English model only')
        if require_reference and voice != 'default' and not request.get('reference'):
            raise ValueError('Named Chatterbox voices require a caller-supplied reference')
        _number(request.get('exaggeration', .5), 'exaggeration', 0, 2)
        _number(request.get('cfg', .5), 'cfg', 0, 1)
    phrasing = request.get('phrasing', [request['text']])
    if (not isinstance(phrasing, list) or not phrasing or
            any(not isinstance(p, str) or not p.strip() for p in phrasing) or
            ' '.join(' '.join(phrasing).split()) != ' '.join(request['text'].split())):
        raise ValueError('phrasing must split text into nonempty phrases without changing words')
    pauses = request.get('pauses', {})
    if not isinstance(pauses, dict) or set(pauses) - {'before', 'between', 'after'}:
        raise ValueError('pauses accepts before, between and after seconds')
    for name, value in pauses.items():
        _number(value, f'pauses.{name}', 0, 10)
    if pauses.get('between', 0) and len(phrasing) < 2:
        raise ValueError('pauses.between needs explicit phrasing with at least two phrases')
    return request


def voice_settings(request, *, require_reference=True):
    """Normalize the settings actually consumed by the two voice providers."""
    validate_request(request, require_reference=require_reference)
    if request['provider'] not in ('kokoro', 'chatterbox'):
        raise ValueError('Batch voice supports kokoro and chatterbox only')
    result = dict(request)
    defaults = {'voice': 'af_heart' if request['provider'] == 'kokoro' else 'default',
                'speed': 1.0, 'seed': 0, 'threads': 4, 'device': 'cpu',
                'revision': 'main', 'local_files_only': True, 'polish': True,
                'phrasing': [request['text']], 'pauses': {}}
    for key, value in defaults.items():
        result.setdefault(key, value)
    result['pauses'] = {key: result['pauses'].get(key, 0) for key in ('before', 'between', 'after')}
    if request['provider'] == 'kokoro':
        result.setdefault('model', 'hexgrad/Kokoro-82M')
        result.setdefault('language', result['voice'][0])
    else:
        result.setdefault('model', 'ResembleAI/chatterbox')
        result.setdefault('exaggeration', .5)
        result.setdefault('cfg', .5)
    return result


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def measure_wav(path):
    """Measure decoded PCM16 frames, amplitude and threshold-based active bounds.

    These bounds are an amplitude envelope, never phoneme/word/acting alignment.
    """
    with wave.open(str(path), 'rb') as stream:
        channels, width, rate, frames = (stream.getnchannels(), stream.getsampwidth(),
                                       stream.getframerate(), stream.getnframes())
        if width != 2 or channels not in (1, 2) or stream.getcomptype() != 'NONE':
            raise ValueError('Voice takes must be mono/stereo PCM16 WAV')
        count = peak = square_sum = clipped = 0
        first = last = None
        while chunk := stream.readframes(4096):
            if len(chunk) % (2 * channels):
                raise ValueError('truncated PCM frame')
            samples = array.array('h', chunk)
            if sys.byteorder != 'little':
                samples.byteswap()
            for i, sample in enumerate(samples):
                magnitude = abs(sample)
                peak = max(peak, magnitude)
                square_sum += sample * sample
                clipped += magnitude >= 32760
                if magnitude >= 104:
                    frame = (count + i) // channels
                    if first is None:
                        first = frame
                    last = frame + 1
            count += len(samples)
        if count != frames * channels:
            raise ValueError('truncated WAV: header and decoded frames differ')
    return {'sample_rate': rate, 'channels': channels, 'frames': frames,
            'duration': frames / rate, 'peak': peak / 32768,
            'rms': math.sqrt(square_sum / count) / 32768 if count else 0,
            'clipped_samples': clipped, 'active_start_sample': first, 'active_end_sample': last}


# Dialogue treatment: rumble off, mud down, consonants up, gentle compression, limit.
VOICE_CHAIN = ('highpass=f=90,equalizer=f=320:t=o:w=1.2:g=-4,equalizer=f=3200:t=o:w=1.6:g=7,'
               'equalizer=f=6500:t=o:w=1:g=2,acompressor=threshold=-24dB:ratio=3:attack=5:release=80:makeup=4dB,'
               'alimiter=limit=0.89')


def polish(source, output):
    """48 kHz PCM16 voice take with VOICE_CHAIN applied (FFmpeg only)."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-af', VOICE_CHAIN + ',aresample=48000',
                    '-ar', '48000', '-c:a', 'pcm_s16le', str(output)], check=True)


def assemble_phrases(phrases, render, sample_rate, pauses):
    """Render phrases sequentially and insert exact sample-count pauses."""
    import numpy as np
    pieces = [np.zeros(round(pauses.get('before', 0) * sample_rate), dtype=np.float32)]
    for i, phrase in enumerate(phrases):
        if i:
            pieces.append(np.zeros(round(pauses.get('between', 0) * sample_rate), dtype=np.float32))
        segment = np.asarray(render(phrase), dtype=np.float32)
        if not segment.size:
            raise AudioDefect('empty')
        if not np.isfinite(segment).all():
            raise AudioDefect('non-finite')
        if float(np.max(np.abs(segment))) < 1e-6:
            raise AudioDefect('silent')
        pieces.append(segment)
    pieces.append(np.zeros(round(pauses.get('after', 0) * sample_rate), dtype=np.float32))
    return np.concatenate(pieces)


class AudioSession:
    """Sequential, process-local model/pipeline reuse. No imports or downloads at init.

    A moving HF ref resolves once per session; new sessions resolve it again. Offline
    mode uses the locally resolved snapshot, never claims it is the upstream latest.
    All loaded model/voice files are hashed, not just the ref name or package version.
    """
    def __init__(self):
        self._snapshots = {}
        self._folders = {}
        self._hashes = {}
        self._models = {}
        self._pipelines = {}
        self._voice_hashes = {}

    def _hash(self, path):
        stat = path.stat()
        key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if key not in self._hashes:
            self._hashes[key] = sha256(path)
        return self._hashes[key]

    def identity(self, request):
        settings = voice_settings(request)
        provider = settings['provider']
        package = 'kokoro' if provider == 'kokoro' else 'chatterbox-tts'
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ImportError(f'{provider} is not installed in this Python runtime; no provider substituted') from exc
        from huggingface_hub import snapshot_download
        files = (['config.json', 'kokoro-v1_0.pth', f'voices/{settings["voice"]}.pt'] if provider == 'kokoro'
                 else ['ve.safetensors', 't3_cfg.safetensors', 's3gen.safetensors', 'tokenizer.json', 'conds.pt'])
        ref_key = (settings['model'], settings['revision'], settings['local_files_only'])
        revision = self._snapshots.get(ref_key, settings['revision'])
        folder = Path(snapshot_download(settings['model'], revision=revision, allow_patterns=files,
                                        local_files_only=settings['local_files_only']))
        if not re.fullmatch(r'[0-9a-f]{40,64}', folder.name):
            raise ValueError('Provider did not resolve an immutable snapshot revision')
        self._snapshots[ref_key] = folder.name
        hashes = {name: self._hash(folder / name) for name in files}
        runtime = {package: version, 'python': sys.version.split()[0]}
        for dependency in ('torch', 'numpy', 'soundfile', 'misaki', 'spacy', 'en_core_web_sm',
                           'phonemizer', 'espeakng-loader', 'transformers', 'librosa', 'safetensors'):
            try:
                runtime[dependency] = importlib.metadata.version(dependency)
            except importlib.metadata.PackageNotFoundError:
                pass
        identity = {'provider': provider, 'model': settings['model'], 'resolved_revision': folder.name,
                    'files': hashes, 'runtime': runtime}
        if settings.get('reference'):
            identity['reference_sha256'] = self._hash(Path(settings['reference']))
        self._folders[json.dumps(identity, sort_keys=True)] = folder
        return identity

    def synthesize(self, request, output):
        """Write untreated 48 kHz PCM16 WAV plus .native.wav; return provenance."""
        started = time.monotonic()
        settings = voice_settings(request)
        identity = self.identity(settings)
        folder = self._folders[json.dumps(identity, sort_keys=True)]
        import numpy as np
        import soundfile as sf
        import torch
        torch.set_num_threads(settings['threads'])
        torch.manual_seed(settings['seed'])
        np.random.seed(settings['seed'])
        import random
        random.seed(settings['seed'])
        provider, device = settings['provider'], settings['device']
        # If local snapshot files are replaced, never describe old loaded weights
        # with their new hashes. Voice files are handled separately below.
        model_files = tuple(sorted((k, v) for k, v in identity['files'].items() if not k.startswith('voices/')))
        model_key = (provider, str(folder), device, model_files)
        if provider == 'kokoro':
            from kokoro import KModel, KPipeline
            if settings['language'] in ('a', 'b'):
                import spacy
                if not spacy.util.is_package('en_core_web_sm'):
                    raise ValueError('Kokoro needs en_core_web_sm in this audio environment; see dev/OPERATIONS.md')
            try:
                import espeakng_loader
                from phonemizer.backend.espeak.wrapper import EspeakWrapper
                EspeakWrapper.set_library(espeakng_loader.get_library_path())
                EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
            except ImportError:
                pass
            if model_key not in self._models:
                self._models[model_key] = KModel(repo_id=settings['model'], config=str(folder / 'config.json'),
                                                model=str(folder / 'kokoro-v1_0.pth')).to(device).eval()
            pipeline_key = (*model_key, settings['language'])
            if pipeline_key not in self._pipelines:
                self._pipelines[pipeline_key] = KPipeline(lang_code=settings['language'],
                    model=self._models[model_key], device=device, repo_id=settings['model'])
            pipeline = self._pipelines[pipeline_key]
            voice_path = str(folder / f'voices/{settings["voice"]}.pt')
            voice_hash = identity['files'][f'voices/{settings["voice"]}.pt']
            voice_key = (pipeline_key, voice_path)
            if self._voice_hashes.get(voice_key) != voice_hash:
                pipeline.voices.pop(voice_path, None)
                self._voice_hashes[voice_key] = voice_hash
            rate = 24000

            def render(text):
                chunks = [a.detach().cpu().numpy() for _, _, a in pipeline(
                    text, voice=voice_path, speed=settings['speed'])]
                if not chunks:
                    raise AudioDefect('empty')
                return np.concatenate(chunks)
        else:
            from chatterbox.tts import ChatterboxTTS
            from copy import deepcopy
            if not hasattr(ChatterboxTTS, 'from_local'):
                raise ValueError('Installed Chatterbox lacks from_local; exact weight provenance is required')
            if model_key not in self._models:
                model = ChatterboxTTS.from_local(folder, device=device)
                self._models[model_key] = (model, deepcopy(model.conds))
            model, defaults = self._models[model_key]
            # generate mutates conditionals: previous references must not leak to a new character.
            model.conds = deepcopy(defaults)
            rate = model.sr

            def render(text):
                return model.generate(text, audio_prompt_path=settings.get('reference'),
                    exaggeration=settings['exaggeration'], cfg_weight=settings['cfg']).detach().cpu().numpy().reshape(-1)

        with torch.inference_mode():
            signal = assemble_phrases(settings['phrasing'], render, rate, settings['pauses'])
        signal *= min(1.0, .9 / float(np.max(np.abs(signal))))
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        native = output.with_suffix('.native.wav')
        sf.write(native, signal, rate, subtype='PCM_16')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(native), '-ar', '48000',
                        '-c:a', 'pcm_s16le', str(output)], check=True)
        return {'identity': identity, 'wall_seconds': round(time.monotonic() - started, 3)}


def generate(request, output, session=None):
    """Backwards-compatible single-take command, optionally sharing an AudioSession."""
    request = validate_request(request)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    provider = request['provider']
    if provider != 'stable-audio':
        dry = output.with_suffix('.dry.wav')
        generated = (session or AudioSession()).synthesize(request, dry)
        dry.with_suffix('.native.wav').replace(output.with_suffix('.native.wav'))
        if request.get('polish', True):
            polish(dry, output)
        else:
            import shutil
            shutil.copyfile(dry, output)
        identity = generated['identity']
        metadata = {'provider': provider, 'model': identity['model'],
                    'resolved_revision': identity['resolved_revision'], 'identity': identity,
                    'cached_revisions': [identity['resolved_revision']], 'revision_note': 'Pinned snapshot; files hashed'}
    else:
        import numpy as np
        import soundfile as sf
        import torch
        from stable_audio_tools import get_pretrained_model
        from stable_audio_tools.inference.generation import generate_diffusion_cond
        torch.set_num_threads(request.get('threads', 4))
        torch.manual_seed(request.get('seed', 0))
        repo = request.get('model', 'stabilityai/stable-audio-open-small')
        device = request.get('device', 'cpu')
        model, config = get_pretrained_model(repo)
        audio = generate_diffusion_cond(model.to(device), steps=8, cfg_scale=1.0,
            conditioning=[{'prompt': request['prompt'], 'seconds_total': min(11, request.get('seconds', 11))}],
            sample_size=config['sample_size'], sampler_type='pingpong', device=device)
        signal = audio[0].detach().cpu().numpy().T
        if not signal.size or not np.isfinite(signal).all() or np.max(np.abs(signal)) < 1e-6:
            raise AudioDefect('Model generated empty, silent or non-finite audio')
        signal *= min(1.0, .9 / float(np.max(np.abs(signal))))
        native = output.with_suffix('.native.wav')
        sf.write(native, signal, config['sample_rate'], subtype='PCM_16')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(native), '-ar', '48000',
                        '-c:a', 'pcm_s16le', str(output)], check=True)
        metadata = {'provider': provider, 'model': repo, 'resolved_revision': None,
                    'revision_note': 'Provider-managed weights; exact revision not asserted'}
    metadata.update(measure_wav(output))
    metadata.update(request=request, wall_seconds=round(time.monotonic() - started, 3),
                    device=request.get('device', 'cpu'),
                    polish=VOICE_CHAIN if provider != 'stable-audio' and request.get('polish', True) else None)
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2))
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request')
    parser.add_argument('output')
    args = parser.parse_args()
    try:
        print(json.dumps(generate(json.loads(Path(args.request).read_text()), args.output), indent=2))
    except Exception as exc:
        parser.exit(1, f'Audio generation failed ({type(exc).__name__}): {exc}\nNo voice fallback was substituted.\n')


if __name__ == '__main__':
    main()
