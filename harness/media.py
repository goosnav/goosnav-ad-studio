"""Deterministic media checks and finishing; creative work stays with workers."""
import array
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave
import zipfile

from .contracts import ContractError, digest
from .workers import supervise


def run(argv, timeout=600):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ContractError(f'Media tool unavailable or timed out: {e}') from e
    if r.returncode:
        raise ContractError(r.stderr[-2000:] or f'Tool failed: {argv[0]}')
    return r


def check_video(path, config, preview=False):
    tools = config['tools']; o = config['output']
    d = json.loads(run([tools['ffprobe'], '-v','error','-show_streams','-show_format','-of','json',str(path)]).stdout)
    videos = [s for s in d.get('streams', []) if s['codec_type'] == 'video']
    audios = [s for s in d.get('streams', []) if s['codec_type'] == 'audio']
    if not videos or not audios:
        raise ContractError('Video must contain picture and an audio stream (intentional silence is explicit)')
    v = videos[0]
    try:
        duration = float(d['format']['duration'])
        a, b = v['avg_frame_rate'].split('/'); fps = float(a)/float(b)
    except (KeyError, ValueError, ZeroDivisionError) as e:
        raise ContractError('Invalid media timing') from e
    if not math.isfinite(duration) or not o['min_seconds']-.15 <= duration <= o['max_seconds']+.15:
        raise ContractError(f'Video duration {duration:.3f} does not fit {o["min_seconds"]}–{o["max_seconds"]} seconds')
    if abs(fps-o['fps']) > .05:
        raise ContractError(f'Expected {o["fps"]} fps; got {fps}')
    if abs(v['width']/v['height'] - o['width']/o['height']) > .02:
        raise ContractError('Wrong aspect ratio')
    if not preview and (v['width'],v['height']) != (o['width'],o['height']):
        raise ContractError('Wrong final resolution')
    if not preview and (v['codec_name'] != 'h264' or v.get('pix_fmt') != 'yuv420p'):
        raise ContractError('Final video must be H.264/yuv420p')
    if int(audios[0]['sample_rate']) != 48000:
        raise ContractError('Final audio must be 48 kHz')
    run([tools['ffmpeg'],'-v','error','-xerror','-i',str(path),'-map','0:v:0','-map','0:a:0','-f','null','-'])
    motion = run([tools['ffmpeg'],'-v','error','-i',str(path),'-an','-vf','fps=2,scale=64:64',
                  '-f','framemd5','-']).stdout
    hashes = {line.rsplit(',',1)[-1].strip() for line in motion.splitlines() if line and not line.startswith('#')}
    if len(hashes) < 2:
        raise ContractError('No visible picture change: a static card is not an animated ad')
    return {'duration':duration, 'fps':fps, 'width':v['width'], 'height':v['height'],
            'audio':True, 'decoded':True, 'distinct_sampled_frames':len(hashes), 'sha256':digest(path)}


def check_audio(path, timeline, config, direction=None):
    try:
        with wave.open(str(path)) as w:
            rate, frames, channels, width = w.getframerate(),w.getnframes(),w.getnchannels(),w.getsampwidth()
            if rate != 48000 or width != 2 or channels not in (1,2):
                raise ContractError('Mix must be 48 kHz, mono/stereo PCM16 WAV')
            peak = 0
            while chunk := w.readframes(48000):
                samples = array.array('h', chunk)
                peak = max(peak, max((abs(x) for x in samples), default=0))
        d=json.loads(Path(timeline).read_text())
        if d.get('sample_rate') != 48000 or d.get('fps') != config['output']['fps']:
            raise ContractError('Timeline sample rate/fps differs from project')
        duration=d.get('duration')
        if not isinstance(duration,(float,int)) or not math.isfinite(duration) or abs(duration-frames/rate) > .05:
            raise ContractError('Timeline duration does not match measured audio')
        for key in ('dialogue','events'):
            if not isinstance(d.get(key),list):
                raise ContractError(f'Timeline requires {key} array')
        for line in d['dialogue']:
            start,end=line.get('start_sample'),line.get('end_sample')
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= frames:
                raise ContractError('Dialogue exceeds audio or has invalid timing')
            if not line.get('text') or not line.get('speaker'):
                raise ContractError('Dialogue needs text and speaker')
        for event in d['events']:
            if type(event.get('sample')) is not int or not 0 <= event['sample'] < frames:
                raise ContractError('Event has invalid sample position')
        if peak >= 32760 or (d['dialogue'] and peak < 100):
            raise ContractError('Mix is clipped or silent despite dialogue')
        if not d['dialogue'] and not d.get('sound_rationale'):
            raise ContractError('No-dialogue films need a sound_rationale in the timeline')
        from .direction import check_cast, check_mix
        if direction is not None:
            check_cast(d, direction)
        levels = check_mix(path, d)
        return {'duration':frames/rate,'peak':peak/32768,'dialogue':len(d['dialogue']),'levels':levels}
    except (wave.Error, KeyError, TypeError, ValueError) as e:
        if isinstance(e,ContractError):raise
        raise ContractError(f'Invalid audio/timeline: {e}') from e


