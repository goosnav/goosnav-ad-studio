import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { createHash } from 'node:crypto';
import { startServer } from '../src/server.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = new URL('../assets/book2-item.mp4', import.meta.url);

test('real MP4 endcard: decoded absolute seeks, full resolution, authored copy, bounded failures', { timeout: 45000 }, async t => {
  const server = createServer(async (req, res) => {
    try {
      if (req.url === '/') {
        res.setHeader('Content-Type', 'text/html');
        return res.end('<style>body{margin:0}</style><script type="importmap">{"imports":{"three":"/node_modules/three/build/three.module.js"}}</script>');
      }
      if (req.url === '/stalled.mp4') return;
      if (req.url === '/stalled-body.mp4') {
        res.writeHead(200, { 'Content-Type': 'video/mp4' }); res.write('incomplete'); return;
      }
      if (req.url === '/unseekable.mp4') {
        res.setHeader('Content-Type', 'application/octet-stream');
        res.writeHead(200); // Deliberately chunked: reproduce the old integration fixture.
        return res.end(await readFile(source));
      }
      const path = resolve(root, `.${req.url}`);
      if (!path.startsWith(root)) throw Error('outside fixture');
      res.setHeader('Content-Type', req.url === '/fixture.mp4' ? 'video/mp4' : /\.m?js$/.test(path) ? 'text/javascript' : 'application/octet-stream');
      const data = await readFile(req.url === '/fixture.mp4' ? source : path);
      // Match frozen production assets: full 200 response, known length, no Range support.
      res.setHeader('Content-Length', data.length); res.end(data);
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  t.after(() => new Promise(r => { server.closeAllConnections(); server.close(r); }));
  const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  assert.equal(await page.evaluate(async () => typeof (await import('/src/endcard.mjs')).loadEndcardVideo), 'function', 'endcard exports the owned paused-video loader');
  const result = await page.evaluate(async () => {
    const { loadEndcardVideo, createEndcard } = await import('/src/endcard.mjs');
    const T = await import('three');
    for (const [family, file, weight] of [['ComicTheatreSans', 'LiberationSans-Bold.ttf', 'bold'], ['ComicTheatreTimes', 'LiberationSerif-Regular.ttf', 'normal']]) {
      const font = await new FontFace(family, `url(/assets/fonts/${file})`, { weight }).load(); document.fonts.add(font);
    }
    const resource = await loadEndcardVideo('/fixture.mp4');
    const { video } = resource;
    const loaded = { paused: video.paused, width: video.videoWidth, height: video.videoHeight, duration: video.duration };
    const copy = { title: 'Comics for the shelf.', text: 'Take the strange bits home.', url: 'www.goosnav.shop/books' };
    const endcard = createEndcard({ width: 1080, height: 1350, card: copy, video, videoAsset: { path: 'assets/book2-item.mp4' } });
    const renderer = new T.WebGLRenderer({ preserveDrawingBuffer: true }); renderer.setSize(1080, 1350); document.body.append(renderer.domElement);
    const images = [], times = [];
    for (const seconds of [0, 5, 0, 0, 15, -15]) {
      await endcard.renderAt(seconds); renderer.render(endcard.scene, endcard.camera); images.push(renderer.domElement.toDataURL());
      times.push({ current: video.currentTime, seeking: video.seeking, ready: video.readyState });
    }
    const canvas = endcard.scene.children[0].material.map.image;
    const actual = canvas.getContext('2d').getImageData(0, 270, 1080, 756).data;
    const reference = document.createElement('canvas'); reference.width = 1080; reference.height = 1350;
    reference.getContext('2d').drawImage(video, 0, 0);
    const expected = reference.getContext('2d').getImageData(0, 270, 1080, 756).data;
    const rawPixelsUnchanged = actual.every((v, i) => v === expected[i]);
    const diagnostics = endcard.diagnostics();
    const longCopy = { title: 'A shelf of strange little stories. '.repeat(4).slice(0, 120), text: 'A book to read, revisit and share. '.repeat(8).slice(0, 240), url: 'www.goosnav.shop/' + 'a'.repeat(144) };
    const longCard = createEndcard({ width: 432, height: 540, card: longCopy, video });
    await longCard.renderAt(1);
    const longTypography = longCard.diagnostics().typography;
    const longImage = longCard.scene.children[0].material.map.image.toDataURL();
    const ownedURL = video.src;
    resource.dispose(); resource.dispose();
    let revoked = false;
    try { await fetch(ownedURL); } catch { revoked = true; }
    let disposedRejected = false;
    try { await endcard.renderAt(1); } catch { disposedRejected = true; }
    renderer.dispose();
    return { loaded, images, times, rawPixelsUnchanged, diagnostics, longCopy, longTypography, longImage, disposedRejected, revoked, ownedURL, released: !video.getAttribute('src') };
  });
  assert.deepEqual(result.loaded, { paused: true, width: 1080, height: 1350, duration: 15 });
  assert.deepEqual(result.times.map(t => t.current), [2, 7, 2, 2, 2, 2]);
  const hashes = result.images.map(image => createHash('sha256').update(image).digest('hex'));
  t.diagnostic(JSON.stringify(result.times));
  for (const [index, image] of result.images.slice(0, 2).entries()) await writeFile(join(tmpdir(), `comic-theatre-endcard-video-${index}.png`), Buffer.from(image.split(',')[1], 'base64'));
  assert.notEqual(hashes[0], hashes[1], 'different source times show different product pixels');
  for (const index of [2, 3, 4, 5]) assert.equal(hashes[index], hashes[0], 'backward, repeated and wrapped seeks are pixel identical');
  assert.equal(result.rawPixelsUnchanged, true, 'video pixels are neither downscaled again nor quantized');
  for (const [key, value] of Object.entries({ title: 'Comics for the shelf.', text: 'Take the strange bits home.', url: 'www.goosnav.shop/books' })) assert.equal(result.diagnostics.typography[key].lines.join(' '), value);
  assert.equal(result.diagnostics.typography.url.color, '#0000ee');
  assert.equal(result.diagnostics.typography.url.underline, true);
  assert.match(result.diagnostics.typography.url.font, /Times/);
  assert.equal(result.disposedRejected, true); assert.equal(result.released, true);
  for (const key of ['title', 'text', 'url']) {
    const block = result.longTypography[key];
    assert.ok(block.size >= 12, `${key} stays readable at 432x540`);
    assert.equal(block.lines.join('').replace(/\s/g, ''), result.longCopy[key].replace(/\s/g, ''));
    assert.ok(block.rect.y >= 0 && block.rect.y + block.rect.height <= 540);
  }
  const { title, text, url } = result.longTypography;
  assert.ok(title.rect.y + title.rect.height <= 540 * .15);
  assert.ok(text.rect.y >= 540 * .80, 'footer stays below the product and shadow');
  assert.ok(text.rect.y + text.rect.height < url.rect.y, 'body and URL have disjoint safe areas');
  await writeFile(join(tmpdir(), 'comic-theatre-endcard-long-copy.png'), Buffer.from(result.longImage.split(',')[1], 'base64'));
  assert.match(result.ownedURL, /^blob:/); assert.equal(result.revoked, true, 'dispose revokes its owned blob URL');
  const chunked = await page.evaluate(async () => {
    const { loadEndcardVideo, createEndcard } = await import('/src/endcard.mjs');
    const resource = await loadEndcardVideo('/unseekable.mp4');
    try {
      const card = createEndcard({ width: 432, height: 540, card: { title: '', text: '', url: '' }, video: resource.video });
      const images = [], times = [];
      for (const seconds of [1, 5, 1]) {
        await card.renderAt(seconds); times.push(resource.video.currentTime);
        images.push(card.scene.children[0].material.map.image.toDataURL());
      }
      return { times, changed: images[0] !== images[1], restored: images[0] === images[2] };
    } finally { resource.dispose(); }
  });
  assert.deepEqual(chunked, { times: [3, 7, 3], changed: true, restored: true }, 'chunked octet-stream MP4 is accurately seekable without range support');
  const failures = await page.evaluate(async () => {
    const { loadEndcardVideo, createEndcard } = await import('/src/endcard.mjs');
    const results = [];
    for (const url of ['/missing.mp4', '/stalled.mp4', '/stalled-body.mp4']) {
      const start = performance.now();
      try { (await loadEndcardVideo(url)).dispose(); results.push({ rejected: false }); }
      catch (error) { results.push({ rejected: true, elapsed: performance.now() - start, message: error.message }); }
    }
    try { createEndcard({ width: 1080, height: 1350, card: {} }); results.push({ rejected: false }); }
    catch { results.push({ rejected: true }); }
    return results;
  });
  for (const failure of failures) assert.equal(failure.rejected, true, 'missing, stalled or absent videos must fail rather than become a static card');
  for (const failure of failures.slice(0, 3)) assert.ok(failure.elapsed < 10000, `failure is bounded: ${failure.elapsed}ms`);
});

test('createPlayer seeks frame 120 with actual production frozen MP4 delivery', { timeout: 45000 }, async t => {
  const server = await startServer({ port: 0 });
  t.after(() => server.close());
  const browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  t.after(() => browser.close());
  const page = await browser.newPage();
  await page.goto(server.url);
  const result = await page.evaluate(async () => {
    const catalog = await (await fetch('/api/catalog')).json();
    const response = await fetch(`/${catalog.assets.endCardVideo.path}`, { headers: { Range: 'bytes=0-99' } });
    const delivery = { status: response.status, type: response.headers.get('content-type'), length: Number(response.headers.get('content-length')), range: response.headers.get('content-range') };
    await response.arrayBuffer();
    const map = document.createElement('script'); map.type = 'importmap';
    map.textContent = JSON.stringify({ imports: { three: '/node_modules/three/build/three.module.js', 'three/addons/': '/node_modules/three/examples/jsm/' } }); document.head.append(map);
    const { createPlayer } = await import('/src/player.mjs');
    const timeline = { version: 1, fps: 12, width: 432, height: 540, frames: 144, duration: 12, seed: 21,
      scene: 'library', template: 'book-duet', cast: ['reader', 'friend'], sources: [catalog.comics[0].id],
      events: [{ id: 'closing', type: 'endcard', start: 9, end: 12, title: 'Keep reading', text: 'Comics for your shelf.', url: 'www.goosnav.shop' }] };
    const canvas = document.createElement('canvas'); document.body.append(canvas);
    const player = await createPlayer(canvas, { timeline, catalog });
    try {
      const images = [], times = [];
      for (const frame of [120, 132, 120]) {
        await player.renderAt(frame); images.push(canvas.toDataURL()); times.push(player.diagnostics().endCard.sourceTime);
      }
      return { delivery, times, changed: images[0] !== images[1], restored: images[0] === images[2], shot: player.diagnostics().shot };
    } finally { player.dispose(); }
  });
  assert.equal(result.delivery.status, 200); assert.equal(result.delivery.type, 'video/mp4');
  assert.ok(result.delivery.length > 0); assert.equal(result.delivery.range, null);
  assert.deepEqual(result.times, [3, 4, 3]);
  assert.equal(result.changed, true); assert.equal(result.restored, true); assert.equal(result.shot, 'endcard');
});

for (const fps of [12, 24, 30]) test(`fractional ${fps}fps endcard seeks survive a 12.975s start and restore every frame`, { timeout: 90000 }, async t => {
  const server = await startServer({ port: 0 }); t.after(() => server.close());
  const browser = await chromium.launch({ headless: true }); t.after(() => browser.close());
  const page = await browser.newPage(); await page.goto(server.url);
  const result = await page.evaluate(async fps => {
    const { loadEndcardVideo, seekEndcardVideo } = await import('/src/endcard-video.mjs');
    const catalog = await (await fetch('/api/catalog')).json();
    const resource = await loadEndcardVideo(`/${catalog.assets.endCardVideo.path}`);
    const canvas = document.createElement('canvas'); canvas.width = 432; canvas.height = 540;
    const context = canvas.getContext('2d');
    const runs = [];
    try {
      {
        const frames = [], images = []; let maxDrift = 0;
        for (let f = Math.ceil(12.975 * fps); f < Math.ceil(15.975 * fps); f++) frames.push(f);
        const draw = async frame => {
          const target = 2 + (frame / fps - 12.975);
          try { await seekEndcardVideo(resource.video, target); }
          catch (error) { throw Error(JSON.stringify({ fps, frame, target, actual: resource.video.currentTime, drift: resource.video.currentTime - target, error: error.message })); }
          maxDrift = Math.max(maxDrift, Math.abs(resource.video.currentTime - target));
          context.drawImage(resource.video, 0, 0, 432, 540);
          const hash = await crypto.subtle.digest('SHA-256', context.getImageData(0, 0, 432, 540).data);
          return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
        };
        for (const frame of frames) images.push(await draw(frame));
        let restored = true, repeated = true;
        for (let i = frames.length - 1; i >= 0; i--) {
          restored &&= await draw(frames[i]) === images[i];
          repeated &&= await draw(frames[i]) === images[i];
        }
        runs.push({ fps, count: frames.length, maxDrift, restored, repeated, changes: new Set(images).size });
      }
      return { runs };
    } catch (error) { return { error: error.message }; }
    finally { resource.dispose(); }
  }, fps);
  assert.equal(result.error, undefined, result.error);
  assert.deepEqual(result.runs.map(r => r.count), [fps * 3]);
  for (const run of result.runs) {
    assert.equal(run.restored, true); assert.equal(run.repeated, true);
    assert.ok(run.changes >= 30); assert.ok(run.maxDrift < .001);
  }
  t.diagnostic(JSON.stringify(result.runs));
});
