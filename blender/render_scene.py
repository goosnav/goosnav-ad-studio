"""Internal Blender side of harness.render; reject mutable external dependencies."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import bpy

request = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text())
external = [i.name for i in bpy.data.images if i.source == 'FILE' and not i.packed_file]
external += [lib.filepath for lib in bpy.data.libraries]
if external:
    raise ValueError('Pack textures and make linked data local before rendering: ' + ', '.join(external))
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.taa_render_samples = request['samples']
scene.render.resolution_x = request['width']; scene.render.resolution_y = request['height']
scene.render.resolution_percentage = 100
scene.render.fps = request['fps']
scene.render.image_settings.file_format = 'PNG'
scene.render.threads_mode = 'FIXED'; scene.render.threads = 4
folder = Path(request['folder'])
journal = folder / 'frames.json'
hashes = json.loads(journal.read_text()) if journal.exists() else {}
for frame in range(request['start'], request['end'] + 1):
    scene.frame_set(frame)
    path = folder / f'{frame:06}.png'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    # Only journal a completed PNG of the requested size, never a partial write.
    data = path.read_bytes()
    if (len(data) < 45 or data[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            or struct.unpack('>II', data[16:24]) != (request['width'], request['height'])
            or data[-12:] != b'\x00\x00\x00\x00IEND\xaeB`\x82'):
        raise ValueError(f'Invalid rendered frame {frame}')
    hashes[path.name] = hashlib.sha256(data).hexdigest()
    temporary = journal.with_suffix('.tmp')
    with temporary.open('w') as handle:
        json.dump(hashes, handle)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(journal)
