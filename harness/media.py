"""Deterministic media checks and finishing; creative work stays with workers."""
import array
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import wave
import zipfile

from .contracts import ContractError, digest
from .speech import normalize_loudness
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


def check_scene(blend, rigs, lines, fps, models=None, timeout=900):
    """Run harness/scene_check.py in Blender on the saved scene; raise with the problems.
    models: {speaker: library character .blend} the speaker's armature must match."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        request, report = Path(tmp) / 'request.json', Path(tmp) / 'report.json'
        request.write_text(json.dumps({'fps': fps, 'rigs': rigs, 'lines': lines, 'models': models or {}}))
        script = Path(__file__).with_name('scene_check.py')
        r = run(['blender', '-b', str(blend), '--python-exit-code', '1', '--python', str(script),
                 '--', str(request), str(report)], timeout=timeout)
        if not report.is_file():
            raise ContractError(f'Scene check produced no report: {r.stdout[-800:]}')
        result = json.loads(report.read_text())
    if result['problems']:
        raise ContractError('Scene check: ' + '; '.join(result['problems']))
    return result


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


# Frame never post-processes the picture or animates text (owner, 2026-10-16: no scanlines,
# crunch, jitter or typewriter). A look only changes how workers build the film itself.
CLEAN = {'retro': {'enabled': False}, 'media_fx': {'mode': 'none'}}


def finish_frame(master, script, config, work, cancelled, direction=None):
    """Frame writes all end text. end_card: the closing seconds become a native Frame card
    (title above the picture, link below, Frame's own fonts); full: the whole ad is framed.
    Frame's type is always clean (CLEAN); output.look only affects production. The ad's audio
    runs straight through."""
    work=Path(work).resolve(); destination=work/'final.mp4'; master=str(Path(master).resolve())
    o=config['output']; look=o.get('look','clean')
    title=end_text(script, direction)
    enabled=o['cta'] and config['website'] and title and not title.lower().startswith('none')
    if not enabled and look=='clean':
        shutil.copy2(master,destination)
        level=normalize_loudness(destination,config)
        return {'summary':f'CTA skipped by project/script policy; loudness {level["integrated"]} LUFS',
                'master':'final.mp4','loudness':level,'files':[{'path':'final.mp4','kind':'video'}]}
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
        # The story keeps the edit's picture untouched, never text.
        jobs.append({'output':str(work/'story.mp4'),'settings':{
            'canvas':{**canvas,'layout':'overlay'},'title':{'visible':False},'link':{'visible':False},
            'media':{'fit':'cover','trim_start':0,'trim_duration':start,'keep_audio':False},
            'export':export_settings,**CLEAN}})
    if enabled:
        text=balance(title); link=link_text(config['website'])
        jobs.append({'output':str(work/'card.mp4'),'still':str(work/'end_card.png'),
            'still_time':min(1.5,(duration-start)*.75),'settings':{
            'canvas':{**canvas,'layout':'stacked'},'title':{'visible':True,'text':text},
            'link':{'visible':True,'text':link},
            'media':{'fit':'contain','trim_start':start,'keep_audio':False},
            'export':export_settings,**CLEAN}})
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
    level=normalize_loudness(destination,config)
    check_video(destination,config)
    files=[{'path':'final.mp4','kind':'video'},{'path':'frame.json','kind':'source'}]
    if enabled:
        files.insert(1,{'path':'end_card.png','kind':'image'})
    what=(f'Frame {o["frame"].replace("_"," ")} from {start:.2f} s: "{title}" + {link_text(config["website"])}'
          if enabled else 'CTA skipped by project/script policy')
    return {'summary':f'{what}; {look} look; edit audio at {level["integrated"]} LUFS','master':'final.mp4',
            'end_card_start':start if enabled else None,'loudness':level,'files':files}


MAX_FREEZE = 1.9      # s of identical picture in the story (a held beat still has life in it)
MAX_BLACK = 0.75      # s of black picture in the story
MIN_CONTRAST = 30     # luma range (signalstats YHIGH-YLOW) below which a frame is washed out
FLAT_SECONDS = 1.0


def _gray(path, t, tools, size=(54, 68)):
    r = subprocess.run([tools['ffmpeg'], '-v', 'error', '-ss', f'{t:.3f}', '-i', str(path), '-frames:v', '1',
                        '-vf', f'scale={size[0]}:{size[1]}', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'],
                       capture_output=True, timeout=120)
    if r.returncode or len(r.stdout) != size[0] * size[1]:
        raise ContractError(f'Could not read a frame at {t:.2f} s of {path}')
    return r.stdout


def check_picture(path, config, story_end, master=None, check_freeze=True):
    """Bad animation and unreadable pictures, measured on the encoded video.

    Story (before story_end): no long frozen stretch, no black gap, no washed-out stretch.
    End card (after story_end, when master is given): Frame's card is really there, i.e. the
    picture differs from the edit master and carries dark type on a light ground."""
    tools = config['tools']; problems = []
    r = subprocess.run([tools['ffmpeg'], '-nostats', '-t', f'{story_end:.3f}', '-i', str(path), '-an', '-vf',
                        f'freezedetect=n=-60dB:d={MAX_FREEZE},blackdetect=d={MAX_BLACK}:pix_th=0.1,'
                        'fps=4,signalstats,metadata=print:file=-', '-f', 'null', '-'],
                       capture_output=True, text=True, timeout=600)
    log = r.stdout + r.stderr
    starts = [float(v) for v in re.findall(r'freeze_start: ([\d.]+)', log)]
    lengths = [float(v) for v in re.findall(r'freeze_duration: ([\d.]+)', log)]
    # An unfinished freeze at the cut-off point still counts up to story_end.
    freezes = [(a, round(d, 2)) for a, d in zip(starts, lengths + [story_end - a for a in starts[len(lengths):]])]
    if check_freeze:
        problems += [f'picture frozen {d:.1f} s from {a:.1f} s' for a, d in freezes if d >= MAX_FREEZE]
    problems += [f'black picture from {float(a):.1f} s' for a in re.findall(r'black_start:([\d.]+)', log)]
    lows = [float(v) for v in re.findall(r'signalstats.YLOW=([\d.]+)', log)]
    highs = [float(v) for v in re.findall(r'signalstats.YHIGH=([\d.]+)', log)]
    run_flat = longest = 0
    for lo, hi in zip(lows, highs):
        run_flat = run_flat + 1 if hi - lo < MIN_CONTRAST else 0
        longest = max(longest, run_flat)
    if longest / 4 >= FLAT_SECONDS:
        problems.append(f'washed-out, low-contrast picture for {longest / 4:.1f} s (luma range under '
                        f'{MIN_CONTRAST}): subjects will not read on a phone')
    card = None
    if master is not None:
        duration = float(json.loads(run([tools['ffprobe'], '-v', 'error', '-show_entries', 'format=duration',
                                          '-of', 'json', str(path)]).stdout)['format']['duration'])
        t = story_end + (duration - story_end) / 2
        framed, plain = _gray(path, t, tools), _gray(master, t, tools)
        diff = sum(abs(a - b) for a, b in zip(framed, plain)) / max(1, len(framed))
        card = {'difference': round(diff, 1), 'darkest': min(framed), 'lightest': max(framed)}
        if diff < 8 or max(framed) - min(framed) < 100:
            problems.append(f'the Frame end card is missing or unreadable at {t:.1f} s ({card})')
    if problems:
        raise ContractError('Picture QA: ' + '; '.join(problems))
    return {'freezes': freezes, 'flat_seconds': longest / 4, 'end_card': card}


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
