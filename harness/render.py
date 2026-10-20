"""Resumable EEVEE render/encode helper. All scene dependencies must be packed/local."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import time

from .contracts import contained, digest
from .learning import signature
from .blender_dependencies import EXTERNAL_PATH_SCAN


# Run inside Blender on EVERY invocation, including complete cache hits. A scene
# hash cannot attest to mutable fonts, sequencer inputs, or simulation sidecars.
_DEPENDENCY_CHECK = r'''
import bpy, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index('--') + 1], load_ui=False, use_scripts=False)
''' + EXTERNAL_PATH_SCAN + r'''
# Strong libraries and actual media are independently rejected even if they share
# a path with an origin reference. Origin metadata never authorizes external data.
external.extend(lib.filepath for lib in bpy.data.libraries)
for image in bpy.data.images:
    if image.source not in {'FILE', 'GENERATED', 'VIEWER'} or (image.source == 'FILE' and not image.packed_file):
        external.append('image: ' + image.name)
for font in bpy.data.fonts:
    if font.filepath != '<builtin>' and not font.packed_file:
        external.append('font: ' + font.name)
for sound in bpy.data.sounds:
    if not sound.packed_file:
        external.append('sound: ' + sound.name)
for collection in (bpy.data.movieclips, bpy.data.volumes, bpy.data.cache_files):
    external.extend('unsupported media/cache: ' + block.name for block in collection)

def point_cache(cache, label):
    if cache and (cache.use_external or cache.use_disk_cache or cache.is_baked):
        external.append('simulation cache: ' + label)

for scene in bpy.data.scenes:
    if scene.rigidbody_world:
        point_cache(scene.rigidbody_world.point_cache, scene.name)
    if scene.sequence_editor:
        for strip in scene.sequence_editor.sequences_all:
            if strip.type in {'IMAGE', 'MOVIE'}:
                external.append('sequencer media: ' + strip.name)
for obj in bpy.data.objects:
    for modifier in obj.modifiers:
        label = obj.name + '/' + modifier.name
        point_cache(getattr(modifier, 'point_cache', None), label)
        if modifier.type in {'MESH_CACHE', 'MESH_SEQUENCE_CACHE'} or (
                modifier.type == 'FLUID' and modifier.domain_settings):
            external.append('unsupported simulation/cache: ' + label)
        if modifier.type == 'NODES' and (getattr(modifier, 'simulation_bake_directory', '') or
                                        getattr(modifier, 'bake_directory', '')):
            external.append('geometry nodes bake: ' + label)
    for system in obj.particle_systems:
        point_cache(system.point_cache, obj.name + '/' + system.name)
if external:
    raise ValueError('Render cache requires a self-contained scene. Pack or remove external/unsupported dependencies: '
                     + ', '.join(sorted(set(external))))
print('AD_RENDER_DEPENDENCIES_OK')
'''


def validate_dependencies(scene, blender, timeout):
    try:
        result = subprocess.run([blender, '--background', '--factory-startup', '--disable-autoexec',
                                 '--python-exit-code', '1', '--python-expr', _DEPENDENCY_CHECK,
                                 '--', str(scene)], check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        detail = ((exc.stdout or '') + '\n' + (exc.stderr or ''))[-4000:]
        raise ValueError('Render dependency validation failed: ' + detail) from exc
    if 'AD_RENDER_DEPENDENCIES_OK' not in result.stdout.splitlines():
        raise ValueError('Blender did not confirm render dependency validation')


def render_key(scene, settings):
    return signature({'scene': digest(scene), 'settings': settings, 'renderer': 2})


def missing_ranges(folder, start, end, hashes):
    ranges = []
    for frame in range(start, end + 1):
        path = Path(folder) / f'{frame:06}.png'
        if path.is_file() and hashes.get(path.name) == digest(path):
            continue
        if ranges and ranges[-1][1] == frame - 1:
            ranges[-1] = (ranges[-1][0], frame)
        else:
            ranges.append((frame, frame))
    return ranges


def render(scene, audio, output, *, width=1080, height=1350, fps=24, seconds=9,
           effort='medium', fast=False, blender='blender', ffmpeg='ffmpeg', timeout=600):
    scene, audio, output = Path(scene).resolve(), Path(audio).resolve(), Path(output).resolve()
    if not scene.is_file() or not audio.is_file():
        raise ValueError('A saved scene and measured mixed audio are required')
    if not (64 <= width <= 4096 and 64 <= height <= 4096 and width % 2 == height % 2 == 0
            and 1 <= fps <= 60 and 0 < seconds <= 300 and timeout > 0):
        raise ValueError('Invalid render dimensions, frame rate, duration or timeout')
    started = time.monotonic()
    def left():
        available = timeout - (time.monotonic() - started)
        if available <= 0:
            raise TimeoutError('Render allowance exhausted; hashed frames retained for resume')
        return available
    checked_scene = digest(scene)
    validate_dependencies(scene, blender, left())
    if digest(scene) != checked_scene:
        raise ValueError('Scene changed during dependency validation; retry with a stable saved scene')
    left()
    scale = 2 if fast or effort != 'high' else 1.5
    settings = {'width': math.ceil(width / scale / 2) * 2, 'height': math.ceil(height / scale / 2) * 2,
                'fps': fps, 'samples': 4 if fast or effort == 'low' else 8 if effort == 'medium' else 16}
    key = render_key(scene, settings)
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = output.parent / '.render-cache' / key
    cache.mkdir(parents=True, exist_ok=True)
    journal = cache / 'frames.json'
    hashes = json.loads(journal.read_text()) if journal.exists() else {}
    end = round(seconds * fps)
    request = cache / 'request.json'
    helper = Path(__file__).resolve().parents[1] / 'blender' / 'render_scene.py'
    # The helper atomically checkpoints EACH frame, even if this process times out.
    # Keep Blender/shaders alive for the entire contiguous missing range.
    for start, stop in missing_ranges(cache, 1, end, hashes):
        request.write_text(json.dumps({**settings, 'start': start, 'end': stop, 'folder': str(cache)}))
        subprocess.run([blender, '--factory-startup', '--disable-autoexec', '-b', str(scene), '--python-exit-code', '1',
                        '--python', str(helper), '--', str(request)], check=True, timeout=left())
        hashes = json.loads(journal.read_text()) if journal.exists() else {}
        if missing_ranges(cache, start, stop, hashes):
            raise ValueError('Unverified rendered frames; helper checkpoint is missing or changed')
    # Never manufacture hashes here: only completed helper checkpoints authorize encoding.
    hashes = json.loads(journal.read_text()) if journal.exists() else {}
    if missing_ranges(cache, 1, end, hashes):
        raise ValueError('Unverified rendered frames before encoding')
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-framerate', str(fps), '-start_number', '1',
                    '-i', str(cache / '%06d.png'), '-i', str(audio), '-t', str(seconds),
                    '-vf', f'scale={width}:{height}:flags=neighbor', '-c:v', 'libx264', '-preset', 'veryfast',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-movflags', '+faststart',
                    str(output)], check=True, timeout=left())
    return {'video': str(output), 'scene_sha256': digest(scene), 'cache_key': key,
            'frames': end, 'settings': settings, 'wall_seconds': round(time.monotonic() - started, 2)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene', required=True); p.add_argument('--output', required=True)
    audio = p.add_mutually_exclusive_group(required=True)
    audio.add_argument('--audio')
    audio.add_argument('--production', help='Measured audio receipt; resolves its mix path and duration')
    p.add_argument('--rigs', help='With --production: check saved speaking rigs before rendering')
    for name, default in [('width',1080), ('height',1350), ('fps',24), ('seconds',9), ('timeout',600)]:
        p.add_argument('--' + name, type=int, default=default)
    p.add_argument('--effort', choices=('low','medium','high'), default='medium')
    p.add_argument('--fast', action='store_true'); p.add_argument('--blender', default='blender'); p.add_argument('--ffmpeg', default='ffmpeg')
    args = vars(p.parse_args(argv))
    receipt = args.pop('production')
    rigs = args.pop('rigs')
    if rigs and not receipt:
        p.error('--rigs requires --production')
    started = time.monotonic()
    if receipt:
        receipt = Path(receipt).resolve()
        data = json.loads(receipt.read_text())
        mix = contained(receipt.parent, data['mix'])
        entry = next((f for f in data['files'] if f['path'] == data['mix']), None)
        if not entry or entry.get('sha256') != digest(mix):
            raise ValueError('Changed or undeclared audio mix in production receipt')
        args.update(audio=str(mix), seconds=data['direction']['duration'])
        if rigs and data['direction']['lines']:
            from .media import check_scene
            from .execution import deadline
            cast = data['direction']['cast']
            with deadline(args['timeout']):
                check_scene(args['scene'], json.loads(Path(rigs).read_text()), data['direction']['lines'],
                            args['fps'], {c['speaker']: c['model'] for c in cast if c.get('model')},
                            blender=args['blender'])
            args['timeout'] -= time.monotonic() - started
    print(json.dumps(render(**args), indent=2))


if __name__ == '__main__':
    main()
