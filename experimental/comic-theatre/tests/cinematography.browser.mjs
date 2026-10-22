import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve, sep, extname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { compileTimeline } from '../src/timeline.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
async function fixture(t) {
  const catalog = JSON.parse(await readFile(resolve(root, 'assets/catalog.json'), 'utf8'));
  const server = createServer(async (req, res) => {
    try {
      const pathname = new URL(req.url, 'http://localhost').pathname;
      if (pathname === '/') {
        res.setHeader('Content-Type', 'text/html');
        return res.end('<style>body{margin:0}canvas{display:block}</style><script type="importmap">{"imports":{"three":"/node_modules/three/build/three.module.js","three/addons/":"/node_modules/three/examples/jsm/"}}</script><canvas></canvas>');
      }
      const path = resolve(root, `.${pathname}`);
      if (!path.startsWith(root.replace(/\/$/, '') + sep)) throw Error('outside fixture');
      res.setHeader('Content-Type', ({ '.mjs': 'text/javascript', '.js': 'text/javascript', '.glb': 'model/gltf-binary', '.jpg': 'image/jpeg', '.mp4':'video/mp4' })[extname(path)] || 'application/octet-stream');
      const bytes = await readFile(path); res.setHeader('Content-Length',bytes.length); res.end(bytes);
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  t.after(() => new Promise(r => { server.closeAllConnections(); server.close(r); }));
  const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 432, height: 768 } });
  const errors = [], external = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (!r.url().startsWith(`http://127.0.0.1:${server.address().port}`) && !r.url().startsWith('blob:') && !r.url().startsWith('data:')) external.push(r.url()); });
  t.after(() => { assert.deepEqual(errors, []); assert.deepEqual(external, []); });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  // Observe the actual render camera, drawn geometry and canvas text, without
  // giving production code a test-only scene accessor or a second rendering path.
  await page.evaluate(async () => {
    const T = await import('three');
    T.Scene.prototype.onBeforeRender = function(renderer, scene, camera) {
      window.drawnScene = scene; window.drawnCamera = camera; window.drawnRenderer = renderer;
    };
    const fillText = CanvasRenderingContext2D.prototype.fillText;
    window.drawnText = [];
    CanvasRenderingContext2D.prototype.fillText = function(text, x, y, ...rest) {
      window.drawnText.push({ text, x, y, font: this.font, color: this.fillStyle,
        rasterSize: Number(this.font.match(/([\d.]+)px/)?.[1]) * this.getTransform().a });
      return fillText.call(this, text, x, y, ...rest);
    };
    window.T = T;
    window.visibleEyePixels = (id, names = ['eye_white']) => {
      const scene = window.drawnScene, camera = window.drawnCamera, renderer = window.drawnRenderer;
      const black = new T.MeshBasicMaterial({ color: 0, toneMapped: false, side: T.DoubleSide });
      const magenta = new T.MeshBasicMaterial({ color: 0xff00ff, toneMapped: false, side: T.DoubleSide });
      const saved = [];
      scene.traverse(o => {
        if (!o.isMesh) return;
        let ancestor = o, target = false;
        while (ancestor) { if (ancestor.name === `actor-${id}`) target = true; ancestor = ancestor.parent; }
        const mask = m => target && names.some(name => m.name.includes(name)) ? magenta : black;
        saved.push([o, o.material]); o.material = Array.isArray(o.material) ? o.material.map(mask) : mask(o.material);
      });
      try {
        renderer.render(scene, camera);
        const gl = renderer.getContext(), pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
        gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
        let count = 0;
        for (let i = 0; i < pixels.length; i += 4) if (pixels[i] > 200 && pixels[i + 1] < 40 && pixels[i + 2] > 200) count++;
        return count;
      } finally {
        for (const [o, material] of saved) o.material = material;
        black.dispose(); magenta.dispose(); renderer.render(scene, camera);
      }
    };
  });
  const timeline = { version: 1, fps: 12, width: 432, height: 768, frames: 144, duration: 12,
    scene: 'library', template: 'page-tour', seed: 11, cast: ['reader', 'friend'],
    sources: catalog.comics.map(c => c.id), events: [
      { id: 'physical-source', type: 'source', comic: catalog.comics[1].id, shot: 'book', start: 0, end: 3 },
      { id: 'two', type: 'line', speaker: 'reader', shot: 'two-shot', start: 3, end: 5 },
      { id: 'reader', type: 'line', speaker: 'reader', shot: 'speaker', start: 5, end: 6 },
      { id: 'friend', type: 'line', speaker: 'friend', shot: 'speaker', start: 6, end: 7 },
      { id: 'ots', type: 'line', speaker: 'reader', shot: 'over-shoulder', start: 7, end: 8,
        mouth: [{t:0,value:0},{t:.5,value:.8},{t:1,value:0}] },
      { id: 'flat', type: 'source', comic: catalog.comics[0].id, shot: 'source', start: 8, end: 9 },
      { id: 'other-book', type: 'source', comic: catalog.comics[2].id, shot: 'book', start: 9, end: 12 },
    ] };
  const load = async (input = timeline, assets = catalog) => page.evaluate(async ({ timeline, catalog }) => {
    window.player?.dispose();
    window.drawnText = [];
    const { createPlayer } = await import('/src/player.mjs');
    window.player = await createPlayer(document.querySelector('canvas'), { timeline, catalog });
  }, { timeline: input, catalog: assets });
  const render = frame => page.evaluate(async f => {
    await window.player.renderAt(f);
    return { ...window.player.diagnostics(), perspective: window.drawnCamera.isPerspectiveCamera === true,
      physicalBook: !!window.drawnScene.getObjectByName('controlled-original-book'),
      pixels: document.querySelector('canvas').toDataURL() };
  }, frame);
  const capture = name => page.screenshot({ path: join(tmpdir(), `comic-cinematography-${name}.png`) });
  return { page, timeline, catalog, load, render, capture };
}

