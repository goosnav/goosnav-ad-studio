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
    c=load_config(None,{'output':{'width':64,'height':64,'min_seconds':1,'max_seconds':2,'cta':False}})
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
