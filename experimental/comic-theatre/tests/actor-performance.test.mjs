import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createActor, sampleMouth } from '../src/actor.mjs';
import { sampleVisemes } from '../src/facial-performance.mjs';
import * as THREE from 'three';

const assetRoot = new URL('../assets/', import.meta.url);
test('held-book hands point inward for either page orientation', async()=>{
 const a=createActor(await load('actor-blue.glb'),'reader');
 for(const yaw of [0,Math.PI]){
  apply(a,0,null);
  const q=new THREE.Quaternion().setFromEuler(new THREE.Euler(-.35,yaw,0));
  const center=new THREE.Vector3(0,1.08,.38);
  const targets=(yaw===0?[1,-1]:[-1,1]).map(sign=>new THREE.Vector3(sign*.2,0,0).applyQuaternion(q).add(center));
  a.grip(targets,1,q);
  for(const side of ['L','R']){
   const hand=a.bones['hand'+side];
   const forward=new THREE.Vector3(0,1,0).applyQuaternion(hand.getWorldQuaternion(new THREE.Quaternion()));
   const inward=center.clone().sub(hand.getWorldPosition(new THREE.Vector3())).normalize();
   assert.ok(forward.dot(inward)>.95,`${side} fingers must face the book center at yaw ${yaw}`);
   const finger=a.bones['f21'+side].getWorldPosition(new THREE.Vector3()).sub(hand.getWorldPosition(new THREE.Vector3())).normalize();
   assert.ok(finger.dot(inward)>.9,`actual ${side} finger bones point inward at yaw ${yaw}`);
  }
 }
});
async function load(relative) {
  const bytes = await readFile(new URL(relative, assetRoot));
  return (await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '')).scene;
}
const line = { type: 'line', speaker: 'reader', start: 1, end: 4, emotion: 'pleased', face: { blink: 'off' },
  mouth: [{ t: 0, value: 0 }, { t: .5, value: 1 }, { t: 1, value: 0 }] };
const apply = (actor, time, event = line) => actor.apply({ time, line: event, seed: 41 });
function morphs(root) {
  const result = [];
  root.traverse(o => { if (o.morphTargetDictionary?.open !== undefined) result.push(o); });
  return result;
}

// Catches linear corner velocities, endpoint pops, and invalid sample propagation.
test('mouth sampling eases between measured samples and closes outside finite support', () => {
  assert.equal(sampleMouth([{ t: 0, value: 0 }, { t: 1, value: 1 }], .25), .15625);
  assert.equal(sampleMouth([{ t: .5, value: 1 }, { t: 1, value: 1 }], .5), 0);
  assert.equal(sampleMouth([{ t: .5, value: 1 }, { t: 1, value: 1 }], 1), 0);
  assert.equal(sampleMouth([{ t: 0, value: 0 }, { t: 1, value: 1 }], NaN), 0);
  assert.equal(sampleMouth([], .4), 0);
  const curve = [{ t: 0, value: 0 }, { t: .5, value: 1 }, { t: 1, value: 0 }];
  for (const t of [.5 - 1e-5, .5 + 1e-5]) assert.ok(Math.abs(sampleMouth(curve, t) - 1) / 1e-5 < .001, 'zero velocity at measured peak');
  for (const t of [-1, 0, .1, .5, 1, 2]) {
    assert.deepEqual(sampleVisemes(0, t, 4), { open: 0, round: 0, wide: 0 });
    const weights = Object.values(sampleVisemes(.7, t, 4));
    assert.ok(weights.every(v => v >= 0 && v <= 1));
    assert.ok(Math.abs(weights.reduce((a, b) => a + b, 0) - .7) < 1e-12);
  }
});

// Use only bundled snapshots; editable-source regression lives in the 3D library.
test('v10 oral cavity is driven, actors own bones and morph weights, seeking restores exactly', async () => {
  const source = await load('actor-blue.glb');
  const a = createActor(source, 'reader'), b = createActor(source, 'friend', 1);
  const sourceValues = morphs(source).map(m => [...m.morphTargetInfluences]);
  apply(a, 1.5);
  assert.equal(a.diagnostics().faceMode, 'oral-cavity');
  assert.ok(morphs(a.root).every(m => m.morphTargetInfluences[m.morphTargetDictionary.open] > .1));
  assert.notEqual(a.bones.head, b.bones.head);
  assert.deepEqual(morphs(source).map(m => m.morphTargetInfluences), sourceValues);
  assert.ok(morphs(b.root).every(m => m.morphTargetInfluences.every(v => v === 0)));
  assert.equal(a.root.getObjectByName('legacy-mouth'), undefined, 'no overlay over the real cavity');
  const first = a.diagnostics(), weights = morphs(a.root).map(m => [...m.morphTargetInfluences]);
  apply(a, 3.5); apply(a, 1.1); apply(a, 1.5);
  assert.deepEqual(a.diagnostics(), first);
  assert.deepEqual(morphs(a.root).map(m => m.morphTargetInfluences), weights);
  apply(a, 4.5, { ...line, type: 'hold', end: 5 });
  assert.ok(morphs(a.root).every(m => ['open', 'round', 'wide'].every(k => m.morphTargetInfluences[m.morphTargetDictionary[k]] === 0)));
});

