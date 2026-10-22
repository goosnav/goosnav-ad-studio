import * as THREE from 'three';
import { clamp, ease } from './actor.mjs';
import { bookSpread } from './book-pages.mjs';

const rails = new Set(['open', 'turn', 'hold', 'read', 'place', 'close', 'slam']);
const mix = THREE.MathUtils.lerp;

export function createBook(gltf, timeline, comics) {
  const root = new THREE.Group(); root.name = 'controlled-original-book';
  const model = gltf.scene;
  // Preserve canonical textures/UVs; room lighting must not bleach printed ink.
  const pageMaterials = new Map();
  model.traverse(o => {
    if (!o.isMesh) return;
    const readable = m => {
      if (!/^Comic page /.test(m.name)) return m;
      if (!pageMaterials.has(m)) {
        const page = new THREE.MeshBasicMaterial({ map: m.map, color: m.color, side: m.side, toneMapped: false });
        page.name = m.name; pageMaterials.set(m, page);
      }
      return pageMaterials.get(m);
    };
    o.material = Array.isArray(o.material) ? o.material.map(readable) : readable(o.material);
  });
  pageMaterials.forEach((_, original) => original.dispose());
  root.add(model);
  const binding = model.getObjectByName('Book2_Root');
  const cover = model.getObjectByName('Cover_Hinge');
  const leaves = [];
  model.traverse(o => { if (/^Page_\d+_Hinge$/.test(o.name)) leaves.push(o); });
  leaves.sort((a, b) => a.name.localeCompare(b.name));
  if (!binding || !cover || leaves.length !== 72) throw new Error('Book GLB must be the full openable Book Two v2 (72 page hinges)');
  binding.position.set(0, 0, 0);
  root.scale.setScalar(1.15);
  const coverRest = cover.position.clone();
  const leafRest = leaves.map(o => o.position.clone());
  // GLB converts Blender's -Y hinge rotation into +Z. Driving named hinges
  // directly avoids seeking the unrelated full-book demonstration clip.
  const axis = new THREE.Vector3(0, 0, 1);
  const pageFor = id => bookSpread(comics.get(id)?.pdfPage);
  const events = timeline.events.filter(e => e.type === 'action').sort((a, b) => a.start - b.start);
  const firstRail = events[0];
  const initialOpen = firstRail?.rail === 'open' ? 0 : 1;
  const firstComic = timeline.sources?.[0] || timeline.events.find(e => e.comic)?.comic;
  const initialPage = pageFor(firstComic) ?? 0;
  let state = {};
  function evaluate(time) {
    let openness = initialOpen, held = 0, page = initialPage, comic = firstComic,
      rail = null, progress = 0, stable = initialOpen ? 'table-open' : 'table-closed';
    for (const event of timeline.events) {
      if (event.start > time) break;
      if (event.type !== 'action') {
        if (event.comic && event.comic !== comic) { comic = event.comic; page = pageFor(comic) ?? page; }
        continue;
      }
      const name = typeof event.rail === 'string' ? event.rail : event.rail?.name;
      if (!rails.has(name)) throw new Error(`Unsupported book rail: ${name}`);
      const p = clamp((time - event.start) / (event.end - event.start || 1));
      const u = ease(name === 'slam' ? clamp(p / .65) : p);
      rail = name; progress = p;
      if (name === 'open') {
        // Choose the requested stack while closed, before revealing its pages.
        // Updating only the comic label leaves the old spread stuck on reopen.
        if (event.comic) { comic = event.comic; page = pageFor(comic) ?? page; }
        openness = mix(openness, 1, u); held = mix(held, 0, u);
      }
      if (name === 'close' || name === 'slam') { openness = mix(openness, 0, u); held = mix(held, 0, u); }
      if (name === 'hold') held = mix(held, 1, u);
      if (name === 'read') held = mix(held, event.bookState === 'held-open' ? 1 : held, u);
      if (name === 'place') held = mix(held, 0, u);
      if (name === 'turn') {
        const target = event.comic ? pageFor(event.comic) : Math.min(72, Math.floor(page) + 1);
        page = mix(page, target ?? page, u);
      }
      if (event.comic && p >= .5) comic = event.comic;
      if (p >= 1) stable = event.bookState || (held > .5 ? 'held-open' : openness > .5 ? 'table-open' : 'table-closed');
      if (p < 1) break;
    }
    return { openness, held, page, comic, rail, progress, state: stable };
  }
  function apply(time, reader) {
    state = evaluate(time);
    cover.quaternion.setFromAxisAngle(axis, Math.PI * state.openness);
    cover.position.copy(coverRest).lerp(new THREE.Vector3(-.001, -.005227, 0), state.openness);
    leaves.forEach((hinge, i) => {
      const turn = clamp(state.page - i) * state.openness;
      hinge.quaternion.setFromAxisAngle(axis, Math.PI * turn);
      const openedY = -.006477 + .0025 + .00025 + (i + .5) * .000099361111;
      hinge.position.copy(leafRest[i]).lerp(new THREE.Vector3(-.0015, openedY, 0), turn);
      hinge.traverse(o => {
        if (o.morphTargetInfluences) o.morphTargetInfluences.fill(Math.sin(turn * Math.PI) * .65);
      });
    });
    const table = new THREE.Vector3(-.48, .823, .32);
    const heldPoint = new THREE.Vector3(0, 1.08, .38).applyQuaternion(reader.root.quaternion).add(reader.root.position);
    root.position.copy(table).lerp(heldPoint, state.held);
    // Page top is local -Z: turn it away from the readers, not the audience.
    root.rotation.set(mix(0, -.35, state.held), Math.PI + mix(-.12, reader.root.rotation.y, state.held), 0);
    root.updateMatrixWorld(true);
    const targets = [-1, 1].map(sign => root.localToWorld(new THREE.Vector3(sign * .20, -.024, .025)));
    const manipulating = ['open', 'close', 'slam', 'turn'].includes(state.rail) && state.progress < 1;
    let contact = 0;
    if (manipulating && state.held === 0) {
      // One hand steadies the board, the other follows the *actual* hinge edge.
      const hinge = state.rail === 'turn' ? leaves[Math.min(71, Math.floor(state.page))] : cover;
      targets[1] = root.localToWorld(new THREE.Vector3(.05, -.012, .10));
      targets[0] = hinge.localToWorld(new THREE.Vector3(.16, .015, .10));
      contact = ease(state.progress / .18) * ease((1 - state.progress) / .18);
    }
    const weight = Math.max(state.held, contact);
    const grip = weight > 0 ? reader.grip(targets, weight, state.held > 0 ? root.getWorldQuaternion(new THREE.Quaternion()) : null) : { errors: [], palmAlignmentErrors: [] };
    state.gripErrors = grip.errors; state.palmAlignmentErrors = grip.palmAlignmentErrors;
    return state;
  }
  return { root, evaluate, apply, diagnostics: () => ({ ...state, model: 'catalog-glb', leaves: leaves.length,
    selectedPdfPage: comics.get(state.comic)?.pdfPage ?? null,
    position: root.position.toArray(), rotation: root.rotation.toArray().slice(0, 3),
    gripQuality: 'bounded wrist targets; finger contact not certified' }) };
}
