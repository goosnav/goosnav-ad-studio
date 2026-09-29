import os
"""Shot list for LIGHTS OUT. 96 BPM: a beat is 0.625 s (15 frames), a bar 2.5 s."""
import math, bpy
from mathutils import Vector
from lib import *

from timing import *
ALL = ['PAPER', 'BINDERY', 'GOOSKLERF', 'TUBE', 'ARMS', 'DOCK']

def cam_path(t, t0, t1, p0, p1, a0, a1, ease=smooth):
    u = ease(clamp((t - t0) / (t1 - t0)))
    return vlerp(p0, p1, u), vlerp(a0, a1, u)

# shot: (start, name, collections, lens, fstop or None, fn(t) -> (loc, target, focus_dist or None))
def sh_lights(t):
    p, a = cam_path(t, 0, 10, (0.3, -20.3, 19.4), (0.1, -15.5, 18.9), (0, 100, 9.5), (0, 100, 8.6))
    return p, a, None
def sh_reel(t):
    p, a = cam_path(t, T['REEL'], T['PRESS'], (-2.0, 14.5, 1.0), (-3.2, 18.0, 4.6), (-11, 36, 12.0), (-11, 42, 17.5))
    return p, a, None
def sh_press(t):
    p, a = cam_path(t, T['PRESS'], T['SHEETS'], (-5.4, 58.6, 3.6), (-6.0, 60.8, 4.0), (-11.8, 76, 7.0), (-11.8, 76, 6.6))
    return p, a, None
def sh_sheets(t):
    p, a = cam_path(t, T['SHEETS'], T['BIND'], (-8.2, 80.7, 3.7), (-8.45, 80.1, 3.45), (-11.55, 80.25, 1.35), (-11.55, 80.1, 1.35))
    return p, a, (a - p).length
def sh_bind(t):
    p, a = cam_path(t, T['BIND'], T['LINE'], (5.2 + 0.62, 50 - 0.62, 0.98 + 0.34), (5.2 + 0.46, 50 - 0.5, 0.98 + 0.24),
                    (5.2, 50.0, 0.99), (5.2, 50.0, 1.0))
    return p, a, (a - p).length
def sh_line(t):
    p, a = cam_path(t, T['LINE'], T['KILN'], (3.3, 57.8, 1.1), (3.3, 58.5, 1.1), (2.95, 62, 0.99), (2.95, 62.7, 0.99), ease=lambda x: x)
    return p, a, 1.25
def sh_kiln(t):
    p, a = cam_path(t, T['KILN'], T['QUENCH'], (11.6, 99.6, 1.5), (11.56, 99.66, 1.48), (11.0, 99.95, 1.3), (11.0, 99.98, 1.3))
    return p, a, (Vector((11.0, 99.95, 1.32)) - p).length
def sh_quench(t):
    p, a = cam_path(t, T['QUENCH'], T['SHUF'], (11.62, 100.22, 1.62), (11.55, 100.28, 1.56), (11.0, 100.72, 1.36), (11.0, 100.74, 1.36))
    return p, a, (a - p).length
def sh_shuf(t):
    p, a = cam_path(t, T['SHUF'], T['CRIMP'], (10.66, 101.12, 1.17), (10.63, 101.18, 1.16), (10.6, 101.7, 1.14), (10.6, 101.7, 1.14))
    return p, a, (a - p).length
def sh_crimp(t):
    p, a = cam_path(t, T['CRIMP'], T['TUBE'], (10.62, 102.72, 1.3), (10.64, 102.78, 1.28), (11.0, 103.24, 1.06), (11.0, 103.26, 1.06))
    return p, a, (a - p).length
def sh_tube(t):
    p, a = cam_path(t, T['TUBE'], T['TUBEUP'], (-11.35, 138.45, 1.62), (-11.5, 138.75, 1.52), (-12.0, 140, 1.36), (-12.0, 140, 1.38))
    return p, a, (a - p).length
def sh_tubeup(t):
    u = smoother(clamp((t - T['TUBEUP']) / 1.2))
    p = Vector((-11.55, 139.25, 1.55))
    look = vlerp((-12, 140, 2.6), (-12, 140.25, 33.0), u)
    return p, look, None
