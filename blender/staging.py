"""Measured actor placement and camera containment, for Blender Python.

No scene reset, asset search, source save, animation rewrite or composition choice.
Coordinates are Blender world units, treated as meters (+Z up). See docs/worlds.md.
"""
import math
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector


def _vector(value, label):
    try:
        result = Vector(value)
        if len(result) != 3 or not all(math.isfinite(v) for v in result):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError(f'{label} must contain three finite coordinates') from None
    return result


def _subjects(subjects):
    if isinstance(subjects, (bpy.types.Object, dict)):
        subjects = [subjects]
    subjects = list(subjects)
    if not subjects:
        raise ValueError('Supply at least one subject')
    return subjects


def _corners(lower, upper):
    return [Vector((x, y, z)) for x in (lower.x, upper.x)
            for y in (lower.y, upper.y) for z in (lower.z, upper.z)]


def _points(subject):
    if isinstance(subject, dict):
        lo, hi = (_vector(subject[key], key) for key in ('min', 'max'))
        if any(lo[i] > hi[i] for i in range(3)):
            raise ValueError('Subject bounds are reversed')
        return _corners(lo, hi)
    if not isinstance(subject, bpy.types.Object):
        raise ValueError('Subjects must be Blender objects or explicit min/max bounds')
    deps = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in [subject, *subject.children_recursive]:
        if obj.type != 'MESH' or obj.hide_render:
            continue
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        try:
            points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        finally:
            evaluated.to_mesh_clear()
    if not points:
        raise ValueError(f'{subject.name}: no renderable mesh geometry')
    if not all(math.isfinite(v) for p in points for v in p):
        raise ValueError('Nonfinite subject geometry')
    return points


def _bounds(points):
    lower = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    upper = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return {'min': list(lower), 'max': list(upper), 'size': list(upper - lower),
            'center': list((lower + upper) / 2)}


def world_bounds(subjects):
    """JSON-safe bounds of evaluated vertices at the current frame, including children.

    Hidden-render meshes are excluded. An explicit {min,max} region is also accepted;
    callers can use this to deliberately frame an upper-body region of a single mesh.
    """
    bpy.context.view_layer.update()
    return _bounds([p for obj in _subjects(subjects) for p in _points(obj)])


def _ancestors(obj):
    result = []
    while obj.parent is not None:
        obj = obj.parent
        result.append(obj)
    return result


