"""Optional local Hugging Face runners. Heavy imports stay out of the controller."""
import argparse
import json
from pathlib import Path
import re
import time


def validate_request(request):
    provider=request.get('provider')
    if provider not in ('kokoro','chatterbox','stable-audio'):
        raise ValueError('provider must be kokoro, chatterbox or stable-audio; Piper is an explicit separate fallback')
    key='prompt' if provider=='stable-audio' else 'text'
    if not isinstance(request.get(key),str) or not request[key].strip():
        raise ValueError(f'{provider} requires nonempty {key}')
    if len(request[key]) > 10000:
        raise ValueError('Audio request exceeds 10,000 characters; generate separate takes')
    if provider=='kokoro' and not re.fullmatch(r'[a-z]{2}_[a-z0-9_]+',request.get('voice','af_heart')):
        raise ValueError('Use one Kokoro voice ID, for example af_heart')
    return request


# Dialogue treatment applied to every voice take: rumble off, mud down, consonants up, gentle
# compression, safety limit. Measured on Kokoro: am_onyx's 2-5 kHz share rises about 5x.
VOICE_CHAIN = ('highpass=f=90,equalizer=f=320:t=o:w=1.2:g=-4,equalizer=f=3200:t=o:w=1.6:g=7,'
               'equalizer=f=6500:t=o:w=1:g=2,acompressor=threshold=-24dB:ratio=3:attack=5:release=80:makeup=4dB,'
               'alimiter=limit=0.89')


def polish(source, output):
    """48 kHz PCM16 voice take with VOICE_CHAIN applied (FFmpeg only; importable anywhere)."""
    import subprocess
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-af', VOICE_CHAIN + ',aresample=48000',
                    '-ar', '48000', '-c:a', 'pcm_s16le', str(output)], check=True)


def generate(request, output):
    request=validate_request(request)
    import numpy as np
    import soundfile as sf
    import torch
    from huggingface_hub import scan_cache_dir, snapshot_download
    torch.set_num_threads(request.get('threads',4))
    torch.manual_seed(request.get('seed',0))
    started=time.monotonic(); provider=request['provider']; device=request.get('device','cpu')
    resolved_revision=None
    if provider=='kokoro':
        # A pinned snapshot is passed to KModel, avoiding a second unpinned weight fetch.
        from kokoro import KModel,KPipeline
        import spacy
        if not spacy.util.is_package('en_core_web_sm'):
            raise ValueError('Kokoro needs en_core_web_sm installed in this audio environment; see dev/OPERATIONS.md')
        try:
            import espeakng_loader
            from phonemizer.backend.espeak.wrapper import EspeakWrapper
            EspeakWrapper.set_library(espeakng_loader.get_library_path())
            EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        except ImportError:
            pass
        repo=request.get('model','hexgrad/Kokoro-82M');voice=request.get('voice','af_heart')
        folder=Path(snapshot_download(repo,revision=request.get('revision','main'),
            allow_patterns=['config.json','kokoro-v1_0.pth',f'voices/{voice}.pt']))
        resolved_revision=folder.name
        model=KModel(repo_id=repo,config=str(folder/'config.json'),model=str(folder/'kokoro-v1_0.pth'))
        pipeline=KPipeline(lang_code=request.get('language','a'),model=model,device=device,repo_id=repo)
        chunks=[a for _,_,a in pipeline(request['text'],voice=str(folder/f'voices/{voice}.pt'),speed=request.get('speed',1.0))]
        if not chunks:raise ValueError('Model generated no audio')
        signal=np.concatenate([a.detach().cpu().numpy() for a in chunks]);rate=24000
    elif provider=='chatterbox':
        from chatterbox.tts import ChatterboxTTS
        repo='ResembleAI/chatterbox'
        model=ChatterboxTTS.from_pretrained(device=device)
        options={'exaggeration':request.get('exaggeration',.5),'cfg_weight':request.get('cfg',.5)}
        if request.get('reference'):
            options['audio_prompt_path']=request['reference']
        signal=model.generate(request['text'],**options).detach().cpu().numpy().T
        rate=model.sr
    else:
        from stable_audio_tools import get_pretrained_model
        from stable_audio_tools.inference.generation import generate_diffusion_cond
        repo=request.get('model','stabilityai/stable-audio-open-small')
        model,c=get_pretrained_model(repo);model=model.to(device)
        audio=generate_diffusion_cond(model,steps=8,cfg_scale=1.0,
            conditioning=[{'prompt':request['prompt'],'seconds_total':min(11,request.get('seconds',11))}],
            sample_size=c['sample_size'],sampler_type='pingpong',device=device)
        signal=audio[0].detach().cpu().numpy().T;rate=c['sample_rate']
    signal=np.asarray(signal,dtype=np.float32)
    if signal.size==0 or not np.isfinite(signal).all() or float(np.max(np.abs(signal)))<1e-6:
        raise ValueError('Model generated empty, silent or non-finite audio')
    signal*=min(1.0,.9/float(np.max(np.abs(signal))))
    # Resample using the already-required FFmpeg, retaining original duration/pitch.
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    native=output.with_suffix('.native.wav');sf.write(native,signal,rate,subtype='PCM_16')
    import subprocess
    dry=output.with_suffix('.dry.wav')
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(native),'-ar','48000','-c:a','pcm_s16le',str(dry)],check=True)
    if provider!='stable-audio' and request.get('polish',True):
        polish(dry,output)   # the take to use; .dry.wav keeps the untreated voice
    else:
        dry.replace(output)
    info=sf.info(output)
    cached=[]
    for entry in scan_cache_dir().repos:
        if entry.repo_id==repo:
            cached=[r.commit_hash for r in entry.revisions]
    metadata={'provider':provider,'model':repo,'resolved_revision':resolved_revision,
              'cached_revisions':cached,'request':request,'sample_rate':info.samplerate,
              'channels':info.channels,'frames':info.frames,'duration':info.duration,
              'wall_seconds':round(time.monotonic()-started,3),'device':device,
              'polish':VOICE_CHAIN if provider!='stable-audio' and request.get('polish',True) else None,
              'revision_note':'Pinned snapshot' if resolved_revision else 'Provider-managed weights; cache revisions recorded, exact revision not asserted'}
    output.with_suffix('.json').write_text(json.dumps(metadata,indent=2))
    return metadata


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('request');p.add_argument('output')
    a=p.parse_args()
    try:
        print(json.dumps(generate(json.loads(Path(a.request).read_text()),a.output),indent=2))
    except Exception as e:
        p.exit(1,f'Audio generation failed ({type(e).__name__}): {e}\nNo voice fallback was substituted.\n')


if __name__=='__main__':main()
