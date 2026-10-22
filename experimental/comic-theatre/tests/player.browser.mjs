import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, extname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = fileURLToPath(new URL('../', import.meta.url));

test('authored eyes stay unchanged at default, centered when narrowed, and visible in speaker/reading views', { timeout: 60000 }, async t => {
  const catalog = JSON.parse(await readFile(resolve(root, 'assets/catalog.json'), 'utf8'));
  // This regression compares the original sealed-face geometry. Modern variant
  // morphs are exercised separately in actor-performance and cinematography.
  delete catalog.variants;
  const server = createServer(async (req, res) => {
    try {
      if (req.url === '/') {
        res.setHeader('Content-Type', 'text/html');
        return res.end('<style>body{margin:0}</style><script type="importmap">{"imports":{"three":"/node_modules/three/build/three.module.js","three/addons/":"/node_modules/three/examples/jsm/"}}</script><canvas></canvas>');
      }
      const path = resolve(root, `.${req.url}`);
      if (!path.startsWith(root)) throw Error('outside test root');
      res.setHeader('Content-Type', /\.m?js$/.test(path) ? 'text/javascript' : extname(path) === '.glb' ? 'model/gltf-binary' : 'image/jpeg');
      res.end(await readFile(path));
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  t.after(() => new Promise(r => { server.closeAllConnections(); server.close(r); }));
  const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 432, height: 540 } });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  const { compositionImages, ...result } = await page.evaluate(async catalog => {
    const T = await import('three');
    const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
    const { createActor } = await import('/src/actor.mjs');
    const { createPlayer } = await import('/src/player.mjs');
    const { createBook } = await import('/src/book.mjs');
    const bookTimeline = { sources: ['book2-020', 'book2-036'], events: [
      { type: 'action', rail: 'open', comic: 'book2-036', start: 0, end: 1, bookState: 'table-open' },
      { type: 'line', comic: 'book2-036', start: 1, end: 2 },
      { type: 'line', comic: 'book2-020', start: 2, end: 3 },
      { type: 'action', rail: 'close', start: 3, end: 4, bookState: 'table-closed' },
      { type: 'action', rail: 'open', comic: 'book2-036', start: 4, end: 5, bookState: 'table-open' },
      { type: 'line', comic: 'book2-036', start: 5, end: 6 },
      { type: 'action', rail: 'close', start: 6, end: 7, bookState: 'table-closed' },
      { type: 'action', rail: 'open', comic: 'book2-020', start: 7, end: 8, bookState: 'table-open' },
      { type: 'line', comic: 'book2-020', start: 8, end: 9 },
    ] };
    const book = createBook(await new GLTFLoader().loadAsync(`/${catalog.assets.book.path}`), bookTimeline, new Map(catalog.comics.map(c => [c.id, c])));
    const bookOpenCases = [0, .5, 1.5, 2.5, 4.5, 5.5, 7.5, 8.5, 1.5].map(time => {
      const state = book.evaluate(time); return { comic: state.comic, page: state.page };
    });
    const source = (await new GLTFLoader().loadAsync(`/${catalog.assets.actor.path}`)).scene;
    const originals = new Map();
    source.traverse(o => { if (o.material?.name?.startsWith('eye_')) originals.set(o.material.name, o.geometry.attributes.position.array.slice()); });
    const actor = createActor(source, 'friend', 1);
    actor.root.position.set(.64, 0, -.02); actor.root.rotation.y = -.3;
    const line = { id: 'eyes', type: 'line', speaker: 'friend', start: 6.775, end: 9.575,
      emotion: 'skeptical', gesture: 'head_tilt', face: {}, shot: 'speaker', comic: catalog.comics[0].id, mouth: [] };
    const args = { time: 7, line, gaze: -.32, seed: 17 };
    actor.apply(args);
    const eyes = [];
    actor.root.traverse(o => { if (o.material?.name?.startsWith('eye_')) eyes.push(o); });
    const delta = () => Math.max(...eyes.flatMap(o => Array.from(o.geometry.attributes.position.array, (v, i) => Math.abs(v - originals.get(o.material.name)[i]))));
    const defaultDelta = delta();
    const midpoint = a => { const ys = Array.from(a).filter((_, i) => i % 3 === 1); return (Math.min(...ys) + Math.max(...ys)) / 2; };
    actor.apply({ ...args, line: { ...line, face: { eye_open: .5, blink: 'off' } } });
    const centerDrift = Math.max(...eyes.map(o => Math.abs(midpoint(o.geometry.attributes.position.array) - midpoint(originals.get(o.material.name)))));
    actor.apply(args);
    const restoredDelta = delta();
    const timeline = { version: 1, fps: 12, width: 432, height: 540, frames: 120, duration: 10, seed: 17,
      scene: 'library', template: 'book-duet', cast: ['reader', 'friend'], sources: [line.comic],
      events: [{ ...line, id: 'reader-closeup', speaker: 'reader', start: 0, end: 5 }, line] };
    // Capture the actual render scene in the test only; production API stays small.
    const originalAdd = T.Scene.prototype.add;
    let productionScene;
    T.Scene.prototype.add = function(...objects) {
      if (objects.some(o => o.name === 'actor-reader')) productionScene = this;
      return originalAdd.apply(this, objects);
    };
    let player;
    try { player = await createPlayer(document.querySelector('canvas'), { timeline, catalog }); }
    finally { T.Scene.prototype.add = originalAdd; }
    const productionRenderer = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    productionRenderer.setSize(432, 540);
    const compositionImages = {}, lampOverlapPixels = {};
    for (const [id, frame] of [['reader', 24], ['friend', 84]]) {
      player.renderAt(frame);
      compositionImages[id] = document.querySelector('canvas').toDataURL();
      const cs = player.diagnostics().camera;
      const c = new T.PerspectiveCamera(cs.fov, .8, .04, 30);
      c.position.fromArray(cs.position); c.quaternion.fromArray(cs.quaternion); c.updateMatrixWorld(true);
      const bounds = new T.Box2();
      productionScene.getObjectByName(`actor-${id}`).traverse(o => {
        if (!o.isMesh) return;
        for (let i = 0; i < o.geometry.attributes.position.count; i++) {
          const v = o.getVertexPosition(i, new T.Vector3()).applyMatrix4(o.matrixWorld);
          if (v.y < 1.15 || v.y > 1.76) continue;
          v.project(c); bounds.expandByPoint(new T.Vector2((v.x + 1) * 216, (v.y + 1) * 270));
        }
      });
      const saved = [], mask = new T.MeshBasicMaterial({ color: 0xff00ff, toneMapped: false }), black = new T.MeshBasicMaterial({ color: 0, toneMapped: false });
      productionScene.traverse(o => {
        if (!o.isMesh) return;
        saved.push([o, o.material]);
        o.material = o.geometry.type === 'ConeGeometry' && o.geometry.parameters.radius === .19 ? mask : black;
      });
      productionRenderer.render(productionScene, c);
      const gl = productionRenderer.getContext(), pixels = new Uint8Array(432 * 540 * 4);
      gl.readPixels(0, 0, 432, 540, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      let overlap = 0;
      for (let y = Math.max(0, Math.ceil(bounds.min.y)); y < Math.min(540, bounds.max.y); y++) {
        for (let x = Math.max(0, Math.ceil(bounds.min.x)); x < Math.min(432, bounds.max.x); x++) {
          const i = (y * 432 + x) * 4;
          if (pixels[i] > 200 && pixels[i + 1] < 40 && pixels[i + 2] > 200) overlap++;
        }
      }
      lampOverlapPixels[id] = overlap;
      for (const [o, material] of saved) o.material = material;
      mask.dispose(); black.dispose();
    }
    player.renderAt(84);
    const cameraState = player.diagnostics().camera;
    // Review the legacy actor at the production blocking, not the old fixture's
    // pre-cinematography position (which points this camera at an empty seat).
    const stagedActor = productionScene.getObjectByName('actor-friend');
    actor.root.position.copy(stagedActor.position);
    actor.root.quaternion.copy(stagedActor.quaternion);
    actor.apply(args);
    productionRenderer.dispose();
    player.dispose();
    const scene = new T.Scene(); scene.background = new T.Color(0x193b3b); scene.add(actor.root);
    scene.add(new T.HemisphereLight(0xf7ead4, 0x395150, 2.1));
    const key = new T.DirectionalLight(0xffdfb1, 3.2); key.position.set(-2.5, 4, 3); scene.add(key);
    const camera = new T.PerspectiveCamera(cameraState.fov, .8, .04, 30);
    camera.position.fromArray(cameraState.position); camera.quaternion.fromArray(cameraState.quaternion);
    const renderer = new T.WebGLRenderer({ canvas: document.querySelector('canvas'), antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(432, 540); renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.15;
    const materials = [];
    actor.root.traverse(o => { if (o.isMesh) { materials.push([o, o.material]); o.material = new T.MeshBasicMaterial({ color: o.material.name === 'eye_white' ? 0xff00ff : 0, toneMapped: false }); } });
    renderer.render(scene, camera);
    const gl = renderer.getContext(), pixels = new Uint8Array(432 * 540 * 4);
    gl.readPixels(0, 0, 432, 540, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let visibleEyePixels = 0;
    for (let i = 0; i < pixels.length; i += 4) if (pixels[i] > 200 && pixels[i + 1] < 40 && pixels[i + 2] > 200) visibleEyePixels++;
    for (const [o, m] of materials) { o.material.dispose(); o.material = m; }
    renderer.render(scene, camera);
    const withProcedure = renderer.domElement.toDataURL();
    for (const eye of eyes) { eye.geometry.attributes.position.array.set(originals.get(eye.material.name)); eye.geometry.attributes.position.needsUpdate = true; }
    renderer.render(scene, camera);
    const offPixelsIdentical = withProcedure === renderer.domElement.toDataURL();
    actor.apply({ ...args, reading: true });
    const readingForward = new T.Vector3(0, 0, 1).applyQuaternion(actor.bones.head.getWorldQuaternion(new T.Quaternion())).applyQuaternion(actor.root.quaternion.clone().invert()).toArray();
    actor.apply(args); renderer.render(scene, camera);
    window.eyeReview = { actor, args, renderer, scene, camera };
    return { defaultDelta, restoredDelta, centerDrift, visibleEyePixels, offPixelsIdentical, readingForward, lampOverlapPixels, compositionImages, bookOpenCases };
  }, catalog);
  for (const [id, data] of Object.entries(compositionImages)) await writeFile(join(tmpdir(), `comic-theatre-lamp-fixed-${id}.png`), Buffer.from(data.split(',')[1], 'base64'));
  t.diagnostic(`Eye geometry/visibility comparison: ${JSON.stringify(result)}`);
  await page.screenshot({ path: join(tmpdir(), 'comic-theatre-eyes-fixed.png') });
  await page.evaluate(() => { const f = window.eyeReview; f.actor.apply({ ...f.args, reading: true }); f.renderer.render(f.scene, f.camera); });
  await page.screenshot({ path: join(tmpdir(), 'comic-theatre-reading-fixed.png') });
  assert.equal(result.defaultDelta, 0, 'default open eyes preserve every authored position exactly');
  assert.equal(result.restoredDelta, 0, 'a seek from narrowed eyes restores original positions exactly');
  assert.equal(result.offPixelsIdentical, true, 'default eye procedure and untouched GLB positions render identically');
  assert.ok(result.centerDrift < 2e-6, `partial closure must not move pupils toward a hard-coded center: ${result.centerDrift}`);
  assert.ok(result.visibleEyePixels >= 350, `speaker framing must expose the authored side eye: ${result.visibleEyePixels} pixels`);
  assert.ok(result.readingForward[1] < -.4 && Math.abs(result.readingForward[0]) < .08, `reading faces down toward the book, not toward the partner: ${result.readingForward}`);
  assert.deepEqual(result.lampOverlapPixels, { reader: 0, friend: 0 }, 'lamp shade must not cover either face/upper-chest screen region');
  assert.deepEqual(result.bookOpenCases, [19, 19, 19, 11, 19, 19, 11, 11, 19].map(page => ({ comic: page === 19 ? 'book2-036' : 'book2-020', page })), 'open and reopen select the named physical spread, independently of source order and seek history');
});
test('real GLBs render seekably, preserve sources, isolate rigs, and obey book rails', { timeout: 120000 }, async t => {
  const catalog = JSON.parse(await readFile(resolve(root, 'assets/catalog.json'), 'utf8'));
  const comic = catalog.comics.find(c => c.verified);
  assert.ok(comic, 'a reviewed source fixture is available');
  const timeline = { version: 1, fps: 24, width: 960, height: 540, frames: 336, duration: 14,
    seed: 21, scene: 'library', template: 'book-duet', cast: ['reader', 'friend'], sources: [comic.id], events: [
      { id: 'source', type: 'source', start: 0, end: 2, comic: comic.id },
      { id: 'talk', type: 'line', start: 2, end: 4, speaker: 'reader', comic: comic.id,
        shot: 'speaker', emotion: 'curious', gesture: 'explain', face: { brow_left: .4, brow_right: .2, eye_open: .8, blink: 'off' },
        reaction: { actor: 'friend', at: 'line_start', duration: 2, emotion: 'skeptical', gesture: 'head_tilt' }, mouth: [{ t: 0, value: 0 }, { t: .5, value: 1 }, { t: 1, value: 0 }] },
      { id: 'hold', type: 'action', rail: 'hold', start: 4, end: 5, bookState: 'held-open' },
      { id: 'read', type: 'action', rail: 'read', start: 5, end: 6, bookState: 'held-open' },
      { id: 'turn', type: 'action', rail: 'turn', start: 6, end: 7, bookState: 'held-open' },
      { id: 'place', type: 'action', rail: 'place', start: 7, end: 8, bookState: 'table-open' },
      { id: 'close', type: 'action', rail: 'close', start: 8, end: 9, bookState: 'table-closed' },
      { id: 'open', type: 'action', rail: 'open', start: 9, end: 10, bookState: 'table-open' },
      { id: 'slam', type: 'action', rail: 'slam', start: 10, end: 11, bookState: 'table-closed' },
      { id: 'reply', type: 'line', start: 11, end: 13, speaker: 'friend', shot: 'speaker',
        gesture: 'shrug', reaction: { actor: 'reader', at: 'line_end', duration: 1, emotion: 'surprised', gesture: 'nod' },
        mouth: [{ t: 0, value: 0 }, { t: .5, value: .8 }, { t: 1, value: 0 }] },
      { id: 'reply-hold', type: 'hold', start: 13, end: 14, speaker: 'friend', mouth: [],
        reaction: { actor: 'reader', at: 'line_end', duration: 1, emotion: 'surprised', gesture: 'nod' } },
    ] };
  const server = createServer(async (req, res) => {
    try {
      const pathname = new URL(req.url, 'http://localhost').pathname;
      if (pathname === '/') {
        res.setHeader('Content-Type', 'text/html');
        return res.end('<style>body{margin:0;background:#171b1d}canvas{display:block}</style><script type="importmap">{"imports":{"three":"/node_modules/three/build/three.module.js","three/addons/":"/node_modules/three/examples/jsm/"}}</script><canvas></canvas>');
      }
      const path = resolve(root, `.${pathname}`);
      if (!path.startsWith(root)) throw new Error('outside fixture root');
      const data = await readFile(path);
      res.setHeader('Content-Type', ({ '.mjs': 'text/javascript', '.js': 'text/javascript', '.glb': 'model/gltf-binary', '.jpg': 'image/jpeg', '.png': 'image/png' })[extname(path)] || 'application/octet-stream');
      res.end(data);
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  t.after(() => new Promise(r => { server.closeAllConnections(); server.close(r); }));
  const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  t.diagnostic(`Pinned Chromium ${browser.version()}; ${chromium.executablePath()}`);
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  const loaded = await page.evaluate(async ({ timeline, catalog }) => {
    try {
      const { createPlayer } = await import('/src/player.mjs');
      window.player = await createPlayer(document.querySelector('canvas'), { timeline, catalog, assetBase: '' });
      return { ok: true };
    } catch (e) { return { ok: false, error: e.message }; }
  }, { timeline, catalog });
  assert.equal(loaded.ok, true, `createPlayer must load real assets: ${loaded.error}`);
  const render = frame => page.evaluate(f => { window.player.renderAt(f); return window.player.diagnostics(); }, frame);
  const source = await render(12);
  assert.equal(source.source.id, comic.id);
  assert.equal(source.source.fit, 'contain');
  assert.equal(source.book.model, 'catalog-glb');
  assert.equal(source.independentSkeletons, true);
  assert.ok(source.actors.every(a => a.faceAttachedToHead));
  await page.screenshot({ path: join(tmpdir(), 'comic-theatre-source.png') });
  const talk = await render(60); // exactly 0.5 seconds into the reader's measured curve
  assert.equal(talk.actors.find(a => a.id === 'reader').mouth, 1);
  assert.equal(talk.actors.find(a => a.id === 'friend').mouth, 0);
  assert.equal(talk.actors.find(a => a.id === 'friend').emotion, 'skeptical');
  assert.deepEqual(talk.actors.find(a => a.id === 'reader').brows, [.4, .2]);
  assert.equal(talk.actors.find(a => a.id === 'reader').eyeOpen, .8);
  assert.equal(talk.shot, 'speaker');
  const pixels = await page.evaluate(() => document.querySelector('canvas').toDataURL());
  await page.screenshot({ path: join(tmpdir(), 'comic-theatre-closeup.png') });
  await render(280);
  assert.deepEqual(await render(60), talk, 'backward seeking restores all reported pose and page state');
  assert.equal(await page.evaluate(() => document.querySelector('canvas').toDataURL()), pixels, 'same frame has byte-identical pixels after arbitrary seeking');
  assert.equal((await render(54)).actors.find(a => a.id === 'reader').mouth, .5, 'line-relative samples interpolate');
  assert.equal((await render(95)).actors.find(a => a.id === 'reader').mouth, 0, 'no procedural talking beyond measured curve');
  const held = await render(126);
  assert.equal(held.book.state, 'held-open');
  assert.ok(held.book.gripErrors.every(e => Number.isFinite(e) && e < .065), `wrist grip target errors are bounded: ${held.book.gripErrors}`);
  assert.ok(held.book.palmAlignmentErrors.every(e => e < .01), 'held palms face the book rather than dangling at rest');
  await page.screenshot({ path: join(tmpdir(), 'comic-theatre-held.png') });
  assert.equal((await render(156)).book.page, Math.floor((comic.pdfPage - 2) / 2) + .5, 'a turn moves a leaf through the middle of its hinge travel');
  assert.equal((await render(168)).book.page, Math.floor((comic.pdfPage - 2) / 2) + 1, 'completed turn persists');
  await render(264);
  assert.deepEqual(await render(126), held, 'held pose is independent of prior slam');
  assert.equal((await render(198)).book.state, 'table-open'); // close is still in progress
  const closed = await render(216);
  assert.equal(closed.book.openness, 0);
  const opening = await render(228);
  assert.equal(opening.book.gripErrors.length, 2, 'opening reaches toward the actual cover and supporting board');
  assert.ok(opening.book.gripErrors.every(e => Number.isFinite(e) && e < .12), `opening target reach errors: ${opening.book.gripErrors}`);
  t.diagnostic(`Held wrist errors (m): ${held.book.gripErrors.join(', ')}; palm normal error (1-dot): ${held.book.palmAlignmentErrors.join(', ')}; opening wrist errors (m): ${opening.book.gripErrors.join(', ')}`);
  const opened = await render(240);
  assert.equal(opened.book.openness, 1);
  assert.equal((await render(264)).book.openness, 0);
  assert.equal((await render(276)).actors.find(a => a.id === 'friend').mouth, .8);
  assert.equal((await render(276)).actors.find(a => a.id === 'reader').emotion, 'neutral', 'line_end reaction waits for speech to finish');
  const reaction = await render(324);
  assert.equal(reaction.actors.find(a => a.id === 'reader').emotion, 'surprised');
  assert.ok(reaction.actors.every(a => a.mouth === 0), 'reaction hold cannot synthesize mouth motion');
  assert.equal((await render(0)).book.openness, 1, 'initial open state survives seeking backward past a slam');
  const invalid = await page.evaluate(() => [-1, .5, NaN, Infinity, 336].map(f => {
    try { window.player.renderAt(f); return false; } catch { return true; }
  }));
  assert.ok(invalid.every(Boolean), 'frame indices must be integers in the capture range');
  await page.evaluate(() => window.player.dispose());
  const fireside = await page.evaluate(async ({ timeline, catalog }) => {
    const { createPlayer } = await import('/src/player.mjs');
    window.player = await createPlayer(document.querySelector('canvas'), { timeline: { ...timeline, scene: 'fireside' }, catalog });
    window.player.renderAt(180);
    return window.player.diagnostics();
  }, { timeline, catalog });
  assert.equal(fireside.scene, 'fireside');
  await page.screenshot({ path: join(tmpdir(), 'comic-theatre-fireside.png') });
  const disposed = await page.evaluate(() => { window.player.dispose(); window.player.dispose(); try { window.player.renderAt(0); return false; } catch { return true; } });
  assert.equal(disposed, true);
  assert.deepEqual(errors, []);

  await page.setViewportSize({ width: 432, height: 540 });
  await page.evaluate(async ({ timeline, catalog }) => {
    const { createPlayer } = await import('/src/player.mjs');
    window.player = await createPlayer(document.querySelector('canvas'), { timeline: { ...timeline, width: 432, height: 540 }, catalog });
  }, { timeline, catalog });
  for (const [frame, name] of [[60, 'closeup'], [126, 'held'], [156, 'turn'], [228, 'opening'], [324, 'reaction']]) {
    await render(frame);
    await page.screenshot({ path: join(tmpdir(), `comic-theatre-portrait-${name}.png`) });
  }
  await page.evaluate(() => window.player.dispose());

  if (catalog.comics.length > 1) {
    const second = catalog.comics[1];
    const tour = { ...timeline, width: 432, height: 540, duration: 8, frames: 192,
      scene: 'fireside', template: 'page-tour', sources: [comic.id, second.id], events: [
        { id: 'first-source', type: 'source', comic: comic.id, start: 0, end: 2 },
        { id: 'first-talk', type: 'line', comic: comic.id, speaker: 'reader', shot: 'two-shot', start: 2, end: 3, mouth: [] },
        { id: 'second-source', type: 'source', comic: second.id, start: 3, end: 5 },
        { id: 'second-talk', type: 'line', comic: second.id, speaker: 'friend', shot: 'two-shot', start: 5, end: 6, mouth: [] },
        { id: 'table-read', type: 'action', rail: 'read', comic: second.id, start: 6, end: 7, bookState: 'table-open' },
        { id: 'quiet', type: 'hold', comic: second.id, speaker: 'reader', start: 7, end: 8, mouth: [] },
      ] };
    await page.evaluate(async ({ timeline, catalog }) => {
      const { createPlayer } = await import('/src/player.mjs');
      window.player = await createPlayer(document.querySelector('canvas'), { timeline, catalog });
    }, { timeline: tour, catalog });
    const selected = await render(90);
    assert.equal(selected.source.id, second.id);
    assert.equal(selected.book.selectedPdfPage, second.pdfPage);
    assert.equal(selected.book.page, Math.floor((second.pdfPage - 2) / 2));
    await page.screenshot({ path: join(tmpdir(), 'comic-theatre-portrait-source.png') });
    const tableRead = await render(156);
    assert.equal(tableRead.book.held, 0, 'read on a table does not lift the book');
    assert.equal(tableRead.book.state, 'table-open');
    assert.equal(tableRead.actors.find(a => a.id === 'reader').gazeTarget, 'book', 'table reading directs the head toward the page');
    assert.equal((await render(60)).book.selectedPdfPage, comic.pdfPage, 'reverse source cut restores the prior exact page');
    await page.screenshot({ path: join(tmpdir(), 'comic-theatre-portrait-fireside.png') });
    await page.evaluate(() => window.player.dispose());
    const rejection = await page.evaluate(async ({ timeline, catalog }) => {
      const { createPlayer } = await import('/src/player.mjs');
      try {
        await createPlayer(document.querySelector('canvas'), { timeline, catalog: { ...catalog, comics: catalog.comics.map(c => ({ ...c, verified: false })) } });
        return false;
      } catch (e) { return /unverified/.test(e.message); }
    }, { timeline: tour, catalog });
    assert.equal(rejection, true, 'unverified source images fail before rendering');
  }
  assert.deepEqual(errors, []);
});