def sh_arms(t):
    p, a = cam_path(t, T['ARMS'], T['WAKE'], (3.6, 260.3, 1.9), (3.2, 261.0, 2.0), (0, 265.0, 1.8), (0, 265.3, 1.9))
    return p, a, None
def sh_wake(t):
    p, a = cam_path(t, T['WAKE'], T['ROW'], (4.1, 263.6, 2.3), (3.8, 264.2, 2.35), (0, 266.4, 1.9), (0, 266.8, 1.9))
    return p, a, None
def sh_row(t):
    p, a = cam_path(t, T['ROW'], T['DOCK'], (2.6, 258.5, 2.3), (3.4, 253.5, 3.1), (0.2, 280, 1.3), (0.2, 282, 1.2))
    return p, a, None
def sh_dock(t):
    p, a = cam_path(t, T['DOCK'], T['END'], (35.9, 170.05, 0.52), (36.25, 170.15, 0.46), (37.6, 170.5, 0.3), (37.6, 170.5, 0.28))
    return p, a, None

SHOTS = [
    (0.0, 'lights', ALL[:2], 26, None, sh_lights),
    (T['REEL'], 'reel', ['PAPER'], 21, None, sh_reel),
    (T['PRESS'], 'press', ['PAPER'], 24, None, sh_press),
    (T['SHEETS'], 'sheets', ['PAPER'], 32, 4.0, sh_sheets),
    (T['BIND'], 'bind', ['BINDERY'], 45, 2.8, sh_bind),
    (T['LINE'], 'line', ['BINDERY'], 28, 4.0, sh_line),
    (T['KILN'], 'kiln', ['GOOSKLERF'], 32, 4.0, sh_kiln),
    (T['QUENCH'], 'quench', ['GOOSKLERF'], 50, 2.8, sh_quench),
    (T['SHUF'], 'shuf', ['GOOSKLERF'], 45, 2.8, sh_shuf),
    (T['CRIMP'], 'crimp', ['GOOSKLERF'], 50, 2.8, sh_crimp),
    (T['TUBE'], 'tube', ['TUBE'], 40, 2.8, sh_tube),
    (T['TUBEUP'], 'tubeup', ['TUBE'], 18, None, sh_tubeup),
    (T['ARMS'], 'arms', ['ARMS'], 30, None, sh_arms),
    (T['WAKE'], 'wake', ['ARMS'], 30, None, sh_wake),
    (T['ROW'], 'row', ['ARMS'], 28, None, sh_row),
    (T['DOCK'], 'dock', ['DOCK'], 35, 5.6, sh_dock),
]

LAMP_N = {'lights': 28, 'reel': 20, 'press': 20, 'line': 18, 'arms': 12, 'row': 14, 'wake': 12, 'tubeup': 14}

PORT = {'lights': (0.85, 0, -4.0), 'reel': (0.8, 0, 0), 'press': (0.8, 0, 1.0), 'sheets': (0.9, 0, 0),
        'bind': (1.3, 0, 0.0), 'line': (1.3, 0, -0.22, (-0.3, 0, 0)), 'kiln': (1.2, 0, 0.1, (0, 0.18, 0)), 'quench': (1.0, 0, 0),
        'shuf': (1.45, 0, 0.01), 'crimp': (1.1, 0, 0), 'tube': (0.8, 0, 0), 'tubeup': (0.8, 0, 0),
        'arms': (0.85, 0, 0.3), 'wake': (0.9, 0, 0.2), 'row': (0.85, 0, 0.3), 'dock': (1.18, 0, 0.02)}

def shot_at(t):
    cur = SHOTS[0]
    for s in SHOTS:
        if t >= s[0]:
            cur = s
    return cur