def link_text(website):
    return website.removeprefix('https://').removeprefix('http://')


def end_text(script, direction):
    card = (direction or {}).get('end_card') or {}
    return card.get('title') or script.get('cta', '')


def balance(title, longest=16):
    """Frame shrinks a line to fit the width; break a long title in two so it stays big."""
    if '\n' in title or len(title) <= longest:
        return title
    cuts = [i for i, ch in enumerate(title) if ch == ' ']
    if not cuts:
        return title
    # Prefer a sentence boundary, then the space nearest the middle.
    cut = min(cuts, key=lambda i: (title[i - 1] not in '.!?,:;', abs(len(title) / 2 - i)))
    return title[:cut] + '\n' + title[cut + 1:]


# Frame retro settings per look. ps1: late-90s console crunch. Pixel-sized type without
# anti-aliasing, RGB split, jitter, a shadow and a typewriter with a cursor; the picture
# pixelated to 15-bit colour with ordered dither; scanlines over the whole frame.
LOOKS = {
    'clean': {'retro': {'enabled': False}, 'media_fx': {'mode': 'none'}},
    'ps1': {'retro': {'enabled': True, 'pixel': 4, 'aliased': True, 'rgb_split': 2, 'scanlines': 'frame',
                      'scanline_strength': 45, 'shadow': True, 'shadow_color': '#7f7f7f', 'jitter': True,
                      'typewriter': True, 'type_delay': 0.15, 'cursor': True},
            'media_fx': {'mode': 'ps1', 'pixel': 5}},
}


def look_settings(look, seconds=None, text_chars=0, text=True):
    """Frame retro/media_fx for a segment. The typewriter finishes in the first half of the card."""
    d = json.loads(json.dumps(LOOKS[look]))
    r = d['retro']
    if r['enabled']:
        if not text:
            r.update(typewriter=False, jitter=False, cursor=False)
        elif r.get('typewriter') and seconds:
            r['type_speed'] = round(min(200, max(12, text_chars / max(.3, seconds * .5 - r['type_delay']))), 1)
    return d