test('all eight emotions blend from neutral and reaction duration releases continuously', async () => {
  const source = await load('actor-blue.glb');
  const a = createActor(source, 'reader');
  const results = new Set();
  for (const emotion of ['neutral', 'thoughtful', 'curious', 'skeptical', 'dry', 'pleased', 'concerned', 'exasperated']) {
    apply(a, 1.5, { ...line, emotion });
    const d = a.diagnostics();
    results.add(JSON.stringify([d.brows, d.eyeOpen, d.head]));
    apply(a, 1, { ...line, emotion });
    assert.deepEqual(a.diagnostics().brows, [0, 0], 'event boundary must return to common neutral');
  }
  assert.equal(results.size, 8);
  const b = createActor(source, 'friend', 1);
  const reacting = { ...line, reaction: { actor: 'friend', at: 'line_start', duration: .7, emotion: 'exasperated' } };
  b.apply({ time: 1.7 - 1e-5, line: reacting, listening: true });
  const before = b.diagnostics();
  b.apply({ time: 1.7 + 1e-5, line: reacting, listening: true });
  assert.ok(before.brows.every((v, i) => Math.abs(v - b.diagnostics().brows[i]) < .001));
});

test('sealed legacy actors keep compatible continuous fallback, without a visibility switch', async () => {
  const bytes = await readFile(new URL('../assets/actor.glb', import.meta.url));
  const source = (await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '')).scene;
  const a = createActor(source, 'reader', 0, { variant: 'olive' });
  const visible = () => { const v = []; a.root.traverse(o => { if (o.isMesh) v.push(o.visible); }); return v; };
  apply(a, 1); const closed = visible(); apply(a, 1.5);
  assert.deepEqual(visible(), closed);
  assert.equal(a.diagnostics().variant, 'olive');
  apply(a, 1.5, { ...line, emotion: 'skeptical' });
  assert.equal(a.diagnostics().eyeOpen, 1, 'legacy sealed eyes retain their original default geometry');
});

test('reaction gestures release continuously at reaction duration', async () => {
  const source = await load('actor-blue.glb');
  const actor = createActor(source, 'friend');
  const event = { ...line, reaction: { actor: 'friend', at: 'line_start', duration: .7, emotion: 'curious', gesture: 'head_tilt' } };
  actor.apply({ time: 1.7 - 1e-5, line: event, listening: true });
  const before = actor.diagnostics().head;
  actor.apply({ time: 1.7 + 1e-5, line: event, listening: true });
  assert.ok(before.every((v, i) => Math.abs(v - actor.diagnostics().head[i]) < .001));
});

test('optional clothing config owns each material without recoloring source or partner', async () => {
  const source = await load('actor-blue.glb');
  const a = createActor(source, 'reader', 0, { variant: 'rust' });
  const b = createActor(source, 'friend', 1, { variant: 'olive' });
  const shirt = root => { let material; root.traverse(o => { if (o.material?.name.includes('shirt')) material = o.material; }); return material; };
  assert.equal(shirt(a.root).color.getHex(), 0xae6149);
  assert.equal(shirt(b.root).color.getHex(), 0x78834e);
  assert.equal(shirt(source).color.getHex(), 0x527fa5);
  shirt(a.root).color.set(0);
  assert.equal(shirt(b.root).color.getHex(), 0x78834e);
  assert.equal(shirt(source).color.getHex(), 0x527fa5);
});

test('all six clothing IDs recolor a differently colored source without changing its eye geometry', async () => {
  const blue = await load('actor-blue.glb'), rust = await load('actor-rust.glb');
  const shirt = root => { let material; root.traverse(o => { if (o.material?.name.includes('shirt')) material = o.material; }); return material; };
  for (const [variant, expected] of [
    ['blue', 0x527fa5], ['rust', 0xae6149], ['olive', 0x78834e],
    ['blue-beady', 0x527fa5], ['rust-beady', 0xae6149], ['olive-beady', 0x78834e],
  ]) {
    const source = expected === 0xae6149 ? blue : rust;
    const original = shirt(source).color.getHex();
    const actor = createActor(source, 'reader', 0, { variant });
    assert.equal(shirt(actor.root).color.getHex(), expected, variant);
    assert.equal(shirt(source).color.getHex(), original, 'source material stays unchanged');
    const whites = [];
    actor.root.traverse(o => { if (o.material?.name === 'eye_white') whites.push(o); });
    assert.equal(whites.length, 2, 'config changes shirt color; eye style comes from the loaded GLB');
  }
});

test('six bundled variants share real visemes, three clothing colors, and authored eye styles', async () => {
  const colors = [];
  for (const variant of ['blue', 'rust', 'olive', 'blue-beady', 'rust-beady', 'olive-beady']) {
    const source = await load(`actor-${variant}.glb`);
    const a = createActor(source, 'reader', 0, { variant });
    apply(a, 1.5);
    assert.equal(a.diagnostics().faceMode, 'oral-cavity');
    assert.ok(morphs(a.root).length > 0);
    a.root.traverse(o => { if (o.material?.name.includes('shirt')) colors.push(o.material.color.getHex()); });
    if (variant.endsWith('-beady')) {
      const eyes = [], whites = [];
      a.root.traverse(o => {
        if (o.material?.name === 'eye_gloss') eyes.push(o);
        if (o.material?.name === 'eye_white') whites.push(o);
      });
      assert.equal(whites.length, 0);
      assert.equal(eyes.length, 2);
      assert.ok(eyes.every(o => o.material.color.r < .04 && o.material.color.g < .04 && o.material.color.b < .04));
      apply(a, 1.5, { ...line, face: { blink: 'off', eye_open: .25 } });
      assert.ok(eyes.every(o => o.morphTargetInfluences[o.morphTargetDictionary.blink] === .75));
      apply(a, 1.5, { ...line, face: { blink: 'off', eye_open: 1 } });
      assert.ok(eyes.every(o => o.morphTargetInfluences[o.morphTargetDictionary.blink] === 0));
    }
  }
  assert.equal(new Set(colors).size, 3);
});