_init = [False]
def update(t, sc, cam, H, S):
    if not _init[0]:
        H.lamps_setup(n_real=64, shadow_ys=(30, 42, 66, 78))
        _init[0] = True
    start, name, colls, lens, fstop, fn = shot_at(t)
    for c in ALL:
        bpy.data.collections[c].hide_render = c not in colls
    # --- light: lamps strike at the top; the far end (the arms) never quite warms up
    lamps_on = T['LAMPS']
    H.update_lamps(t, t_on=lamps_on, power=5000)
    for g, lo, y, x in H.lamps:
        if y > 236:
            k = 0.18
            g.color = (g.color[0] * k, g.color[1] * k * 0.5, g.color[2] * k * 0.4, 1)
            if lo is not None:
                lo.data.energy *= k
    if t > T['LAMPS_OFF'] and name == 'dock':
        for g, lo, y, x in H.lamps:
            g.color = (0, 0, 0, 1)
            if lo is not None: lo.data.energy = 0
    # moon: strong while the hall is dark, an accent afterwards; the dock gets the dawn instead
    moon = H.moon
    if name == 'dock':
        H.set_moon_dir((-0.95, 0.12, -0.16))
        moon.data.energy = 3.5; moon.data.color = (1.0, 0.86, 0.72)
    else:
        H.set_moon_dir((0.86, 0.22, -0.46))
        moon.data.color = (0.50, 0.62, 1.0)
        moon.data.energy = lerp(30.0, 7.0, smooth(ramp(t, 3.0, 9.0)))
    H.update_movers(t)
    # --- stations
    P = S['paper']
    if name in ('lights', 'reel', 'press', 'sheets'):
        P.update(t, printing=True, rain=1.0 if name in ('press',) else 0.0)
    if name in ('bind', 'line', 'lights', 'dock'):
        S['bind'].update(t, T['BIND_T0'], T['BIND_SLAM'])
        S['bind'].update_line(t)
    if name in ('kiln', 'quench', 'shuf', 'crimp'):
        S['gk'].update(t, T['DICE_T0'], T['SHUF'] + 0.1, T['CRIMP'] - 0.3)
    if name in ('tube', 'tubeup'):
        S['tube'].update(t, T['FIRE'])
    if name in ('arms', 'wake', 'row'):
        S['arms'].update(t, T['ARMS_T0'])
    if name == 'dock':
        S['dock'].update(t, T['DOCK'])
        S['dock'].door_light.data.energy = 3000
        S['dock'].fill.data.energy = 0.0 if t > T['LAMPS_OFF'] else 45
    # --- camera
    loc, tgt, focus = fn(t)
    if os.environ.get('LO_PORTRAIT'):
        # 4:5: the sensor fits the height, so the width narrows; per shot: lens scale, pull back (m), target lift (m)
        pv = PORT.get(name, (0.8, 0.0, 0.0))
        ls, back, lift = pv[:3]
        loc, tgt = Vector(loc), Vector(tgt) + Vector(pv[3] if len(pv) > 3 else (0, 0, 0)) + Vector((0, 0, lift))
        d = (tgt - loc).normalized()
        loc = loc - d * back
        lens = lens * ls
        if focus: focus += back
    if os.environ.get('CAMTEST'):
        v = [float(x) for x in os.environ['CAMTEST'].split(',')]
        loc, tgt, lens = Vector(v[0:3]), Vector(v[3:6]), v[6]
        focus = (tgt - loc).length
    loc = Vector(loc)
    # shake after press slams
    shake = 0.0
    if name in ('press', 'sheets'):
        for ts in P.slam_times(t - 0.6, t):
            shake += 0.03 * math.exp(-(t - ts) * 9) * (1.0 if name == 'press' else 0.4)
    if name == 'bind':
        age = t - T['BIND_SLAM']
        if age >= 0: shake += 0.012 * math.exp(-age * 7)
    if shake:
        loc += Vector((math.sin(t * 91) * shake, math.sin(t * 77 + 1) * shake * 0.5, math.sin(t * 83 + 2) * shake))
    cam.location = loc
    look_at(cam, tgt)
    # only the lamps that matter to this camera get real lights (Eevee legacy shades every light per pixel)
    fwd = (Vector(tgt) - loc).normalized()
    N = LAMP_N.get(name, 12)
    ahead = loc + fwd * (22 if N > 16 else 6)
    real = [(lo, (Vector(lo.location) - ahead).length) for g, lo, y, x in H.lamps if lo is not None]
    real.sort(key=lambda r: r[1])
    for i, (lo, d) in enumerate(real):
        lo.hide_render = i >= N
    cam.data.lens = lens
    cam.data.dof.use_dof = fstop is not None
    if fstop is not None:
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.focus_distance = focus if focus else (Vector(tgt) - loc).length
    # scene-level tweaks
    sc.eevee.volumetric_end = 260 if name in ('lights', 'reel', 'press', 'row', 'arms') else 120