def import_actor(sourceblend, name, location, height_m, *, rig_name=None):
    """Append ONE local rig and its bound meshes under a new placement Empty.

    `name` names the placement root, not a source rig. Multi-rig files require
    `rig_name`. Preserve rig/mesh parent chains, shape keys, modifiers, actions and
    NLA. Normalize evaluated geometry at the CURRENT frame: XY center and Z floor
    become `location`, and height becomes `height_m`. Original animation is untouched.
    Move/rotate the returned root; its `staging_rig` property names the imported rig.
    """
    location = _vector(location, 'location')
    if not isinstance(height_m, (int, float)) or not math.isfinite(height_m) or height_m <= 0:
        raise ValueError('height_m must be positive and finite')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Supply a nonempty placement name')
    source = Path(sourceblend).resolve()
    if not source.is_file() or source.suffix.lower() != '.blend':
        raise ValueError('Supply an existing explicit .blend source')
    if bpy.data.filepath and Path(bpy.data.filepath).resolve() == source:
        raise ValueError('Import into a destination scene, not the source file itself')
    before = set(bpy.data.objects)
    created = []
    try:
        # Library append does not open the source scene or execute its text scripts.
        with bpy.data.libraries.load(str(source), link=False) as (src, dst):
            original_names = list(src.objects)
            dst.objects = list(original_names)  # Blender replaces this list's strings with IDs.
            dst.actions = list(src.actions)
        loaded = {old: obj for old, obj in zip(original_names, dst.objects) if obj}
        rigs = [(old, obj) for old, obj in loaded.items() if obj.type == 'ARMATURE'
                and (rig_name is None or old == rig_name)]
        if len(rigs) != 1:
            names = [old for old, obj in loaded.items() if obj.type == 'ARMATURE']
            raise ValueError(f'Select exactly one source armature using rig_name; available: {names}')
        rig = rigs[0][1]
        meshes = {obj for obj in loaded.values() if obj.type == 'MESH' and
                  (rig in _ancestors(obj) or any(m.type == 'ARMATURE' and m.object == rig
                                               for m in obj.modifiers))}
        if not meshes:
            raise ValueError('Selected rig has no bound meshes')
        keep = {rig, *meshes}
        # Keep structural parent/control empties, not unrelated siblings or scenery.
        pending = list(keep)
        while pending:
            obj = pending.pop()
            dependencies = _ancestors(obj)
            constraints = list(obj.constraints)
            if obj.type == 'ARMATURE':
                constraints += [c for bone in obj.pose.bones for c in bone.constraints]
            dependencies += [c.target for c in constraints if getattr(c, 'target', None)]
            dependencies += [m.object for m in obj.modifiers if getattr(m, 'object', None)]
            animations = [obj.animation_data]
            if obj.type == 'MESH' and obj.data.shape_keys:
                animations.append(obj.data.shape_keys.animation_data)
            for anim in animations:
                if anim:
                    dependencies += [t.id for driver in anim.drivers for variable in driver.driver.variables
                                     for t in variable.targets if isinstance(t.id, bpy.types.Object)]
            for dependency in dependencies:
                if dependency in keep:
                    continue
                if dependency.type != 'EMPTY' or dependency not in loaded.values():
                    raise ValueError('Actor depends on external scenery/another rig; prepare a self-contained actor')
                keep.add(dependency)
                pending.append(dependency)
        for obj in keep:
            if obj.library or (obj.data is not None and obj.data.library):
                raise ValueError('Actor has linked data; supply a local self-contained source')
            bpy.context.scene.collection.objects.link(obj)
        # Drop every unselected imported object, including other characters and scenery.
        for obj in set(bpy.data.objects) - before - keep:
            bpy.data.objects.remove(obj, do_unlink=True)
        for original_name, obj in loaded.items():
            if obj in keep:
                obj['staging_source_name'] = original_name
                obj.name = f'{name}.{original_name}'
        placement = bpy.data.objects.new(name, None)
        normalizer = bpy.data.objects.new(f'{name}.normalization', None)
        created.extend([placement, normalizer])
        for obj in created:
            bpy.context.scene.collection.objects.link(obj)
        normalizer.parent = placement
        # Only add an identity parent to original roots: their local animation stays intact.
        for obj in keep:
            if obj.parent is None:
                obj.parent = normalizer
                obj.matrix_parent_inverse = Matrix.Identity(4)
        bounds = world_bounds(placement)
        if bounds['size'][2] <= 1e-8:
            raise ValueError('Actor has zero evaluated height')
        factor = height_m / bounds['size'][2]
        base = Vector((bounds['center'][0], bounds['center'][1], bounds['min'][2]))
        normalizer.scale = (factor,) * 3
        normalizer.location = -base * factor
        placement.location = location
        placement['staging_rig'] = rig.name
        placement['staging_height_m'] = height_m
        placement['staging_reference_frame'] = bpy.context.scene.frame_current
        placement['staging_source'] = source.name
        bpy.context.view_layer.update()
        return placement
    except Exception:
        for obj in set(bpy.data.objects) - before:
            bpy.data.objects.remove(obj, do_unlink=True)
        raise