// Breaks if source:book is flattened, the wrong GLB page is framed, the pan is
// stateful, or portrait framing loses/shrinks either actor.
test('physical selected-page reveal, portrait conversations and reverse seeks use actual rendered geometry', { timeout: 120000 }, async t => {
  const { page, catalog, timeline, load, render, capture } = await fixture(t);
  await load();
  const start = await render(0);
  assert.equal(start.shot, 'book');
  assert.equal(start.physicalBook, true);
  assert.equal(start.perspective, true);
  assert.equal(start.book.selectedPdfPage, 40);
  assert.equal(start.book.page, 19);
  await capture('book-wide');
  const reading = await page.evaluate(() => {
    const book = drawnScene.getObjectByName('controlled-original-book');
    const reader = drawnScene.getObjectByName('actor-reader');
    const top = new T.Vector3(0,0,-1).transformDirection(book.matrixWorld);
    const away = book.position.clone().sub(reader.position); away.y=0; away.normalize();
    let inkMaterial;
    book.traverse(o=>{for(const m of(Array.isArray(o.material)?o.material:[o.material]))if(m?.name==='Comic page 38')inkMaterial=m;});
    return {facing:top.dot(away),unlit:inkMaterial?.isMeshBasicMaterial,toneMapped:inkMaterial?.toneMapped};
  });
  assert.ok(reading.facing>.8,'top of page points away from readers, not toward them');
  assert.equal(reading.unlit,true,'original page ink is not washed out by room lights');
  assert.equal(reading.toneMapped,false);
  const pushed = await render(32);
  assert.notDeepEqual(pushed.camera.position, start.camera.position, 'book reveal moves slowly toward the selected page');
  assert.equal(pushed.book.selectedPdfPage, 40);
  await capture('book-push');
  // Raycast the center of the real frame; labels alone cannot prove the page is visible.
  const centerPage = await page.evaluate(() => {
    const ray = new T.Raycaster(); ray.setFromCamera(new T.Vector2(0, 0), window.drawnCamera);
    return ray.intersectObject(window.drawnScene, true).filter(h => h.object.isMesh).slice(0, 4).map(h => {
      const mats = h.object.material;
      return Array.isArray(mats) ? mats[h.face.materialIndex]?.name : mats.name;
    });
  });
  assert.ok(centerPage.includes('Comic page 38'), `center ray must hit actual PDF page 40 (interior 38), got ${centerPage}`);
  const two = await render(42);
  await capture('two-shot');
  const heads = await page.evaluate(() => ['reader', 'friend'].map(id => {
    const bounds = new T.Box2();
    window.drawnScene.getObjectByName(`actor-${id}`).traverse(o => {
      if (!o.isMesh) return;
      for (let i = 0; i < o.geometry.attributes.position.count; i++) {
        const p = o.getVertexPosition(i, new T.Vector3()).applyMatrix4(o.matrixWorld);
        if (p.y < 1.25 || p.y > 1.82) continue;
        p.project(window.drawnCamera); bounds.expandByPoint(new T.Vector2(p.x, p.y));
      }
    });
    return { id, min: bounds.min.toArray(), max: bounds.max.toArray() };
  }));
  for (const h of heads) {
    assert.ok(h.min[0] > -.96 && h.max[0] < .96 && h.min[1] > -.9 && h.max[1] < .96, `whole ${h.id} head and nose in portrait frame: ${JSON.stringify(h)}`);
    assert.ok(h.max[1] - h.min[1] > .3, `readable ${h.id} portrait size`);
  }
  const reader = await render(64); await capture('reader');
  const friend = await render(76); await capture('friend');
  assert.notDeepEqual(reader.camera.position, friend.camera.position);
  const ots = await render(88); await capture('ots');
  assert.equal(ots.shot, 'over-shoulder');
  assert.notDeepEqual(ots.camera.position, two.camera.position);
  assert.notDeepEqual(ots.camera.position, reader.camera.position);
  const visibleActors = await page.evaluate(() => {
    const ids = new Set(), ray = new T.Raycaster();
    for (const x of [-.8, -.4, 0, .4, .8]) for (const y of [-.5, 0, .4]) {
      ray.setFromCamera(new T.Vector2(x, y), window.drawnCamera);
      let object = ray.intersectObject(window.drawnScene, true)[0]?.object;
      while (object) { if (object.name.startsWith('actor-')) ids.add(object.name); object = object.parent; }
    }
    return [...ids];
  });
  assert.ok(visibleActors.includes('actor-reader'), 'OTS must see the speaker, never the outside of the set wall');
  assert.ok(visibleActors.includes('actor-friend'), 'OTS must include a listening shoulder in the foreground');
  assert.ok(await page.evaluate(() => window.visibleEyePixels('reader')) > 30, 'OTS foreground cannot hide the speaking face');
  assert.ok(await page.evaluate(() => window.visibleEyePixels('reader', ['mouth_dark','tongue'])) > 10,
    'near actor must not occlude the actual speaking oral-cavity geometry');
  const flat = await render(100); await capture('flat');
  assert.equal(flat.source.fit, 'contain'); assert.equal(flat.perspective, false);
  assert.equal((await render(138)).book.selectedPdfPage, 99); await capture('other-book');
  assert.deepEqual(await render(32), pushed, 'identical camera, pose and pixels after reverse seek');
  assert.deepEqual(await render(42), two);
  // Catalog bytes stay identical; originals never pass through a drawing filter.
  for (const item of [...catalog.comics, catalog.assets.cover, catalog.assets.book]) {
    assert.equal(createHash('sha256').update(await readFile(resolve(root, item.path))).digest('hex'), item.sha256);
  }
  await page.setViewportSize({ width: 432, height: 540 });
  await load({ ...timeline, width: 432, height: 540 });
  for (const [frame, name] of [[0, 'book-wide'], [32, 'book-push'], [42, 'two'], [64, 'reader'], [76, 'friend'], [88, 'ots']]) {
    await render(frame); await capture(`4x5-${name}`);
    if(name==='ots')assert.ok(await page.evaluate(() => window.visibleEyePixels('reader', ['mouth_dark','tongue'])) > 10,
      '4:5 OTS also keeps the actual speaking mouth visible');
  }
  await page.setViewportSize({ width: 960, height: 540 });
  await load({ ...timeline, width: 960, height: 540 });
  await render(42); await capture('landscape-two');
  const concurrent = compileTimeline({ ...timeline, output:{width:432,height:540,fps:12},
    comics:[catalog.comics[1].id],cast:[{id:'reader'},{id:'friend'}],lines:[
      {id:'narration',speaker:'reader',comic:catalog.comics[1].id,shot:'auto',pause:0},
    ] }, { narration:{duration:7,mouth:[{t:0,value:0},{t:.5,value:.8},{t:7,value:0}]} });
  await load(concurrent);
  const opening=await render(6);
  assert.equal(opening.shot,'book');assert.equal(opening.activeEvent,'narration');
  assert.equal(opening.source.pdfPage,40);
  assert.equal((await render(59)).shot,'book');
  assert.equal((await render(60)).shot,'two-shot','readers appear after five seconds without a speech gap');
});

