"""Shared source snippet for isolated Blender validators (no Blender import here)."""

# Blender's path enumerator reports one occurrence per reference, including local
# IDs' append-origin metadata. Subtract those occurrences, NOT whole path names:
# a shader node or other real input may use the very same path. Neither validator
# modifies IDs, clears provenance, makes linked data local, or saves the source.
EXTERNAL_PATH_SCAN = r'''
import os
from collections import Counter
def normalized_dependency_path(path):
    return os.path.normcase(os.path.abspath(bpy.path.abspath(path)))
origins = Counter(normalized_dependency_path(ref.filepath) for block in bpy.data.user_map()
                  if (ref := getattr(block, 'library_weak_reference', None)) and ref.filepath)
external = []
for path in bpy.utils.blend_paths(absolute=True, packed=False):
    key = normalized_dependency_path(path)
    if origins[key]:
        origins[key] -= 1
    else:
        external.append(path)
'''
