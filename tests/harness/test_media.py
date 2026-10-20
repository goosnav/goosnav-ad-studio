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
    c['output'].update(width=432,height=540,target_seconds=4,min_seconds=4,max_seconds=4,look='clean')
    p=tmp_path/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=432x540:r=24',
        '-f','lavfi','-i','sine=frequency=300:sample_rate=48000','-t','4','-c:v','libx264',
        '-pix_fmt','yuv420p','-c:a','aac','-ar','48000',str(p)],check=True)
    direction={'end_card':{'seconds':1.5,'title':'Read the book','picture':'black'}}
    result=finish_frame(p,{'cta':'ignored: the director title wins'},c,tmp_path,lambda:False,direction)
    final=tmp_path/'final.mp4'
    assert result['end_card_start']==2.5 and (tmp_path/'end_card.png').is_file()
    card = json.loads((tmp_path/'frame.json').read_text())['jobs'][-1]['settings']
    assert card['title']['text']=='Read the book'
    assert card['link']['font'] == 'sys-times'
    assert card['link']['underline'] is True
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
    rgb=subprocess.run(['ffmpeg','-v','error','-ss','3','-i',str(final),'-frames:v','1',
                        '-vf','crop=iw:100:0:440','-pix_fmt','rgb24','-f','rawvideo','-'],
                       capture_output=True,check=True).stdout
    blue = [rgb[i+2] > rgb[i] + 60 and rgb[i+2] > rgb[i+1] + 60 for i in range(0,len(rgb),3)]
    assert sum(blue) > 200  # A real blue hyperlink is present in the encoded end card.
    assert max(sum(blue[y*432:(y+1)*432]) for y in range(100)) > 180  # Continuous blue underline.


def test_long_end_titles_break_into_two_big_lines():
    from harness.media import balance
    assert balance('Read the book') == 'Read the book'
    assert balance('Goosnav Book Two. Keep yours.') == 'Goosnav Book Two.\nKeep yours.'
    assert balance('The card game nobody asked for') == 'The card game\nnobody asked for'


@pytest.mark.parametrize(('available', 'expected'), [
    ({'sys-times', 'termes-regular'}, 'sys-times'),
    ({'heros-bold', 'termes-regular'}, 'termes-regular'),
])
def test_times_link_uses_real_face_or_bundled_times_never_sans(available, expected):
    from harness.frame_runner import link_font
    assert link_font('sys-times', available) == expected


@pytest.mark.parametrize('look', ['clean', 'ps1'])
def test_2002_card_dithers_picture_but_story_and_text_stay_steady(tmp_path, look):
    from pathlib import Path
    if not Path('harness.local.json').is_file():
        pytest.skip('local Frame config unavailable')
    c=load_config('harness.local.json')
    if not Path(c['tools']['frame_python']).is_file():
        pytest.skip('local Frame runtime unavailable')
    c['output'].update(width=432,height=540,target_seconds=4,min_seconds=4,max_seconds=4,look=look)
    p=tmp_path/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=0x808080:s=432x540:r=24',
        '-f','lavfi','-i','sine=frequency=300:sample_rate=48000','-t','4','-c:v','libx264',
        '-pix_fmt','yuv420p','-c:a','aac','-ar','48000',str(p)],check=True)
    finish_frame(p,{},c,tmp_path,lambda:False,{'end_card':{'seconds':2,'title':'Read the book','picture':'grey'}})
    def gray(t):
        r=subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(tmp_path/'final.mp4'),'-frames:v','1',
            '-pix_fmt','gray','-f','rawvideo','-'],capture_output=True,check=True)
        return r.stdout
    story=gray(1)
    rows=[sum(story[y*432:(y+1)*432])/432 for y in range(0,540)]
    assert max(rows)-min(rows)<3                      # story picture untouched: no scanlines/crunch
    ink=lambda f:sum(v<60 for v in f[:432*120])       # dark title pixels in the top band
    assert ink(gray(2.1)) > 0 and abs(ink(gray(2.1))-ink(gray(3.8))) < 50   # whole title at once, steady
    card = gray(3)
    center = [card[y*432+x] for y in range(240,280) for x in range(196,236)]
    assert max(center) - min(center) > 4  # Ordered dither adds a real pattern to flat midtones.
    request = json.loads((tmp_path/'frame.json').read_text())
    assert request['jobs'][0]['settings']['media_fx']['mode'] == 'none'
    assert request['jobs'][-1]['settings']['media_fx']['mode'] == 'ps1'
    assert request['jobs'][-1]['settings']['retro']['aliased'] is True
    assert request['jobs'][-1]['settings']['retro']['jitter'] is False


