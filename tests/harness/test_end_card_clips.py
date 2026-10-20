import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from harness.config import ConfigError, load_config
from harness.end_cards import prepare_clip
from harness.media import finish_frame


def fixture(tmp_path):
    root = tmp_path / 'relocatable library'
    root.mkdir()
    clip = root / 'floating.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=s=108x136:r=24', '-t', '0.5', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(clip)], check=True)
    (root / 'asset-catalog.json').write_text(json.dumps({'schema_version': 1, 'entries': [{
        'id': 'product-floating', 'kind': 'end_card_video', 'path': 'floating.mp4',
        'sha256': hashlib.sha256(clip.read_bytes()).hexdigest(), 'status': 'active'}]}))
    config = load_config(None, {'output': {'end_card_library': str(root),
        'end_card_clips': [{'product': 'Example Book', 'asset_id': 'product-floating', 'start': .1}]}})
    work = tmp_path / 'work'
    work.mkdir()
    return root, config, work


def test_clip_relocated_by_identity_trimmed_and_looped_without_audio(tmp_path):
    root, config, work = fixture(tmp_path)
    (root / 'floating.mp4').rename(root / 'moved.mp4')
    info = prepare_clip({'product': 'Example Book; use original artwork'}, None, config, work, 2)
    assert info['mode'] == 'library_clip'
    assert info['asset_id'] == 'product-floating'
    assert info['path'] == 'end_card_clip.mp4'
    probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                       '-of', 'json', str(work / info['path'])], capture_output=True, text=True, check=True).stdout)
    assert abs(float(probe['format']['duration']) - 2) < .05
    assert [s['codec_type'] for s in probe['streams']] == ['video']


def test_missing_or_retired_clip_falls_back_without_failing_ad(tmp_path):
    root, config, work = fixture(tmp_path)
    (root / 'floating.mp4').unlink()
    info = prepare_clip({'product': 'Example Book'}, None, config, work, 2)
    assert info['mode'] == 'master'
    assert info['reason']
    assert not (work / 'end_card_clip.mp4').exists()


def test_unrelated_unhydrated_asset_does_not_disable_ready_clip(tmp_path):
    root, config, work = fixture(tmp_path)
    index = root / 'asset-catalog.json'
    data = json.loads(index.read_text())
    (root / 'unhydrated.blend').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:' + 'a'*64 + '\nsize 42\n')
    data['entries'].append({'id': 'unrelated', 'kind': 'character', 'status': 'active',
                            'path': 'unhydrated.blend', 'sha256': 'a'*64})
    index.write_text(json.dumps(data))
    assert prepare_clip({'product': 'Example Book'}, None, config, work, 2)['mode'] == 'library_clip'


def test_exact_product_name_wins_over_broader_prefix(tmp_path):
    _, config, work = fixture(tmp_path)
    config['output']['end_card_clips'].append({'product': 'Example', 'asset_id': 'not-this-one'})
    info = prepare_clip({}, {'end_card': {'product': 'Example Book'}}, config, work, 2)
    assert info['mode'] == 'library_clip'
    assert info['asset_id'] == 'product-floating'


@pytest.mark.parametrize('defect', ['retired', 'wrong_kind', 'corrupt'])
def test_unusable_selected_clip_falls_back(tmp_path, defect):
    root, config, work = fixture(tmp_path)
    index = root / 'asset-catalog.json'
    data = json.loads(index.read_text())
    if defect == 'retired':
        data['entries'][0]['status'] = 'retired'
    elif defect == 'wrong_kind':
        data['entries'][0]['kind'] = 'character'
    else:
        (root / 'floating.mp4').write_bytes(b'not a video')
        data['entries'][0]['sha256'] = hashlib.sha256(b'not a video').hexdigest()
    index.write_text(json.dumps(data))
    assert prepare_clip({'product': 'Example Book'}, None, config, work, 2)['mode'] == 'master'


def test_explicit_card_product_can_select_clip_and_other_products_do_not(tmp_path):
    _, config, work = fixture(tmp_path)
    assert prepare_clip({'product': 'Another book'}, None, config, work, 2)['mode'] == 'master'
    info = prepare_clip({'product': 'Long freeform description'},
                        {'end_card': {'product': 'Example Book'}}, config, work, 2)
    assert info['mode'] == 'library_clip'


def test_clip_config_rejects_duplicate_products_and_bad_offsets():
    entry = {'product': 'Example Book', 'asset_id': 'book', 'start': 0}
    with pytest.raises(ConfigError):
        load_config(None, {'output': {'end_card_clips': [entry, entry]}})
    with pytest.raises(ConfigError):
        load_config(None, {'output': {'end_card_clips': [{**entry, 'start': -1}]}})


def test_frame_uses_moving_clip_but_keeps_original_audio(tmp_path):
    if not Path('harness.local.json').is_file():
        pytest.skip('local Frame runtime unavailable')
    _, source, work = fixture(tmp_path)
    config = load_config('harness.local.json')
    config['output'].update(source['output'], width=108, height=136, target_seconds=4,
                            min_seconds=4, max_seconds=4)
    master = tmp_path / 'story.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=108x136:r=24',
                    '-f', 'lavfi', '-i', 'sine=frequency=300:sample_rate=48000', '-t', '4',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(master)], check=True)
    result = finish_frame(master, {'product': 'Example Book'}, config, work, lambda: False,
                          {'end_card': {'seconds': 2, 'title': 'A book', 'picture': 'Product'}})
    assert result['end_card_media']['mode'] == 'library_clip'
    assert 'end_card_clip.mp4' in [f['path'] for f in result['files']]
    request = json.loads((work / 'frame.json').read_text())
    assert request['jobs'][-1]['input'] == str(work / 'end_card_clip.mp4')
    assert request['jobs'][-1]['settings']['media']['trim_start'] == 0
    def gray(time):
        return subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(time), '-i', str(work / 'final.mp4'),
                               '-frames:v', '1', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'],
                              capture_output=True, check=True).stdout
    assert max(gray(1)) < 3
    assert sum(abs(a-b) for a,b in zip(gray(2.05), gray(2.25))) / (108*136) > 1
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '3', '-i', str(work / 'final.mp4'),
                          '-t', '0.3', '-vn', '-ac', '1', '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    assert max(abs(int.from_bytes(pcm[i:i+2], 'little', signed=True)) for i in range(0, len(pcm), 2)) > 1000
