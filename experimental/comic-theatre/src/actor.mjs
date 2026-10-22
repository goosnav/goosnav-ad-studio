import * as THREE from 'three';
import { clone } from 'three/addons/utils/SkeletonUtils.js';
import { clamp, ease, clothing, envelope as faceEnvelope, sampleMouth, sampleExpression, sampleVisemes } from './facial-performance.mjs';
export { clamp, ease, sampleMouth } from './facial-performance.mjs';

// Provenance: Homunculus web/room.js (rest-relative bone poses), browser-room.js
// (sealed-face overlay coordinates and head.attach). No runtime checkout imports.
const number = (n, fallback = 0) => Number.isFinite(n) ? n : fallback;

export function createActor(source, id, index = 0, config = {}) {
  const root = new THREE.Group();
  root.name = `actor-${id}`;
  const body = clone(source);
  root.add(body);
  const bones = {}, rest = {}, skeletons = [], eyes = [], mouthMeshes = [], blinkMeshes = [];
  let authoredVariant;
  body.traverse(o => {
    if (o.userData?.theatre_variant) authoredVariant = o.userData.theatre_variant;
    if (o.isBone) {
      const key = o.name.replaceAll('.', '');
      bones[key] = o;
      rest[key] = { q: o.quaternion.clone(), p: o.position.clone(), s: o.scale.clone() };
    }
    if (o.isSkinnedMesh) { o.frustumCulled = false; skeletons.push(o.skeleton); }
    if (o.isMesh) {
      o.castShadow = true; o.receiveShadow = true;
      const ownMaterial = m => {
        const owned = m.clone();
        if (clothing[config?.variant] && m.name.includes('shirt')) owned.color.set(clothing[config.variant]);
        return owned;
      };
      o.material = Array.isArray(o.material) ? o.material.map(ownMaterial) : ownMaterial(o.material);
      if (o.morphTargetInfluences) o.morphTargetInfluences = o.morphTargetInfluences.map(() => 0);
      if (['open', 'round', 'wide'].every(n => o.morphTargetDictionary?.[n] !== undefined)) mouthMeshes.push(o);
      if (o.morphTargetDictionary?.blink !== undefined) blinkMeshes.push(o);
    }
    if (o.isMesh && o.morphTargetDictionary?.blink === undefined && ['eye_white', 'eye_black'].includes(o.material?.name)) {
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
  const variant = config?.variant ?? authoredVariant ?? null;
  const faceMode = mouthMeshes.length ? 'oral-cavity' : 'legacy-overlay';
  const dark = new THREE.MeshStandardMaterial({ color: 0x372722, roughness: .95 });
  const face = new THREE.Group();
  face.name = 'head-attached-expression';
  face.position.set(0, 1.525, .147);
  // Only old sealed exports need an overlay. New skins use the recessed cavity;
  // never layer a floating mouth over genuine lip/cavity geometry.
  let mouth, lip;
  if (!mouthMeshes.length) {
    mouth = new THREE.Mesh(new THREE.SphereGeometry(.038, 20, 12), dark);
    mouth.name = 'legacy-mouth';
    mouth.position.set(0, -.006, .012);
    face.add(mouth);
    lip = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
      new THREE.Vector3(-.10, -.018, 0), new THREE.Vector3(-.05, .002, .009),
      new THREE.Vector3(0, .009, .012), new THREE.Vector3(.05, .002, .009), new THREE.Vector3(.10, -.018, 0),
    ]), 20, .006, 6, false), dark);
    face.add(lip);
  }
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
    const expressionDuration = line ? Math.min(line.end - line.start,
      !ownsLine && reactionActive ? requested.duration ?? Infinity : Infinity) : 0;
    const envelope = line ? faceEnvelope(age, expressionDuration, .25, .3) : 0;
    const expressionWeight = line ? faceEnvelope(age, expressionDuration) : 0;
    const exp = sampleExpression(emotion, faceMode === 'legacy-overlay'
      ? { ...faceControl, eye_open: number(faceControl.eye_open, 1) } : faceControl, expressionWeight);
    const mouthValue = speaking ? sampleMouth(line.mouth, age) * faceEnvelope(age, line.end - line.start, .035, .045) : 0;
    const visemes = sampleVisemes(mouthValue, age, seed, index);
    const phase = time * 1.7 + index * 2.1 + (seed % 100) * .13;
    const gesture = (ownsLine ? line.gesture : reaction.gesture) || 'none';
    let tilt = exp.tilt;
    if (gesture === 'tilt' || gesture === 'head_tilt') tilt += .13 * envelope;
    const gazeTarget = reading || held > .5 || gesture === 'page_glance' ? 'book' : faceControl.gaze ?? reaction.gaze ?? (listening ? 'speaker' : 'partner');
    const yaw = gazeTarget === 'book' ? 0 : typeof gazeTarget === 'number' ? clamp(gazeTarget, -.65, .65)
      : gazeTarget === 'camera' ? -root.rotation.y : gaze;
    const down = gazeTarget === 'book' ? .55 : 0;
    const nod = gesture === 'nod' ? Math.sin(age * 5) * .13 * envelope : 0;
    pose('chest', Math.sin(phase) * .008, 0, 0);
    pose('head', down + nod - .025 + (speaking ? (.025 + Math.sin(age * 4) * .025) * envelope : 0), yaw, tilt);
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
    for (const mesh of mouthMeshes) {
      const weights = { ...visemes, smile: Math.max(0, exp.smile), frown: Math.max(0, -exp.smile) };
      for (const [name, value] of Object.entries(weights)) {
        const target = mesh.morphTargetDictionary[name];
        if (target !== undefined) mesh.morphTargetInfluences[target] = value;
      }
    }
    if (mouth) {
      mouth.scale.set(1.35 - mouthValue * .25, .025 + mouthValue * 1.05, .14);
      lip.scale.set(1, 1 - 1.8 * exp.smile, 1);
      // Continuous recession and thickness, no threshold visibility changes.
      lip.scale.multiplyScalar(1 - .9 * mouthValue);
    }
    const browValues = exp.brows;
    brows.forEach(({ anchor, q, p, sign }, i) => {
      anchor.position.copy(p);
      anchor.quaternion.copy(q).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0,
        sign * browValues[i])));
    });
    const blinkMode = faceControl.blink || 'auto';
    const blinkAge = blinkMode === 'once' ? age - .35 : ((time + index * 1.3 + (seed % 7) * .23) % 4.7) - 4.35;
    const blink = blinkMode === 'off' || blinkAge < 0 || blinkAge > .18 ? 0 : Math.sin(blinkAge / .18 * Math.PI);
    const eyeOpen = exp.eyeOpen * (1 - blink);
    for (const mesh of blinkMeshes) mesh.morphTargetInfluences[mesh.morphTargetDictionary.blink] = 1 - eyeOpen;
    for (const { mesh, positions, centerY } of eyes) {
      const attr = mesh.geometry.attributes.position;
      // Preserve the exact original Float32 vertices whenever the eye is open.
      attr.array.set(positions);
      if (eyeOpen < 1) for (let i = 0; i < attr.count; i++) attr.setY(i, centerY + (positions[i * 3 + 1] - centerY) * Math.max(.015, eyeOpen));
      attr.needsUpdate = true;
    }
    root.updateMatrixWorld(true);
    state = { id, variant, faceMode, visemes, expressionWeight, smile: exp.smile,
      mode: speaking ? 'talk' : listening ? 'listen' : 'idle', emotion, gesture, mouth: mouthValue,
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
        const normal = new THREE.Vector3(0, 1, 0).applyQuaternion(bookRotation);
        // Grip sides change when the book faces the readers. Fingers always
        // point toward the other grip, independently of the book's yaw.
        const forward = targets[1 - i].clone().sub(targets[i]).normalize();
        forward.addScaledVector(normal, -forward.dot(normal)).normalize();
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