def finish_frame(master, script, config, work, cancelled, direction=None):
    """Frame writes all end text. end_card: the closing seconds become a native Frame card
    (title above the picture, link below, Frame's own fonts); full: the whole ad is framed.
    output.look sets Frame's treatment of text and picture (clean or ps1). The ad's audio
    runs straight through."""
    work=Path(work).resolve(); destination=work/'final.mp4'; master=str(Path(master).resolve())
    o=config['output']; look=o.get('look','clean')
    title=end_text(script, direction)
    enabled=o['cta'] and config['website'] and title and not title.lower().startswith('none')
    if not enabled and look=='clean':
        shutil.copy2(master,destination)
        return {'summary':'CTA skipped by project/script policy', 'master':'final.mp4',
                'files':[{'path':'final.mp4','kind':'video'}]}
    tools=config['tools']; root=Path(tools['frame_root'])
    python=tools['frame_python']
    if not tools['frame_root'] or not (root/'app/src/goosnav_frame').is_dir() or not Path(python).is_file():
        raise ContractError('Frame finishing requested: configure tools.frame_root and tools.frame_python')
    probe=json.loads(run([tools['ffprobe'],'-v','error','-show_entries','format=duration','-of','json',master]).stdout)
    duration=float(probe['format']['duration'])
    if not enabled:
        start=duration
    elif o['frame']=='full':
        start=0.0
    else:
        card=(direction or {}).get('end_card') or {}
        seconds=min(card.get('seconds') or o['end_card_seconds'], duration/2)
        start=round((duration-seconds)*o['fps'])/o['fps']  # cut on a frame boundary
    canvas={'preset':'custom','width':o['width'],'height':o['height'],'background':'#ffffff'}
    export_settings={'format':'mp4','fps':o['fps'],'quality':'high'}
    jobs=[]
    if start>0:
        # The story keeps the edit's picture; only the look is applied, never text.
        jobs.append({'output':str(work/'story.mp4'),'settings':{
            'canvas':{**canvas,'layout':'overlay'},'title':{'visible':False},'link':{'visible':False},
            'media':{'fit':'cover','trim_start':0,'trim_duration':start,'keep_audio':False},
            'export':export_settings,**look_settings(look,text=False)}})
    if enabled:
        text=balance(title); link=link_text(config['website'])
        jobs.append({'output':str(work/'card.mp4'),'still':str(work/'end_card.png'),
            'still_time':min(1.5,(duration-start)*.75),'settings':{
            'canvas':{**canvas,'layout':'stacked'},'title':{'visible':True,'text':text},
            'link':{'visible':True,'text':link},
            'media':{'fit':'contain','trim_start':start,'keep_audio':False},
            'export':export_settings,**look_settings(look,duration-start,len(text)+len(link))}})
    request=work/'frame.json';request.write_text(json.dumps({'root':str(root),'input':master,
        'scale':o['width']/1080,'jobs':jobs},indent=2))
    runner=Path(__file__).with_name('frame_runner.py')
    r=supervise([python,str(runner),str(request)],cwd=work,prompt='',log=work/'frame.log',
                timeout=config['limits']['production_timeout_seconds'],cancelled=cancelled)
    if r['kind'] != 'ok':
        raise ContractError(f'Frame failed ({r["kind"]}): {r["detail"][-1000:]}')
    inputs=[]
    for job in jobs:
        inputs+=['-i',job['output']]
    parts=''.join(f'[{i+1}:v]setpts=PTS-STARTPTS[s{i}];' for i in range(len(jobs)))
    video=parts+''.join(f'[s{i}]' for i in range(len(jobs)))+f'concat=n={len(jobs)}:v=1:a=0[v]'
    run([tools['ffmpeg'],'-v','error','-y','-i',master,*inputs,'-filter_complex',
         f'{video};[v]fps={o["fps"]},format=yuv420p[out]','-map','[out]','-map','0:a:0',
         '-c:v','libx264','-crf','17','-preset','medium','-c:a','copy','-t',f'{duration:.6f}',
         '-movflags','+faststart',str(destination)],timeout=config['limits']['production_timeout_seconds'])
    for job in jobs:
        Path(job['output']).unlink()
    check_video(destination,config)
    files=[{'path':'final.mp4','kind':'video'},{'path':'frame.json','kind':'source'}]
    if enabled:
        files.insert(1,{'path':'end_card.png','kind':'image'})
    what=(f'Frame {o["frame"].replace("_"," ")} from {start:.2f} s: "{title}" + {link_text(config["website"])}'
          if enabled else 'CTA skipped by project/script policy')
    return {'summary':f'{what}; {look} look; audio kept from the edit','master':'final.mp4',
            'end_card_start':start if enabled else None,'files':files}


def check_final_mix(path, timeline, config, work):
    """The finished video's audio must still pass the mix gates at the timeline's dialogue times."""
    from .direction import check_mix
    wav=Path(work)/'final-audio.wav'
    run([config['tools']['ffmpeg'],'-v','error','-y','-i',str(path),'-vn','-ac','1','-ar','48000',
         '-c:a','pcm_s16le',str(wav)])
    try:
        return check_mix(wav, timeline)
    finally:
        wav.unlink(missing_ok=True)


def package(inputs, state, work):
    work=Path(work)
    manifest={'run':state['id'],'config':state['config'],'models':state['models'],
              'inputs':inputs, 'sources':state.get('sources',[])}
    (work/'manifest.json').write_text(json.dumps(manifest,indent=2))
    with zipfile.ZipFile(work/'ad.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        z.write(work/'manifest.json','manifest.json')
        for task_id,result in inputs.items():
            if not isinstance(result,dict):continue
            for index,f in enumerate(result.get('files',[])):
                p=Path(f['path'])
                if digest(p) != f['sha256']:
                    raise ContractError(f'Artifact changed before packaging: {p}')
                z.write(p,f'artifacts/{task_id}/{index:03d}-{p.name}')
        z.writestr('README.txt','Run manifest contains original paths, model routing, scripts and source evidence.\n'
                   'artifacts/ contains accepted production files. See worker source/notes for render commands.\n'
                   'This package is a local review/export, not proof of publication.\n')
    return {'summary':'Local delivery package ready', 'files':[{'path':'ad.zip','kind':'package'},
            {'path':'manifest.json','kind':'manifest'}]}