def _clip(path, source, seconds=4, size='108x136'):
    spec=source+(':' if '=' in source else '=')+f's={size}:r=24'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',spec,'-f','lavfi',
        '-i','sine=frequency=300:sample_rate=48000','-t',str(seconds),'-c:v','libx264','-pix_fmt','yuv420p',
        '-c:a','aac','-ar','48000',str(path)],check=True)
    return path


def test_full_framing_keeps_picture_clean_with_the_new_hyperlink(tmp_path):
    from pathlib import Path
    if not Path('harness.local.json').is_file():
        pytest.skip('local Frame config unavailable')
    c = load_config('harness.local.json')
    c['output'].update(width=108, height=136, frame='full', target_seconds=4, min_seconds=4, max_seconds=4)
    master = tmp_path/'input.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=0x808080:s=108x136:r=24',
                    '-f', 'lavfi', '-i', 'sine=frequency=300:sample_rate=48000', '-t', '4',
                    '-vf', r'drawbox=x=0:y=0:w=24:h=24:color=white:t=fill:enable=gte(t\,2)',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', str(master)],
                   check=True)
    finish_frame(master, {}, c, tmp_path, lambda: False,
                 {'end_card': {'title': 'Read', 'picture': 'Grey'}})
    settings = json.loads((tmp_path/'frame.json').read_text())['jobs'][0]['settings']
    assert settings['link']['font'] == 'sys-times'
    assert settings['link']['underline'] is True
    assert settings['media_fx']['mode'] == 'none'
    pixels = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '1', '-i', str(tmp_path/'final.mp4'),
                             '-frames:v', '1', '-vf', 'crop=12:12:48:60', '-pix_fmt', 'gray',
                             '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    assert max(pixels) - min(pixels) < 4


def test_picture_qa_rejects_frozen_flat_and_missing_card(tmp_path):
    from harness.media import check_picture
    c=load_config(None,{'output':{'width':108,'height':136,'target_seconds':4}})
    moving=_clip(tmp_path/'moving.mp4','testsrc2')
    assert check_picture(moving,c,story_end=4)['freezes']==[]
    with pytest.raises(ContractError,match='frozen'):
        check_picture(_clip(tmp_path/'still.mp4','smptebars'),c,story_end=4)
    with pytest.raises(ContractError,match='contrast'):
        check_picture(_clip(tmp_path/'flat.mp4','color=0xb0b0b0'),c,story_end=4,check_freeze=False)
    with pytest.raises(ContractError,match='end card'):
        check_picture(moving,c,story_end=2,master=moving)   # "framed" video identical to the master
def test_compact_picture_allows_short_hold_but_not_mostly_static_story(tmp_path):
    from harness.config import load_config
    from harness.media import check_picture
    from harness.contracts import ContractError
    import subprocess
    moving = tmp_path / 'held-reaction.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=160x200:rate=24:duration=4', '-vf',
                    'tpad=stop_mode=clone:stop_duration=2.2', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(moving)], check=True)
    c = load_config()
    result = check_picture(moving, c, story_end=6.2, max_frozen_fraction=.5)
    assert result['freezes'] and result['freezes'][0][1] > 2
    with pytest.raises(ContractError, match='frozen'):
        check_picture(_clip(tmp_path/'still-compact.mp4', 'smptebars'), c, story_end=4,
                      max_frozen_fraction=.5)


def test_compact_picture_counts_short_stills_across_multiple_shots(tmp_path):
    from harness.config import load_config
    from harness.media import check_picture
    from harness.contracts import ContractError
    import subprocess
    slideshow = tmp_path / 'slideshow.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=160x200:rate=24:duration=6', '-vf', 'fps=2/3,fps=24',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(slideshow)], check=True)
    with pytest.raises(ContractError, match='picture frozen'):
        check_picture(slideshow, load_config(), story_end=6, max_frozen_fraction=.5)