// Breaks if an endcard is rejected, ignores authored text, changes the URL to
// non-Times/plain text, mutates a frame on seeking, or ignores enabled:false.
test('endcard draws exact custom text, spinning product and a blue Times URL locally', { timeout: 120000 }, async t => {
  const { page, catalog, timeline, load, render, capture } = await fixture(t);
  const endCard = { enabled: true, title: 'Comics for the shelf.', text: 'Take the strange bits home.', url: 'www.goosnav.shop/books', seconds: 3 };
  const events = [...timeline.events.filter(e => e.start < 9), { id: 'end-card', type: 'endcard', start: 9, end: 12, ...endCard }];
  await load({ ...timeline, endCard: { ...endCard, title: 'Fallback title' }, events });
  const card = await render(120); await capture('endcard');
  assert.equal(card.shot, 'endcard');
  const text = await page.evaluate(() => window.drawnText);
  for (const expected of [endCard.title, endCard.text, endCard.url]) assert.ok(text.some(t => t.text === expected), `actual canvas draws ${expected}`);
  const url = text.find(t => t.text === endCard.url);
  assert.match(url.font, /Times|Tinos/);
  assert.equal(url.color, '#0000ee');
  assert.equal(card.endCard.video.path, catalog.assets.endCardVideo.path);
  const beforeSeek=await render(0);
  const raced=await page.evaluate(async()=>{
    const pending=window.player.renderAt(120);
    await window.player.renderAt(0);
    await pending;
    return {pixels:document.querySelector('canvas').toDataURL(),frame:window.player.diagnostics().frame};
  });
  assert.equal(raced.frame,0);
  assert.ok(raced.pixels===beforeSeek.pixels,'a stale video seek cannot paint over a newer conversation frame');
  await render(64); assert.deepEqual(await render(120), card, 'endcard pixels survive reverse seeking');
  await load({ ...timeline, endCard, events: [...events.slice(0, -1), { id: 'end-card', type: 'endcard', start: 9, end: 12 }] });
  await render(120);
  assert.ok((await page.evaluate(() => window.drawnText)).some(t => t.text === endCard.title), 'timeline endCard fills absent event fields');
  await load({ ...timeline, endCard: { ...endCard, enabled: false }, events: [...events.slice(0, -1), { id: 'end-card', type: 'endcard', start: 9, end: 12 }] });
  assert.notEqual((await render(120)).shot, 'endcard');
  const long = { ...endCard, title: 'A shelf of strange little stories. '.repeat(4).slice(0, 120), text: 'A book to read, revisit and share. '.repeat(8).slice(0, 240), url: 'www.goosnav.shop/' + 'a'.repeat(144) };
  await page.setViewportSize({ width: 432, height: 540 });
  await load({ ...timeline, height: 540, endCard: long, events: [...events.slice(0, -1), { id: 'end-card', type: 'endcard', start: 9, end: 12 }] });
  const longCard = await render(120); await capture('4x5-endcard-long');
  for (const key of ['title', 'text', 'url']) {
    assert.equal(longCard.endCard.typography[key].lines.join('').replace(/\s/g, ''), long[key].replace(/\s/g, ''), `${key} is wrapped without truncation`);
    assert.ok(longCard.endCard.typography[key].size >= 12, `${key} stays readable at 4:5 size`);
  }
  assert.ok((await page.evaluate(() => window.drawnText)).every(t => t.rasterSize >= 11), 'maximum text lengths retain readable glyph resolution before aliasing');
  const manyBreaks = { ...endCard, title: 'A\n'.repeat(60), text: 'First line.\nSecond line.' };
  await load({ ...timeline, height: 540, endCard: manyBreaks, events: [...events.slice(0, -1), { id: 'end-card', type: 'endcard', start: 9, end: 12 }] });
  const wrapped = await render(120); await capture('4x5-endcard-newlines');
  assert.equal(wrapped.endCard.typography.title.lines.join('').replace(/\s/g, ''), 'A'.repeat(60), 'excessive breaks reflow without losing text');
  assert.deepEqual(wrapped.endCard.typography.text.lines, ['First line.', 'Second line.'], 'ordinary authored line breaks stay intact');
  const title = wrapped.endCard.typography.title;
  assert.ok(title.lines.length * title.size * 1.22 <= 540 * .13, 'all title lines fit their rectangle above the cover');
});

test('variant selection resolves catalog asset keys and never silently replaces a missing modern variant', { timeout: 120000 }, async t => {
  const { timeline, catalog, load, render } = await fixture(t);
  const modern = { ...catalog, variants: [
    { id: 'blue', label: 'Blue', asset: 'actorBlue' }, { id: 'rust', label: 'Rust', asset: 'actorRust' },
  ], assets: { ...catalog.assets, actorBlue: catalog.assets.actor, actorRust: catalog.assets.actor } };
  // Aliased real GLBs exercise resolution before the independently built variant
  // snapshots arrive. The final bundled catalog is also exercised by fixture().
  delete modern.assets.actor;
  await load({ ...timeline, characters: { reader: 'rust', friend: 'blue' } }, modern);
  const result = await render(42);
  assert.deepEqual(result.actors.map(a => a.variant), ['rust', 'blue']);
  assert.equal(result.independentSkeletons, true);
  await assert.rejects(() => load({ ...timeline, characters: { reader: 'olive', friend: 'blue' } }, modern), /variant/i);
});
