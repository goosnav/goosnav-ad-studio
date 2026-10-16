"""Transcribe dialogue windows with a local Whisper model. Runs in config.audio.python.

    python harness/asr.py request.json result.json
request: {"wav": 16 kHz mono WAV, "windows": [[start, end], ...] seconds, "model": HF model id}
"""
import json
import sys


def main():
    request = json.load(open(sys.argv[1]))
    import soundfile as sf
    from transformers import pipeline
    asr = pipeline('automatic-speech-recognition', model=request.get('model', 'openai/whisper-small.en'), device='cpu')
    audio, rate = sf.read(request['wav'], dtype='float32')
    texts = []
    for a, b in request['windows']:
        clip = audio[int(max(0, a) * rate):int(b * rate)]
        texts.append(asr({'raw': clip, 'sampling_rate': rate})['text'] if len(clip) else '')
    json.dump({'texts': texts, 'model': request.get('model')}, open(sys.argv[2], 'w'))


if __name__ == '__main__':
    main()
