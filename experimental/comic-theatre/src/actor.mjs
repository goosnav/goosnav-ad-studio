import * as THREE from 'three';
import { clone } from 'three/addons/utils/SkeletonUtils.js';

// Provenance: Homunculus web/room.js (rest-relative bone poses), browser-room.js
// (sealed-face overlay coordinates and head.attach). No runtime checkout imports.
export const clamp = (n, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, n));
export const ease = n => { const x = clamp(n); return x * x * (3 - 2 * x); };
const number = (n, fallback = 0) => Number.isFinite(n) ? n : fallback;

export function sampleMouth(curve, seconds) {
  if (!curve?.length || seconds < curve[0].t || seconds > curve.at(-1).t) return 0;
  for (let i = 1; i < curve.length; i++) {
    if (seconds <= curve[i].t) {
      const a = curve[i - 1], b = curve[i];
      return clamp(THREE.MathUtils.lerp(a.value, b.value, clamp((seconds - a.t) / (b.t - a.t || 1))));
    }
  }
  return clamp(curve.at(-1).value);
}

const expressions = {
  neutral: { brow: -.12, tilt: 0 }, calm: { brow: -.12, tilt: 0 },
  curious: { brow: .22, asymmetry: .18, tilt: -.10 },
  skeptical: { brow: -.26, asymmetry: .38, tilt: .10 },
  deadpan: { brow: 0, tilt: 0 }, amused: { brow: .12, smile: .6, tilt: -.05 },
  happy: { brow: .22, smile: 1 }, surprised: { brow: .55, tilt: -.08 },
  annoyed: { brow: -.40, tilt: .03 }, sad: { brow: .4, tilt: .08 },
  thoughtful: { brow: .12, tilt: .06 }, dry: { brow: 0, tilt: 0 },
  pleased: { brow: .18, smile: .7 }, concerned: { brow: .35, tilt: .06 },
  exasperated: { brow: -.38, asymmetry: .18, tilt: -.09 },
};