def frame_subjects(camera, subjects, margin=.08, view_direction=None):
    """Fit evaluated bounds without choosing shots, lens, angle, cuts or actor positions.

    margin is a fraction of EACH image edge (0 <= margin < .5). Preserve the current
    world camera rotation unless an explicit camera-to-subject direction is supplied.
    Perspective adjusts distance; orthographic adjusts ortho_scale. Preserve lens,
    sensor, shifts and render aspect; expand far clip if needed. Current frame only.
    Returns actual projected containment, NOT occlusion/face-direction verification.
    """
    if not isinstance(camera, bpy.types.Object) or camera.type != 'CAMERA':
        raise ValueError('camera must be a Blender camera object')
    if camera.data.type not in {'PERSP', 'ORTHO'}:
        raise ValueError('Only perspective and orthographic cameras are supported')
    if not isinstance(margin, (int, float)) or not math.isfinite(margin) or not 0 <= margin < .5:
        raise ValueError('margin must be a finite fraction in [0, .5)')
    if any(not c.mute and c.influence for c in camera.constraints):
        raise ValueError('Fit an unconstrained camera, then author camera animation explicitly')
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    subjects = _subjects(subjects)
    geometry = [_points(obj) for obj in subjects]
    # World AABB corners are conservative under every viewing angle, unlike object origins.
    bounds = [_bounds(points) for points in geometry]
    corners = [p for b in bounds for p in _corners(Vector(b['min']), Vector(b['max']))]
    center = Vector(_bounds(corners)['center'])
    rotation = camera.matrix_world.to_quaternion()
    if view_direction is not None:
        direction = _vector(view_direction, 'view_direction')
        if direction.length < 1e-8:
            raise ValueError('view_direction must be nonzero')
        rotation = direction.normalized().to_track_quat('-Z', 'Y')
    local = [rotation.inverted() @ (p - center) for p in corners]
    near = max(camera.data.clip_start * 1.01, .001)
    distance = max(p.z for p in local) + near
    frame = camera.data.view_frame(scene=scene)
    if camera.data.type == 'PERSP':
        xs, ys = [p.x / -p.z for p in frame], [p.y / -p.z for p in frame]
        middle_x, middle_y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        for axis, values, middle in ((0, xs, middle_x), (1, ys, middle_y)):
            span = max(values) - min(values)
            low, high = min(values) + margin * span, max(values) - margin * span
            for p in local:
                distance = max(distance, (p[axis] + low * p.z) / (low - middle),
                               (p[axis] + high * p.z) / (high - middle))
        distance += max(1e-5, abs(distance) * 1e-6)
        offset = Vector((middle_x * distance, middle_y * distance, 0))
    else:
        spans = [max(p[i] for p in frame) - min(p[i] for p in frame) for i in (0, 1)]
        ratio = max((max(p[i] for p in local) - min(p[i] for p in local)) /
                    (spans[i] * (1 - 2 * margin)) for i in (0, 1))
        camera.data.ortho_scale *= max(ratio * (1 + 1e-6), 1e-6)
        frame = camera.data.view_frame(scene=scene)
        offset = Vector(((min(p.x for p in frame) + max(p.x for p in frame)) / 2,
                         (min(p.y for p in frame) + max(p.y for p in frame)) / 2, 0))
        # Unequal subjects can have an off-center silhouette in this view even when
        # their union's WORLD-space AABB is centered. Center in camera XY as well.
        offset -= Vector(((min(p.x for p in local) + max(p.x for p in local)) / 2,
                          (min(p.y for p in local) + max(p.y for p in local)) / 2, 0))
        distance = max(distance, (camera.matrix_world.translation - center).length, 1.)
    camera.matrix_world = (Matrix.Translation(center + rotation @ Vector((0, 0, distance))
                                             - rotation @ offset) @ rotation.to_matrix().to_4x4())
    far = distance - min(p.z for p in local)
    camera.data.clip_end = max(camera.data.clip_end, far * 1.01 + .01)
    bpy.context.view_layer.update()
    records = []
    for subject, points, bound in zip(subjects, geometry, bounds):
        projected = [world_to_camera_view(scene, camera, p) for p in points]
        ndc = _bounds(projected)
        inside = (all(ndc['min'][i] >= margin - 1e-5 and ndc['max'][i] <= 1 - margin + 1e-5
                      for i in (0, 1)) and ndc['min'][2] >= camera.data.clip_start
                  and ndc['max'][2] <= camera.data.clip_end)
        records.append({'name': subject.get('name', 'region') if isinstance(subject, dict) else subject.name,
                        'world_bounds': bound, 'projected_min': ndc['min'], 'projected_max': ndc['max'],
                        'inside_margin': inside})
    return {'camera': camera.name, 'projection': camera.data.type, 'frame': scene.frame_current,
            'margin': margin, 'subjects': records, 'all_inside_margin': all(r['inside_margin'] for r in records),
            'validation': 'Current-frame frustum containment only; occlusion and face visibility not assessed'}
