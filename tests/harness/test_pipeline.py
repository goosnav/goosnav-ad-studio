"""Scripted workers + real media tools test scheduling, not creative quality."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from harness.config import load_config
from harness.store import Store
from harness.workflow import Engine


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='requires FFmpeg')
def test_two_ads_repair_and_package_with_real_media(tmp_path):
    video=tmp_path/'fixture.mp4';audio=tmp_path/'mix.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=24',
        '-f','lavfi','-i','sine=frequency=300:sample_rate=48000','-t','1',
        '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(video)],check=True)
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=300:sample_rate=48000',
        '-t','1','-c:a','pcm_s16le',str(audio)],check=True)
    c=load_config(None,{'count':2,'output':{'width':64,'height':64,'target_seconds':1,'min_seconds':1,'max_seconds':2,'cta':False,
        'folder':str(tmp_path/'delivered')}})
    store=Store(tmp_path/'state');s=store.create(c);calls=[];review_count=[0]
    def execute(profile,work,prompt,log,**kwargs):
        stage=work.name.split('-')[-1];calls.append(work.name)
        # critique_final and creative_qa use underscores, not hyphens.
        d={'summary':'test fixture','files':[]}
        def file(name,kind):d['files'].append({'path':name,'kind':kind})
        if stage=='research':d.update(brand_brief='fictional',creative_directions='object comedy',references=[])
        elif stage in ('write','revise'):
            d['scripts']=[dict(id=str(i),title='fixture',premise='test',script='test',visual_direction='motion',product='demo',cta='none') for i in range(6)]
        elif stage in ('critique','critique_final','board_review','review','creative_qa'):
            d.update(verdict='pass',findings=[])
            if stage=='review' and review_count[0]==0:
                d.update(verdict='revise',findings=[dict(target='0.5s',severity='important',problem='test repair',fix='rebuild')])
            if stage=='review':review_count[0]+=1
        elif stage=='select':d.update(selected=['0','1'],reason='distinct')
        elif stage=='direct':
            d['direction']=dict(duration=1,beats=[dict(start=0,end=1,shot='wide',picture='test pattern',sound='tone',faces=[])],
                                cast=[],lines=[],mix='tone only')
        elif stage=='assets':
            (work/'manifest.txt').write_text('original test source');file('manifest.txt','manifest')
            d['assets']=[dict(name='testsrc',source='generated',rights='test only',proxy=False)]
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=64x64','-frames:v','1',str(work/'b0.png')],check=True)
            file('b0.png','image');d['boards']=[dict(beat=0,image='b0.png')]
        elif stage=='audio':
            shutil.copy2(audio,work/'mix.wav');file('mix.wav','audio')
            (work/'timeline.json').write_text(json.dumps(dict(fps=24,sample_rate=48000,duration=1,
                dialogue=[],events=[],sound_rationale='test tone')));file('timeline.json','timeline')
            d.update(mix='mix.wav',timeline='timeline.json')
        elif stage=='animate':
            shutil.copy2(video,work/'preview.mp4');file('preview.mp4','video')
            (work/'source.py').write_text('# FFmpeg fixture; not a production ad\n');file('source.py','source')
            d.update(preview='preview.mp4',source='source.py')
        elif stage=='edit':
            shutil.copy2(video,work/'master.mp4');file('master.mp4','video');d['master']='master.mp4'
        else:raise AssertionError(stage)
        (work/'result.json').write_text(json.dumps(d));return {'kind':'ok'}
    def resolve(workers):return {'workers':{role:[{'provider':'codex','model':'fixture'}] for role in workers}}
    engine=Engine(store,execute=execute,resolve=resolve,auth=lambda _:True)
    state=engine.run(s['id'])
    assert state['status']=='complete',state.get('error') or [(t['id'],t['status'],t['feedback']) for t in state['tasks']]
    assert len([t for t in state['tasks'] if t['stage']=='package' and t['status']=='succeeded'])==2
    assert calls.count('ad-01-animate')==2 and calls.count('ad-01-direct')==1
    # A passing first critique makes the rewrite and second critique redundant.
    assert 'campaign-revise' not in calls and 'campaign-critique_final' not in calls
    assert calls.count('ad-01-board_review')==1
    out=tmp_path/'delivered'/s['id']
    assert sorted(f.name for f in out.iterdir())==['ad-01.mp4','ad-01.zip','ad-02.mp4','ad-02.zip']
    before=list(calls);engine.run(s['id']);assert calls==before
