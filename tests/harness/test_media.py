import json
import shutil
import subprocess
import wave

import pytest

from harness.config import load_config
from harness.contracts import ContractError
from harness.media import check_video, check_audio, finish_frame


def test_timeline_cannot_overrun_audio(tmp_path):
    p=tmp_path/'mix.wav'
    with wave.open(str(p),'wb') as w:
        w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(b'\x00\x00'*48000)
    t=tmp_path/'timeline.json';t.write_text(json.dumps({'sample_rate':48000,'fps':24,'duration':1,
       'dialogue':[{'start_sample':0,'end_sample':96000,'text':'cut off','speaker':'A'}], 'events':[]}))
    with pytest.raises(ContractError):check_audio(p,t,load_config())


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg missing')
def test_real_video_validation_and_no_cta_audio_preservation(tmp_path):
    p=tmp_path/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=24',
        '-f','lavfi','-i','sine=frequency=300:sample_rate=48000','-t','1','-c:v','libx264',
        '-pix_fmt','yuv420p','-c:a','aac',str(p)],check=True)
    c=load_config(None,{'output':{'width':64,'height':64,'target_seconds':1,'min_seconds':1,'max_seconds':2,'cta':False}})
    assert check_video(p,c)['audio']
    out=tmp_path/'out';out.mkdir()
    result=finish_frame(str(p),{'cta':'None: fictional demo'},c,out,cancelled=lambda:False)
    assert check_video(out/result['master'],c)['audio']
    c['output']['width']=128
    with pytest.raises(ContractError):check_video(p,c)


def test_missing_frame_does_not_silently_skip_requested_cta(tmp_path):
    c=load_config(None,{'website':'example.com'})
    with pytest.raises(ContractError):
        finish_frame('/missing.mp4',{'cta':'Buy the book'},c,tmp_path,cancelled=lambda:False)


def test_frame_writes_a_native_end_card_and_keeps_the_audio(tmp_path):
    from pathlib import Path
    if not Path('harness.local.json').is_file():
        pytest.skip('local Frame config unavailable')
    c=load_config('harness.local.json')
    if not Path(c['tools']['frame_python']).is_file():
        pytest.skip('local Frame runtime unavailable')
    c['output'].update(width=432,height=540,target_seconds=4,min_seconds=4,max_seconds=4)
    p=tmp_path/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=432x540:r=24',
        '-f','lavfi','-i','sine=frequency=300:sample_rate=48000','-t','4','-c:v','libx264',
        '-pix_fmt','yuv420p','-c:a','aac','-ar','48000',str(p)],check=True)
    direction={'end_card':{'seconds':1.5,'title':'Read the book','picture':'black'}}
    result=finish_frame(p,{'cta':'ignored: the director title wins'},c,tmp_path,lambda:False,direction)
    final=tmp_path/'final.mp4'
    assert result['end_card_start']==2.5 and (tmp_path/'end_card.png').is_file()
    assert json.loads((tmp_path/'frame.json').read_text())['settings']['title']['text']=='Read the book'
    def brightness(t,crop='iw:ih:0:0'):
        r=subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(final),'-frames:v','1',
            '-vf',f'crop={crop}','-pix_fmt','gray','-f','rawvideo','-'],capture_output=True,check=True)
        return sum(r.stdout)/len(r.stdout)
    assert brightness(1)<2                      # story untouched
    assert brightness(3.5,'iw:20:0:0')>250      # Frame's white card above the picture
    assert brightness(3.5,'40:40:196:250')<20   # the closing picture sits inside the card
    report=check_video(final,c)
    assert abs(report['duration']-4)<.1
    pcm=subprocess.run(['ffmpeg','-v','error','-ss','3','-i',str(final),'-t','0.5','-vn','-f','s16le','-ac','1','-'],
                       capture_output=True,check=True).stdout
    assert max(abs(int.from_bytes(pcm[i:i+2],'little',signed=True)) for i in range(0,len(pcm),2))>1000


def test_long_end_titles_break_into_two_big_lines():
    from harness.media import balance
    assert balance('Read the book') == 'Read the book'
    assert balance('Goosnav Book Two. Keep yours.') == 'Goosnav Book Two.\nKeep yours.'
    assert balance('The card game nobody asked for') == 'The card game\nnobody asked for'