export function createActor(source, id, index = 0) {
  const root = new THREE.Group();
  root.name = `actor-${id}`;
  const body = clone(source);
  root.add(body);
  const bones = {}, rest = {}, skeletons = [], eyes = [];
  body.traverse(o => {
    if (o.isBone) {
      const key = o.name.replaceAll('.', '');
      bones[key] = o;
      rest[key] = { q: o.quaternion.clone(), p: o.position.clone(), s: o.scale.clone() };
    }
    if (o.isSkinnedMesh) { o.frustumCulled = false; skeletons.push(o.skeleton); }
    if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; }
    if (o.isMesh && ['eye_white', 'eye_black'].includes(o.material?.name)) {
      // Own the geometry before a per-frame eye squeeze; never mutate the other
      // actor or the source GLB's shared vertex buffers.
      o.geometry = o.geometry.clone();
      o.geometry.computeBoundingBox();
      const bounds = o.geometry.boundingBox;
      // The bundled export is Y-up in mesh space. Use each authored primitive's
      // own center: pupils and sclera do not share exactly the same height.
      eyes.push({ mesh: o, positions: o.geometry.attributes.position.array.slice(), centerY: (bounds.min.y + bounds.max.y) / 2 });
    }
  });
  if (!bones.head || !bones.upper_armL || !bones.handR || !skeletons.length) {
    throw new Error('Actor GLB must contain the Homunculus head and arm skeleton');
  }
  const dark = new THREE.MeshStandardMaterial({ color: 0x372722, roughness: .95 });
  const face = new THREE.Group();
  face.name = 'head-attached-expression';
  face.position.set(0, 1.525, .147);
  // A shallow solid aperture remains visible in three-quarter long-nose shots.
  const mouth = new THREE.Mesh(new THREE.SphereGeometry(.038, 20, 12), dark);
  mouth.position.set(0, -.006, .02);
  mouth.scale.set(1.35, .08, .16);
  face.add(mouth);
  const lip = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
    new THREE.Vector3(-.10, -.018, 0), new THREE.Vector3(-.05, .002, .009),
    new THREE.Vector3(0, .009, .012), new THREE.Vector3(.05, .002, .009), new THREE.Vector3(.10, -.018, 0),
  ]), 20, .006, 6, false), dark);
  face.add(lip);
  root.add(face);
  root.updateMatrixWorld(true);
  bones.head.attach(face);
  const brows = [-1, 1].map(sign => {
    const brow = new THREE.Mesh(new THREE.CapsuleGeometry(.007, .077, 4, 8), dark);
    const anchor = new THREE.Group();
    anchor.position.set(sign * .095, 1.659, .083);
    brow.rotation.z = Math.PI / 2;
    anchor.add(brow);
    root.add(anchor); root.updateMatrixWorld(true); bones.head.attach(anchor);
    return { anchor, q: anchor.quaternion.clone(), p: anchor.position.clone(), sign };
  });
  let state = {};
  function pose(name, x = 0, y = 0, z = 0) {
    if (bones[name]) bones[name].quaternion.copy(rest[name].q).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z)));
  }

  function apply({ time, line, listening, gaze = 0, held = 0, reading = false, seed = 0 }) {
    for (const [key, bone] of Object.entries(bones)) {
      bone.position.copy(rest[key].p); bone.quaternion.copy(rest[key].q); bone.scale.copy(rest[key].s);
    }
    const ownsLine = line?.speaker === id;
    const speaking = ownsLine && line.type === 'line';
    const age = line ? time - line.start : 0;
    const requested = line?.reaction;
    const reactionActive = listening && requested && (!requested.actor || requested.actor === id) &&
      (requested.at === 'line_end' ? line.type === 'hold' : line.type === 'line') && age < (requested.duration ?? Infinity);
    const reaction = reactionActive ? requested : {};
    const emotion = (ownsLine ? line?.emotion : reaction.emotion) || 'neutral';
    const faceControl = ownsLine ? (line.face || {}) : (reaction.face || {});
    const exp = { ...(expressions[emotion] || expressions.neutral), ...faceControl };
    const envelope = line ? ease(age / .25) * ease((line.end - time) / .3) : 0;
    const mouthValue = speaking ? sampleMouth(line.mouth, age) : 0;
    const phase = time * 1.7 + index * 2.1 + (seed % 100) * .13;
    const gesture = (ownsLine ? line.gesture : reaction.gesture) || 'none';
    let tilt = number(exp.tilt) * envelope;
    if (gesture === 'tilt' || gesture === 'head_tilt') tilt += .13 * envelope;
    const gazeTarget = reading || held > .5 || gesture === 'page_glance' ? 'book' : faceControl.gaze ?? reaction.gaze ?? (listening ? 'speaker' : 'partner');
    const yaw = gazeTarget === 'book' ? 0 : typeof gazeTarget === 'number' ? clamp(gazeTarget, -.65, .65)
      : gazeTarget === 'camera' ? -root.rotation.y : gaze;
    const down = gazeTarget === 'book' ? .55 : 0;
    const nod = gesture === 'nod' ? Math.sin(age * 5) * .13 * envelope : 0;
    pose('chest', Math.sin(phase) * .008, 0, 0);
    pose('head', down + nod + (speaking ? Math.sin(age * 4) * .025 * envelope : -.025), yaw, tilt);
    for (const [side, sign] of [['L', 1], ['R', -1]]) {
      let arm = .08, elbow = .10, spread = sign * .04;
      if (gesture === 'shrug') { arm += .22 * envelope; elbow += .8 * envelope; spread += sign * .28 * envelope; }
      if ((gesture === 'explain' || gesture === 'point' || gesture === 'offer') && side === 'R') {
        arm += .65 * envelope; elbow += .65 * envelope;
        spread -= .2 * envelope;
      }
      pose(`upper_arm${side}`, arm, 0, spread);
      pose(`forearm${side}`, elbow);
      // Subtle deliberate finger curl; never random perturbations on a grip.
      for (const digit of ['f11', 'f21', 'f31']) pose(`${digit}${side}`, .15 - held * .05);
      for (const digit of ['f12', 'f22', 'f32']) pose(`${digit}${side}`, held * .08);
    }
    mouth.scale.set(1.35 - mouthValue * .25, .07 + mouthValue * 1.05, .19);
    mouth.visible = mouthValue > .025;
    lip.visible = mouthValue <= .25;
    lip.scale.y = 1 - 1.8 * number(faceControl.mouth_curve, number(exp.smile));
    const browValues = [number(faceControl.brow_left, number(exp.brow, -.12)),
      number(faceControl.brow_right, number(exp.brow, -.12) + number(exp.asymmetry))].map(n => clamp(n, -1, 1));
    brows.forEach(({ anchor, q, p, sign }, i) => {
      anchor.position.copy(p);
      anchor.quaternion.copy(q).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0,
        sign * browValues[i])));
    });
    const blinkMode = faceControl.blink || 'auto';
    const blinkAge = blinkMode === 'once' ? age - .35 : ((time + index * 1.3 + (seed % 7) * .23) % 4.7) - 4.35;
    const blink = blinkMode === 'off' || blinkAge < 0 || blinkAge > .18 ? 0 : Math.sin(blinkAge / .18 * Math.PI);
    const eyeOpen = clamp(number(faceControl.eye_open, 1)) * (1 - blink);
    for (const { mesh, positions, centerY } of eyes) {
      const attr = mesh.geometry.attributes.position;
      // Preserve the exact original Float32 vertices whenever the eye is open.
      attr.array.set(positions);
      if (eyeOpen < 1) for (let i = 0; i < attr.count; i++) attr.setY(i, centerY + (positions[i * 3 + 1] - centerY) * Math.max(.015, eyeOpen));
      attr.needsUpdate = true;
    }
    root.updateMatrixWorld(true);
    state = { id, mode: speaking ? 'talk' : listening ? 'listen' : 'idle', emotion, gesture, mouth: mouthValue,
      gaze: yaw, gazeTarget, brows: browValues, eyeOpen, head: bones.head.quaternion.toArray(), faceAttachedToHead: face.parent === bones.head };
  }

  // Analytic two-link reach. Every solve starts from this frame's rest-relative
  // pose; lengths and the elbow pole are bounded, with no iterative frame history.
  function grip(targets, weight = 1, bookRotation = null) {
    const errors = [], palmAlignmentErrors = [];
    for (const [i, side] of ['L', 'R'].entries()) {
      const upper = bones[`upper_arm${side}`], lower = bones[`forearm${side}`], hand = bones[`hand${side}`];
      root.updateMatrixWorld(true);
      const a = upper.getWorldPosition(new THREE.Vector3());
      const b = lower.getWorldPosition(new THREE.Vector3());
      const c = hand.getWorldPosition(new THREE.Vector3());
      const requested = targets[i].clone();
      const target = c.clone().lerp(requested, clamp(weight));
      const l1 = a.distanceTo(b), l2 = b.distanceTo(c);
      const axis = target.clone().sub(a), distance = clamp(axis.length(), Math.abs(l1 - l2) + .001, l1 + l2 - .001);
      axis.normalize();
      const pole = new THREE.Vector3(side === 'L' ? .35 : -.35, -.9, -.35).applyQuaternion(root.quaternion);
      pole.addScaledVector(axis, -pole.dot(axis)).normalize();
      const along = (l1 * l1 - l2 * l2 + distance * distance) / (2 * distance);
      const elbow = a.clone().addScaledVector(axis, along).addScaledVector(pole, Math.sqrt(Math.max(0, l1 * l1 - along * along)));
      const end = a.clone().addScaledVector(axis, distance);
      function aim(bone, child, point) {
        root.updateMatrixWorld(true);
        const origin = bone.getWorldPosition(new THREE.Vector3());
        const from = child.getWorldPosition(new THREE.Vector3()).sub(origin).normalize();
        const to = point.clone().sub(origin).normalize();
        const world = bone.getWorldQuaternion(new THREE.Quaternion());
        world.premultiply(new THREE.Quaternion().setFromUnitVectors(from, to));
        bone.quaternion.copy(bone.parent.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(world));
      }
      aim(upper, lower, elbow); aim(lower, hand, end);
      if (bookRotation) {
        const forward = new THREE.Vector3(side === 'L' ? -1 : 1, 0, 0).applyQuaternion(bookRotation);
        const normal = new THREE.Vector3(0, 1, 0).applyQuaternion(bookRotation);
        const across = new THREE.Vector3().crossVectors(forward, normal).normalize();
        const desired = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(across, forward, normal));
        const local = hand.parent.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(desired);
        hand.quaternion.slerp(local, clamp(weight));
        root.updateMatrixWorld(true);
        const actual = new THREE.Vector3(0, 0, 1).applyQuaternion(hand.getWorldQuaternion(new THREE.Quaternion()));
        palmAlignmentErrors.push(1 - clamp(actual.dot(normal), -1, 1));
      }
      root.updateMatrixWorld(true);
      errors.push(hand.getWorldPosition(new THREE.Vector3()).distanceTo(requested));
    }
    return { errors, palmAlignmentErrors };
  }
  function diagnostics() {
    return { ...state, head: bones.head.quaternion.toArray(), hands: ['L', 'R'].map(s => bones[`hand${s}`].getWorldPosition(new THREE.Vector3()).toArray()) };
  }
  return { root, bones, skeletons, apply, grip, diagnostics };
}
