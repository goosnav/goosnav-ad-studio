"""DRAW YOUR OWN: render the story frames (the end card is Frame's job).

blender -b WORKDIR/scene.blend --python-exit-code 1 --python films/draw_your_own/render.py -- \
    films/draw_your_own/cut.json WORKDIR/frames [--samples 32] [--scale 100]

Writes numbered PNGs and skips frames that already exist, so an interrupted render resumes.
"""
import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index('--') + 1:]
cut = json.loads(Path(args[0]).read_text())
out = Path(args[1]).expanduser()
samples = int(args[args.index('--samples') + 1]) if '--samples' in args else 32
scale = int(args[args.index('--scale') + 1]) if '--scale' in args else 100
out.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
scene.eevee.taa_render_samples = samples
scene.render.resolution_percentage = scale
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
last = round(cut['end_card']['start'] * cut['fps']) - 1
for frame in range(0, last + 1):
    target = out / f'{frame:04d}.png'
    if target.exists() and target.stat().st_size > 0:
        continue
    scene.frame_set(frame)
    scene.render.filepath = str(target)
    bpy.ops.render.render(write_still=True)
print('RENDERED', last + 1, 'frames to', out)
