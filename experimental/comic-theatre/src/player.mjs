import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createActor } from './actor.mjs';
import { createBook } from './book.mjs';

const assetURL = (base, path) => `${base.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
const material = color => new THREE.MeshStandardMaterial({ color, roughness: .83 });

function buildSet(scene, treatment) {
  const wood = material(0x422b24), trim = material(0x967143), teal = material(0x193b3b);
  const cream = material(0xc8b38b), brass = material(0xa88b52), dark = material(0x1b2020);
  function box(size, position, mat) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), mat);
    mesh.position.set(...position); mesh.castShadow = true; mesh.receiveShadow = true;
    scene.add(mesh); return mesh;
  }
  box([12, .12, 12], [0, -.08, 0], wood);
  box([10, 4, .12], [0, 1.9, -1.48], teal);
  box([10, .12, .15], [0, .16, -1.36], trim);
  for (let x = -4; x <= 4; x += .65) box([.025, 1.05, .025], [x, .64, -1.39], trim);
  box([10, .045, .16], [0, 1.12, -1.38], trim);
  const rug = box([3.5, .018, 2.4], [0, -.008, .25], material(0x775047));
  for (const x of [-1.65, 1.65]) box([.035, .004, 2.2], [x, .004, .25], cream);
  const table = box([2.25, .085, .83], [-.05, .76, .58], wood);
  box([2.26, .018, .84], [-.05, .807, .58], material(0x78543b));
  for (const x of [-.97, .87]) for (const z of [.27, .9]) box([.055, .72, .055], [x, .36, z], brass);
  // Decorative spines are abstract set dressing, not replacement product artwork.
  const palette = [0x866a50, 0x485e59, 0x8c5046, 0xbaa27b, 0x343d4c];
  function shelf(x) {
    box([1.12, 2.5, .25], [x, 1.27, -1.28], wood);
    box([.96, 2.32, .02], [x, 1.3, -1.12], dark);
    for (let row = 0; row < 5; row++) {
      const y = .22 + row * .46;
      box([1.14, .045, .36], [x, y, -1.12], trim);
      for (let i = 0; i < 9; i++) {
        const h = .24 + ((i * 7 + row * 3) % 5) * .027;
        const spine = box([.075, h, .16], [x - .42 + i * .103, y + h / 2 + .025, -1.04], material(palette[(i + row) % palette.length]));
        spine.rotation.z = i === 7 ? -.09 : 0;
        box([.052, .011, .006], [spine.position.x, y + h - .035, -.956], brass);
      }
    }
  }
  shelf(-1.65);
  if (treatment !== 'fireside') shelf(1.65);
  if (treatment === 'fireside') {
    box([1.55, 1.37, .32], [1.7, .69, -1.22], material(0x6a594b));
    box([1.15, .9, .035], [1.7, .55, -1.04], dark);
    box([1.73, .12, .5], [1.7, 1.41, -1.14], cream);
    box([1.65, .10, .64], [1.7, .06, -1.02], material(0x554d48));
    for (let i = 0; i < 5; i++) {
      const ember = new THREE.Mesh(new THREE.ConeGeometry(.075, .22 + i % 2 * .12, 7),
        new THREE.MeshStandardMaterial({ color: 0xc67728, emissive: 0xf16918, emissiveIntensity: 1.5, roughness: 1 }));
      ember.position.set(1.7 + (i - 2) * .16, .25, -.99); scene.add(ember);
    }
    const fire = new THREE.PointLight(0xffa35b, 2.5, 4, 2); fire.position.set(1.7, .65, -.65); scene.add(fire);
  } else {
    box([1.5, 1.2, .055], [0, 2.0, -1.36], brass);
    box([1.39, 1.09, .06], [0, 2.0, -1.31], dark);
    box([1.29, .99, .065], [0, 2.0, -1.26], material(0x496c70));
    for (const x of [-.65, 0, .65]) box([.035, 1.05, .09], [x, 2, -1.22], brass);
    box([1.34, .035, .09], [0, 2, -1.21], brass);
  }
  // Warm practical pool on the table without blocking either face.
  box([.035, .55, .035], [0, 1.1, .20], brass);
  const shade = new THREE.Mesh(new THREE.ConeGeometry(.19, .18, 32, 1, true), material(0xc2aa72));
  shade.position.set(0, 1.39, .20); scene.add(shade);
  const lamp = new THREE.PointLight(0xffd79e, .8, 2.5, 2); lamp.position.set(0, 1.28, .20); scene.add(lamp);
  return { table, rug };
}

function disposeObjects(roots, extraTextures = []) {
  const geometries = new Set(), materials = new Set(), textures = new Set(extraTextures), skeletons = new Set();
  for (const root of roots) root?.traverse(o => {
    if (o.geometry) geometries.add(o.geometry);
    if (o.skeleton) skeletons.add(o.skeleton);
    for (const mat of (Array.isArray(o.material) ? o.material : o.material ? [o.material] : [])) {
      materials.add(mat);
      for (const value of Object.values(mat)) if (value?.isTexture) textures.add(value);
    }
  });
  geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose());
  textures.forEach(t => { t.dispose(); t.source?.data?.close?.(); });
  skeletons.forEach(s => s.dispose());
}

function validate(timeline, catalog) {
  if (!timeline || !Array.isArray(timeline.events) || !Number.isInteger(timeline.fps) || timeline.fps <= 0 ||
      !Number.isInteger(timeline.frames) || timeline.frames < 1) throw new Error('Timeline requires events, positive integer fps and frames');
  for (const key of ['width', 'height']) if (!Number.isInteger(timeline[key]) || timeline[key] < 1 || timeline[key] > 4096) throw new Error(`Invalid timeline ${key}`);
  if (!['library', 'fireside'].includes(timeline.scene)) throw new Error('Unknown scene treatment');
  if (!catalog?.assets?.actor?.path || !catalog?.assets?.book?.path) throw new Error('Catalog must supply actor and book GLBs');
  if (!Array.isArray(timeline.cast) || !timeline.cast.includes('reader') || timeline.cast.some(id => !['reader', 'friend'].includes(id)) || new Set(timeline.cast).size !== timeline.cast.length) throw new Error('Cast must contain reader and optionally friend');
  const comics = new Map(catalog.comics.map(c => [c.id, c]));
  const selected = new Set(timeline.sources || []);
  for (const id of [...selected, ...timeline.events.map(e => e.comic).filter(Boolean)]) {
    const comic = comics.get(id);
    if (!comic?.verified || !comic.path || !Number.isInteger(comic.pdfPage) || comic.pdfPage < 3 || comic.pdfPage > 146) throw new Error(`Unknown, unverified or unmappable source: ${id}`);
    if (!selected.has(id)) throw new Error(`Source is not selected in timeline: ${id}`);
  }
  for (const e of timeline.events) {
    if (!['line', 'source', 'action', 'hold'].includes(e.type) || !Number.isFinite(e.start) || !Number.isFinite(e.end) || e.start < 0 || e.end <= e.start) throw new Error('Invalid timeline event');
    if (e.speaker && !timeline.cast.includes(e.speaker)) throw new Error(`Unknown speaker: ${e.speaker}`);
    if (e.type === 'source' && !e.comic) throw new Error('Source events need a catalog comic');
    let prev = -Infinity;
    for (const sample of e.mouth || []) {
      if (!Number.isFinite(sample.t) || sample.t < 0 || sample.t < prev || !Number.isFinite(sample.value)) throw new Error('Mouth samples must be finite and ordered in line-relative seconds');
      prev = sample.t;
    }
  }
  return comics;
}

export async function createPlayer(canvas, { timeline: input, catalog, assetBase = '' }) {
  // Own a stable snapshot: host edits must create a new player, never alter a capture.
  const timeline = structuredClone(input);
  timeline.events?.sort((a, b) => a.start - b.start);
  const comics = validate(timeline, catalog);
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x192929);
  const insertScene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, timeline.width / timeline.height, .04, 30);
  const insertCamera = new THREE.OrthographicCamera(-camera.aspect, camera.aspect, 1, -1, .1, 5);
  insertCamera.position.z = 2;
  const textures = new Map(), loadedRoots = [];
  let renderer, actors, book, sourcePlane, disposed = false, frame = null, active = null, source = null, shot = 'two-shot';
  try {
    // Load sequentially so every fulfilled allocation is owned even if a later load fails.
    const loader = new GLTFLoader();
    const actorGLTF = await loader.loadAsync(assetURL(assetBase, catalog.assets.actor.path));
    loadedRoots.push(actorGLTF.scene);
    const bookGLTF = await loader.loadAsync(assetURL(assetBase, catalog.assets.book.path));
    loadedRoots.push(bookGLTF.scene);
    const textureLoader = new THREE.TextureLoader();
    for (const id of timeline.sources) {
      const texture = await textureLoader.loadAsync(assetURL(assetBase, comics.get(id).path));
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.generateMipmaps = false; texture.minFilter = THREE.LinearFilter;
      textures.set(id, texture);
    }
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1); renderer.setSize(timeline.width, timeline.height, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.15;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    scene.add(new THREE.HemisphereLight(0xf7ead4, 0x395150, 2.1));
    const key = new THREE.DirectionalLight(0xffdfb1, 3.2);
    key.position.set(-2.5, 4, 3); key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024); key.shadow.camera.left = -3; key.shadow.camera.right = 3;
    key.shadow.camera.top = 3; key.shadow.camera.bottom = -3; key.shadow.normalBias = .018;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xc7e4ef, 1.6); fill.position.set(2, 2, 2); scene.add(fill);
    const rim = new THREE.DirectionalLight(0xf9bd77, 2); rim.position.set(0, 3, -2); scene.add(rim);
    buildSet(scene, timeline.scene);
    actors = timeline.cast.map((id, i) => {
      const actor = createActor(actorGLTF.scene, id, i);
      actor.root.position.set(id === 'reader' ? -.64 : .64, 0, -.02);
      actor.root.rotation.y = id === 'reader' ? .30 : -.30;
      scene.add(actor.root); return actor;
    });
    book = createBook(bookGLTF, timeline, comics); scene.add(book.root);
    sourcePlane = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial({ toneMapped: false }));
    insertScene.background = new THREE.Color(0xeee9df); insertScene.add(sourcePlane);
  } catch (error) {
    disposeObjects([scene, insertScene, ...loadedRoots], [...textures.values()]); renderer?.dispose(); throw error;
  }

  function renderAt(frameIndex) {
    if (disposed) throw new Error('Player is disposed');
    if (!Number.isInteger(frameIndex) || frameIndex < 0 || frameIndex >= timeline.frames) throw new RangeError(`frameIndex must be an integer from 0 to ${timeline.frames - 1}`);
    frame = frameIndex;
    const time = frame / timeline.fps;
    const current = timeline.events.filter(e => e.start <= time && time < e.end);
    active = current.find(e => e.type === 'line' || e.type === 'hold') || null;
    const sourceEvent = current.find(e => e.type === 'source') || (active?.shot === 'source' ? active : null);
    source = sourceEvent ? comics.get(sourceEvent.comic) : null;
    const reader = actors.find(a => a.root.name === 'actor-reader');
    const bookState = book.evaluate(time);
    actors.forEach((actor, i) => actor.apply({ time, line: active,
      listening: !!active && active.speaker !== timeline.cast[i],
      gaze: actors.length > 1 ? (i === 0 ? .32 : -.32) : 0,
      held: timeline.cast[i] === 'reader' ? bookState.held : 0,
      reading: timeline.cast[i] === 'reader' && bookState.rail === 'read' && bookState.progress < 1,
      seed: timeline.seed || 0 }));
    book.apply(time, reader);
    scene.updateMatrixWorld(true);
    shot = source ? 'source' : active?.shot || 'two-shot';
    // Holds after speech favor the reacting listener, retaining a three-quarter angle.
    const reacting = active?.type === 'hold' && active.reaction?.at === 'line_end' && time - active.start < active.reaction.duration;
    const focusId = reacting ? active.reaction.actor : active?.speaker;
    if (shot === 'speaker' && focusId) {
      // Camera sits outside the inward-facing cast: an inside camera nearly
      // aligns with the nose and hides the model's authored side-mounted eyes.
      const x = focusId === 'reader' ? -.64 : .64, side = focusId === 'reader' ? -1 : 1;
      camera.fov = 32;
      const distance = camera.aspect < 1 ? 2.45 : 1.9;
      camera.position.set(x + side * .65, 1.69, distance);
      camera.lookAt(x, 1.43, .03);
    } else {
      camera.fov = 38;
      const distance = Math.max(3.7, 1.5 / (Math.tan(THREE.MathUtils.degToRad(19)) * camera.aspect));
      camera.position.set(.10, 1.95, distance);
      camera.lookAt(0, 1.05, .03);
    }
    camera.updateProjectionMatrix();
    if (source) {
      const texture = textures.get(source.id);
      sourcePlane.material.map = texture; sourcePlane.material.needsUpdate = true;
      const ratio = texture.image.width / texture.image.height;
      const h = Math.min(.95, camera.aspect * .95 / ratio);
      sourcePlane.scale.set(h * ratio, h, 1);
      renderer.render(insertScene, insertCamera);
    } else renderer.render(scene, camera);
  }

  function diagnostics() {
    return structuredClone({ frame, time: frame === null ? null : frame / timeline.fps,
      scene: timeline.scene, shot, activeEvent: active?.id || null,
      source: source ? { id: source.id, path: source.path, sha256: source.sha256, pdfPage: source.pdfPage, fit: 'contain' } : null,
      independentSkeletons: actors.every((a, i) => actors.slice(i + 1).every(b =>
        a.skeletons.every(s => b.skeletons.every(t => s !== t && s.bones.every(bone => !t.bones.includes(bone)))))),
      actors: actors.map(a => a.diagnostics()), book: book.diagnostics(),
      camera: { position: camera.position.toArray(), quaternion: camera.quaternion.toArray(), fov: camera.fov },
      disposed, warnings: ['Grip measures wrist targets only; natural finger contact has not been certified.',
        'Procedural library/fireside set; optional environment GLB is not used.',
        'Page changes outside explicit turn rails are deliberate source cuts.'] });
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    disposeObjects([scene, insertScene, ...loadedRoots], [...textures.values()]);
    renderer.renderLists.dispose(); renderer.dispose();
  }
  renderAt(0);
  return { renderAt, diagnostics, dispose };
}
