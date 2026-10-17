import array
import math
import wave

import pytest

from harness.contracts import ContractError
from harness.lipsync import mouth_curves

RATE = 48000


def stem(path, seconds, voiced):
    """A dialogue stem: syllable-like 220 Hz bursts inside voiced (start, end) windows, silence elsewhere."""
    x = array.array('h', [0]) * int(seconds * RATE)
    for a, b in voiced:
        for i in range(int(a * RATE), int(b * RATE)):
            syllable = 0.5 + 0.5 * math.sin(2 * math.pi * 4 * (i / RATE))   # 4 syllables/s
            x[i] = int(12000 * syllable * math.sin(2 * math.pi * 220 * i / RATE))
    with wave.open(str(path), 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(x.tobytes())
    return path


def timeline(lines, seconds=4):
    return {'fps': 24, 'sample_rate': RATE, 'duration': seconds,
            'dialogue': [{'speaker': s, 'text': 'words', 'start_sample': int(a * RATE), 'end_sample': int(b * RATE)}
                         for s, a, b in lines], 'events': []}


def test_each_speaker_moves_only_on_their_own_lines(tmp_path):
    lines = [('A', 0.5, 1.5), ('B', 2.0, 3.0)]
    m = mouth_curves(stem(tmp_path / 'd.wav', 4, [(a, b) for _, a, b in lines]), timeline(lines), 24)
    assert m['fps'] == 24 and m['frames'] == 96 and set(m['speakers']) == {'A', 'B'}
    a, b = m['speakers']['A'], m['speakers']['B']
    assert all(0 <= v <= 1 for v in a + b)
    assert sum(v > 0 for v in a[12:36]) > 12 and not any(a[48:96])     # A talks 0.5-1.5 s, then shut
    assert sum(v > 0 for v in b[48:72]) > 12 and not any(b[:44])        # B only on its own line
    assert len(set(a[12:36])) > 2                                        # it opens and closes, not a held gape


def test_stem_must_match_the_timeline(tmp_path):
    with pytest.raises(ContractError, match='dialogue stem'):
        mouth_curves(stem(tmp_path / 'd.wav', 2, [(0.5, 1.5)]), timeline([('A', 0.5, 1.5)], seconds=4), 24)
    with pytest.raises(ContractError, match='silent'):
        mouth_curves(stem(tmp_path / 's.wav', 4, []), timeline([('A', 0.5, 1.5)]), 24)


GUY = __import__('pathlib').Path.home() / 'Desktop/code/goosnav-3D-assets/assets/3D/characters/goosnav_guy_ps1.blend'
BUILD = '''
import bpy, sys, json
sys.path.insert(0, {blender!r})
import lipsync
args = json.loads(sys.argv[sys.argv.index("--") + 1])
scene = bpy.context.scene
scene.render.fps = 24; scene.frame_start = 1; scene.frame_end = 96
scene.render.resolution_x, scene.render.resolution_y = 432, 540
arm = bpy.data.objects["guy"]
head = arm.matrix_world @ arm.pose.bones["head"].head
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); scene.collection.objects.link(cam)
cam.location = (head.x, head.y - 2.2, head.z + 0.1)
cam.rotation_euler = (1.53, 0, 0); scene.camera = cam
if args["blocked"]:
    bpy.ops.mesh.primitive_cube_add(size=0.6, location=(head.x, head.y - 1.0, head.z + 0.1))
if args["mouths"]:
    lipsync.apply(args["mouths"], {{"A": "guy"}})
bpy.ops.wm.save_as_mainfile(filepath=args["out"])
'''


V10 = GUY.parents[1] / 'ps1guy' / 'ps1guy.blend'


@pytest.mark.skipif(not GUY.is_file() or not __import__('shutil').which('blender'), reason='needs Blender and the 3D library')
@pytest.mark.parametrize('rig', [GUY, V10], ids=['jaw-bone rig', 'v10 mouth-morph rig'])
def test_scene_check_on_the_real_rig(tmp_path, rig):
    import json, subprocess
    from pathlib import Path
    from harness.media import check_scene
    repo = Path(__file__).resolve().parents[2]
    lines = [('A', 0.5, 1.5)]
    mouths = tmp_path / 'mouths.json'
    mouths.write_text(json.dumps(mouth_curves(stem(tmp_path / 'd.wav', 4, [(0.5, 1.5)]), timeline(lines), 24)))
    build = tmp_path / 'build.py'; build.write_text(BUILD.format(blender=str(repo / 'blender')))
    def scene(name, blocked=False, keyed=True):
        out = tmp_path / f'{name}.blend'
        subprocess.run(['blender', '-b', str(rig), '--python-exit-code', '1', '--python', str(build), '--',
                        json.dumps({'out': str(out), 'blocked': blocked, 'mouths': str(mouths) if keyed else ''})],
                       check=True, capture_output=True)
        return out
    plan = [{'speaker': 'A', 'text': 'For who?', 'start': 0.5, 'end': 1.5}]
    good = check_scene(scene('good'), {'A': 'guy'}, plan, 24)
    assert good['lines'][0]['mouth_open'] > 0.3 and good['lines'][0]['face_visible'] > 0.9
    with pytest.raises(ContractError, match='mouth is open on only'):
        check_scene(scene('silent', keyed=False), {'A': 'guy'}, plan, 24)
    with pytest.raises(ContractError, match='face is visible'):
        check_scene(scene('blocked', blocked=True), {'A': 'guy'}, plan, 24)
    good_scene = tmp_path / 'good.blend'
    assert check_scene(good_scene, {'A': 'guy'}, plan, 24, models={'A': str(rig)})
    other = V10 if rig == GUY else GUY
    with pytest.raises(ContractError, match='not the library character'):
        check_scene(good_scene, {'A': 'guy'}, plan, 24, models={'A': str(other)})


def test_audio_stage_requires_a_stem_and_ships_mouth_curves(tmp_path):
    import json
    from harness.store import Store
    from harness.workflow import Engine
    from harness.config import load_config
    lines = [('A', 0.5, 1.5)]
    stem(tmp_path / 'voices.wav', 4, [(0.5, 1.5)])
    (tmp_path / 'timeline.json').write_text(json.dumps(timeline(lines)))
    engine = Engine(Store(tmp_path / 'home'))
    data = {'files': [{'path': 'timeline.json', 'kind': 'timeline'}], 'timeline': 'timeline.json'}
    with pytest.raises(ContractError, match='dialogue_stem'):
        engine.measure_mouths(data, tmp_path, load_config())
    data['files'].append({'path': 'voices.wav', 'kind': 'audio'}); data['dialogue_stem'] = 'voices.wav'
    engine.measure_mouths(data, tmp_path, load_config())
    assert data['mouths'] == 'mouths.json' and {'path': 'mouths.json', 'kind': 'timeline'} in data['files']
    assert json.loads((tmp_path / 'mouths.json').read_text())['speakers']['A']
