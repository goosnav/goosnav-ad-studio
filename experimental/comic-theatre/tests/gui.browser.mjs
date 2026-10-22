import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { readFile } from 'node:fs/promises';

// Only HTTP is mocked: the actual web files, browser input, downloads and fetch
// requests run normally. No renderer, parent runtime, writer or voice is started.
const root = new URL('../', import.meta.url);
const token = 'gui-test-session-token';
const hostile = '<img src=x onerror="window.injected=true">';
const catalog = {
  version: 1, edition: { id: 'fixture', title: 'Test edition', pdfSha256: 'a'.repeat(64), evidence: 'Test fixture only' },
  assets: { actor: { path: 'assets/actor.glb', sha256: 'b'.repeat(64) }, book: { path: 'assets/book.glb', sha256: 'c'.repeat(64) } },
  comics: ['page-a', 'page-b', 'page-c'].map((id, i) => ({
    id, title: i === 0 ? hostile : `Comic ${i + 1}`, path: `assets/comics/${id}.png`,
    sha256: String(i + 1).repeat(64), pdfPage: i + 10, printedPage: i + 8,
    transcript: i === 0 ? `Literal transcript: ${hostile}` : `Transcript ${i + 1}`,
    observations: 'Fixture observation', verified: true,
  })),
  templates: [
    { id: 'book-duet', label: 'Book duet', minComics: 1, maxComics: 2, speakers: ['reader', 'friend'], scenes: ['library', 'fireside'] },
    { id: 'fireside-reader', label: 'Fireside reader', minComics: 1, maxComics: 1, speakers: ['reader'], scenes: ['fireside'] },
    { id: 'page-tour', label: 'Page tour', minComics: 1, maxComics: 3, speakers: ['reader'], scenes: ['library'] },
  ], scenes: [{ id: 'library', label: 'Library' }, { id: 'fireside', label: 'Fireside' }],
};
const script = (ids = ['page-a']) => ({
  version: 1, template: 'book-duet', title: 'My reading', comics: ids,
  lines: ids.map(comic => ({ speaker: 'reader', text: `Reading ${comic}`, comic })),
});
let browser;
let launchError;
before(async () => {
  try {
    const { chromium } = await import('playwright');
    browser = await chromium.launch({ headless: true, ...(process.env.THEATRE_TEST_CHROMIUM ? { executablePath: process.env.THEATRE_TEST_CHROMIUM } : {}) });
  } catch (error) { launchError = error; }
});
after(async () => { await browser?.close(); });

async function fixture(t, { clock = false } = {}) {
  if (!browser) {
    t.skip(`Installed Playwright/Chromium unavailable. Run npm run setup:browser or set THEATRE_TEST_CHROMIUM. ${launchError?.message}`);
    return;
  }
  const state = { requests: [], assets: [], jobs: [], polls: 0, draft: 'unconfigured', draftDelay: 0, selectDelay: 0, validationError: '', sessionError: false, jobsError: false, resolved: false };
  const held = new Map();
  state.hold = path => {
    let release;
    const promise = new Promise(resolve => { release = resolve; });
    held.set(path, { promise, release });
  };
  state.release = path => { held.get(path)?.release(); held.delete(path); };
  const resolvedScript = value => ({
    ...value, seed: value.seed ?? 42, scene: value.scene ?? 'library', output: { width: 1080, height: 1350, fps: 24 },
    sourceLock: value.comics.map(id => ({ id, sha256: catalog.comics.find(comic => comic.id === id).sha256, pdfPage: catalog.comics.find(comic => comic.id === id).pdfPage, pdfSha256: catalog.edition.pdfSha256 })),
    cast: [{ id: 'reader', voice: 'am_onyx' }, { id: 'friend', voice: 'am_puck' }],
    lines: value.lines.map((line, i) => ({ ...line, id: `beat-${i}`, bookState: 'table-open' })),
  });
  const resolve = value => state.resolved ? resolvedScript(value) : value;
  const json = (res, status, body) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body)); };
  const server = http.createServer(async (req, res) => {
    try {
      const path = new URL(req.url, 'http://localhost').pathname;
      if (req.method === 'POST') {
        let raw = ''; for await (const chunk of req) raw += chunk;
        const body = JSON.parse(raw);
        state.requests.push({ path, body, token: req.headers['x-theatre-token'], origin: req.headers.origin });
        if (req.headers['x-theatre-token'] !== token) return json(res, 403, { error: 'Missing session token' });
        if (held.has(path)) await held.get(path).promise;
        if (path === '/api/select') {
          await new Promise(resolve => setTimeout(resolve, state.selectDelay));
          return json(res, 200, { script: resolve({ ...script(['page-b']), template: body.template, ...(body.seed === undefined ? {} : { seed: body.seed }) }) });
        }
        if (path === '/api/validate') {
          const resolved = resolvedScript(body.script);
          if (body.script.sourceLock !== undefined && JSON.stringify(body.script.sourceLock) !== JSON.stringify(resolved.sourceLock)) return json(res, 400, { error: 'Source lock changed. Re-select and review the source before creating a new script.' });
          return state.validationError ? json(res, 400, { error: state.validationError }) : json(res, 200, { script: resolved });
        }
        if (path === '/api/draft') {
          await new Promise(resolve => setTimeout(resolve, state.draftDelay));
          if (!body.script.lines.length || body.script.lines.some(line => !line.action && !line.text.trim())) return json(res, 400, { error: 'Writer input needs nonempty placeholder or authored lines for selected pages' });
          if (state.draft === 'unconfigured') return json(res, 409, { error: 'Optional writer is not configured' });
          if (state.draft === 'swap') return json(res, 200, { script: script(['page-c']) });
          return json(res, 200, { script: resolve({ ...body.script, lines: body.script.comics.map(comic => ({ speaker: 'reader', text: 'AI draft text', comic })) }) });
        }
        if (path === '/api/render') {
          state.jobs = [{ id: 'job-1', status: 'queued', progress: 0 }];
          return json(res, 200, { id: 'job-1', status: 'queued' });
        }
      }
      if (path === '/api/session') return state.sessionError ? json(res, 500, { error: 'Session unavailable' }) : json(res, 200, { token });
      if (path === '/api/catalog') return json(res, 200, catalog);
      if (path === '/api/jobs') {
        state.polls++;
        return state.jobsError ? json(res, 500, { error: 'Jobs temporarily unavailable' }) : json(res, 200, { jobs: state.jobs });
      }
      if (path.startsWith('/assets/')) {
        state.assets.push(path);
        res.writeHead(200, { 'Content-Type': 'image/png' });
        return res.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jfRcAAAAASUVORK5CYII=', 'base64'));
      }
      const files = { '/': 'web/index.html', '/app.mjs': 'web/app.mjs', '/style.css': 'web/style.css', '/web/app.mjs': 'web/app.mjs', '/web/style.css': 'web/style.css' };
      if (files[path]) {
        const bytes = await readFile(new URL(files[path], root));
        res.writeHead(200, { 'Content-Type': path.endsWith('.mjs') ? 'text/javascript' : path.endsWith('.css') ? 'text/css' : 'text/html' });
        return res.end(bytes);
      }
      res.writeHead(404); res.end('Not found');
    } catch (error) { res.writeHead(404); res.end(error.code === 'ENOENT' ? 'GUI file not implemented' : error.message); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  if (clock) await page.clock.install();
  page.setDefaultTimeout(3500);
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  t.after(async () => {
    for (const path of held.keys()) state.release(path);
    await context.close();
    await new Promise(resolve => server.close(resolve));
    assert.deepEqual(pageErrors, [], 'No uncaught browser errors');
  });
  const origin = `http://127.0.0.1:${server.address().port}`;
  await page.goto(origin);
  return { page, state, origin };
}
async function ready(page) {
  await page.getByRole('heading', { name: 'Comic Theatre', exact: true }).waitFor();
  await page.locator('#template option[value="book-duet"]').waitFor({ state: 'attached' });
}
async function loadScript(page, value = script()) {
  await page.locator('#script-json').fill(JSON.stringify(value, null, 2));
  await page.getByRole('button', { name: 'Apply JSON', exact: true }).click();
  await page.waitForFunction(title => document.querySelector('#title').value === title, value.title);
}
async function status(page, pattern) {
  await page.waitForFunction(source => new RegExp(source, 'i').test(document.querySelector('#editor-status').textContent), pattern);
}

test('catalog pages are actual asset thumbnails with literal transcripts; template changes preserve selected IDs', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page);
  await page.locator('#gallery img').first().waitFor();
  assert.equal(await page.locator('#gallery img').count(), 3);
  assert.ok(state.assets.includes('/assets/comics/page-a.png'));
  assert.match(await page.locator('#gallery').textContent(), /PDF page 10/);
  assert.match(await page.locator('#gallery').textContent(), /Printed page 8/);
  assert.ok((await page.locator('#gallery').textContent()).includes(hostile));
  await page.getByRole('checkbox', { name: 'Select page-a', exact: true }).check();
  await page.getByRole('checkbox', { name: 'Select page-b', exact: true }).check();
  await page.locator('#template').selectOption('fireside-reader');
  assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).comics, ['page-a', 'page-b']);
  assert.match(await page.locator('#selected-pages').textContent(), /page-a[\s\S]*page-b/);
  await page.getByRole('button', { name: 'Validate', exact: true }).click();
  await status(page, '1.*page|page.*1');
  assert.equal(state.requests.length, 0, 'Invalid selection does not reach server');
  assert.equal(await page.evaluate(() => window.injected), undefined);
});

test('manual dialogue edits synchronize JSON; advanced fields and action rows survive form edits, upload and download', async t => {
  const f = await fixture(t); if (!f) return;
  const { page } = f; await ready(page);
  await page.getByRole('checkbox', { name: 'Select page-a', exact: true }).check();
  await page.getByRole('button', { name: 'Add dialogue', exact: true }).click();
  await page.getByLabel('Line 1 text', { exact: true }).fill(hostile);
  await page.getByLabel('Line 1 speaker', { exact: true }).selectOption('friend');
  await page.getByLabel('Line 1 emotion', { exact: true }).fill('dry');
  await page.getByLabel('Line 1 gesture', { exact: true }).fill('shrug');
  const authored = JSON.parse(await page.locator('#script-json').inputValue());
  assert.deepEqual(authored.lines[0], { speaker: 'friend', text: hostile, comic: 'page-a', emotion: 'dry', gesture: 'shrug' });
  authored.title = 'Advanced reading';
  authored.lines[0].face = { brow_left: 0.4 };
  authored.lines[0].reaction = { emotion: 'curious' };
  authored.lines[0].pause = 0.6;
  authored.lines[0].shot = 'source';
  authored.lines.push({ action: 'close', seconds: 1 });
  await loadScript(page, authored);
  await page.locator('#title').fill('Edited title');
  await page.getByLabel('Line 1 text', { exact: true }).fill('New line');
  const current = JSON.parse(await page.locator('#script-json').inputValue());
  assert.deepEqual(current.lines[0].face, { brow_left: 0.4 });
  assert.deepEqual(current.lines[0].reaction, { emotion: 'curious' });
  assert.deepEqual(current.lines[1], { action: 'close', seconds: 1 });
  assert.match(await page.locator('#dialogue').textContent(), /close/);
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download JSON', exact: true }).click();
  const download = await downloadEvent;
  const stream = await download.createReadStream();
  const chunks = []; for await (const chunk of stream) chunks.push(chunk);
  assert.deepEqual(JSON.parse(Buffer.concat(chunks)), current);
  await page.locator('#upload-json').setInputFiles({ name: 'reading.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(script(['page-b']))) });
  await page.waitForFunction(() => document.querySelector('#title').value === 'My reading');
  assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).comics, ['page-b']);
  assert.equal(await page.evaluate(() => window.injected), undefined);
});

test('unapplied or invalid JSON cannot be overwritten by form controls, jobs, uploads, or generation', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page); await loadScript(page);
  const dirty = '{ "title": "unfinished';
  await page.locator('#script-json').fill(dirty);
  assert.equal(await page.locator('#title').isDisabled(), true);
  await page.getByRole('button', { name: 'Apply JSON', exact: true }).click();
  await status(page, 'JSON');
  state.jobs = [{ id: 'bad', status: 'failed', error: hostile, video: 'javascript:window.injected=true' }];
  await page.getByRole('button', { name: 'Refresh jobs', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#jobs').textContent.includes('failed'));
  assert.equal(await page.locator('#script-json').inputValue(), dirty);
  assert.equal(await page.locator('#jobs a').count(), 0);
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  await status(page, 'Apply JSON|unapplied');
  assert.equal(state.requests.length, 0);
  await page.locator('#upload-json').setInputFiles({ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('null') });
  assert.equal(await page.locator('#script-json').inputValue(), dirty);
  await page.locator('#script-json').fill(JSON.stringify({ ...script(), comics: ['not-in-catalog'] }));
  await page.getByRole('button', { name: 'Apply JSON', exact: true }).click();
  await status(page, 'unknown|catalog');
  assert.equal(await page.locator('#title').inputValue(), 'My reading');
  await page.getByRole('button', { name: 'Revert JSON', exact: true }).click();
  assert.equal(await page.locator('#title').isDisabled(), false);
  assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).comics, ['page-a']);
});

test('random selection sends template, seed and token; validation and rendering use authored pages with local voice only', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state, origin } = f; await ready(page);
  await page.locator('#template').selectOption('page-tour');
  await page.locator('#seed').fill('123');
  await page.getByRole('button', { name: 'Random sample', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#selected-pages').textContent.includes('page-b'));
  assert.deepEqual(state.requests[0].body, { template: 'page-tour', seed: 123 });
  await page.getByRole('button', { name: 'Validate', exact: true }).click();
  await status(page, 'validation passed');
  const authored = JSON.parse(await page.locator('#script-json').inputValue());
  assert.equal(authored.sourceLock[0].id, 'page-b', 'Validation retains the source lock for rendering');
  assert.match(await page.locator('#source-lock').textContent(), /page-b/);
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  await status(page, 'job-1');
  const render = state.requests.find(r => r.path === '/api/render');
  assert.deepEqual(render.body, { script: authored, voice: 'kokoro' });
  assert.equal(state.requests.some(r => r.path === '/api/draft'), false, 'Generate never invokes writer');
  for (const request of state.requests) { assert.equal(request.token, token); assert.equal(request.origin, origin); }
  state.jobs = [{ id: 'job-1', status: 'rendering', progress: 0.5 }];
  const pollsBefore = state.polls;
  await page.waitForFunction(() => document.querySelector('#jobs').textContent.includes('50%'), null, { timeout: 6000 });
  assert.ok(state.polls > pollsBefore, 'Jobs update by automatic polling');
  await page.getByLabel('Line 1 text', { exact: true }).fill('Keep my edit');
  state.jobs = [{ id: 'job-1', status: 'complete', progress: 1, video: '/output/job-1/video.mp4' }];
  await page.getByRole('button', { name: 'Refresh jobs', exact: true }).click();
  await page.locator('#jobs a').waitFor();
  assert.equal(await page.locator('#jobs a').getAttribute('href'), '/output/job-1/video.mp4');
  assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).lines[0].text, 'Keep my edit');
});

test('optional AI is explicit, handles missing configuration and rejects source swaps', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page);
  const value = script(); value.lines = [];
  await loadScript(page, value);
  assert.equal(state.requests.length, 0);
  await page.getByRole('button', { name: 'AI Draft', exact: true }).click();
  await status(page, 'not configured');
  assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).comics, ['page-a']);
  state.draft = 'swap';
  await page.getByRole('button', { name: 'AI Draft', exact: true }).click();
  await status(page, 'source|selected|swap');
  assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).comics, ['page-a']);
  state.draft = 'success';
  await page.getByRole('button', { name: 'AI Draft', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#script-json').value.includes('AI draft text'));
  assert.equal(await page.getByLabel('Line 1 text', { exact: true }).inputValue(), 'AI draft text');
  for (const request of state.requests) assert.equal(request.token, token);
});

test('late AI and random responses never replace edits made while a request is pending', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page); await loadScript(page);
  state.draft = 'success'; state.draftDelay = 450;
  await page.getByRole('button', { name: 'AI Draft', exact: true }).click();
  await page.locator('#title').fill('Edited while drafting');
  await status(page, 'changed|newer|edited');
  assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).title, 'Edited while drafting');
  assert.equal(await page.getByLabel('Line 1 text', { exact: true }).inputValue(), 'Reading page-a');
  state.selectDelay = 450;
  page.on('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Random sample', exact: true }).click();
  await page.locator('#script-json').fill('{ "new draft":');
  await status(page, 'changed|newer|edited');
  assert.equal(await page.locator('#script-json').inputValue(), '{ "new draft":');
});

test('server errors are actionable and preserve edits; recorded audio is an explicit choice', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page); await loadScript(page);
  state.validationError = 'Line 1: unsupported gesture. Use idle or talk.';
  await page.getByRole('button', { name: 'Validate', exact: true }).click();
  await status(page, 'unsupported gesture');
  assert.equal(await page.getByLabel('Line 1 text', { exact: true }).inputValue(), 'Reading page-a');
  state.jobsError = true;
  await page.getByRole('button', { name: 'Refresh jobs', exact: true }).click();
  await page.waitForFunction(() => /unavailable|retry/i.test(document.querySelector('#jobs-status').textContent));
  const value = script(); value.lines[0].audio = 'recordings/line.wav';
  await loadScript(page, value);
  await page.locator('#voice').selectOption('recorded');
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  await status(page, 'job-1');
  assert.equal(state.requests.at(-1).body.voice, 'recorded');
});

test('session failure blocks POSTs and retry recovers; phone layout fits without horizontal scrolling', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f;
  state.sessionError = true;
  await page.reload();
  await status(page, 'session|connect');
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  assert.equal(state.requests.length, 0);
  state.sessionError = false;
  await page.getByRole('button', { name: 'Retry connection', exact: true }).click();
  await ready(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await loadScript(page);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await page.getByLabel('Line 1 text', { exact: true }).fill('A phone edit');
  assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).lines[0].text, 'A phone edit');
});

test('resolved drafts retain locks through dialogue edits and clear them only on intentional reselection', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page); await loadScript(page);
  state.resolved = true; state.draft = 'success';
  await page.getByRole('button', { name: 'AI Draft', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#script-json').value.includes('AI draft text'));
  const drafted = JSON.parse(await page.locator('#script-json').inputValue());
  assert.equal(drafted.seed, 42);
  assert.equal(drafted.scene, 'library');
  assert.equal(drafted.sourceLock[0].id, 'page-a');
  assert.equal(drafted.cast, undefined);
  assert.equal(drafted.lines[0].id, undefined);
  assert.equal(drafted.lines[0].bookState, undefined);
  await page.getByLabel('Line 1 text', { exact: true }).fill('Edited with the same source');
  assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, drafted.sourceLock);
  page.on('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Random sample', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#selected-pages').textContent.includes('page-b'));
  const sampled = JSON.parse(await page.locator('#script-json').inputValue());
  assert.equal(sampled.sourceLock[0].id, 'page-b');
  assert.equal(sampled.lines[0].id, undefined);
  await page.getByRole('checkbox', { name: 'Select page-b', exact: true }).uncheck();
  await page.getByRole('checkbox', { name: 'Select page-a', exact: true }).check();
  assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, undefined);
  await page.getByLabel('Line 1 comic', { exact: true }).selectOption('page-a');
  await page.getByRole('button', { name: 'Validate', exact: true }).click();
  await status(page, 'validation passed');
  assert.deepEqual(state.requests.at(-1).body.script.comics, ['page-a']);
  assert.equal(state.requests.at(-1).body.script.sourceLock, undefined);
  assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock[0].id, 'page-a');
  await page.locator('#template').selectOption('page-tour');
  assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, undefined);
});

test('minimal public JSON inherits the current page; undeclared and unused pages prevent rendering', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page);
  const minimal = { template: 'book-duet', title: 'Minimal script', comics: ['page-a'], lines: [{ speaker: 'reader', text: 'Hello page.' }] };
  await loadScript(page, minimal);
  await page.getByRole('button', { name: 'Validate', exact: true }).click();
  await status(page, 'validation passed');
  assert.deepEqual(state.requests.at(-1).body.script, minimal);
  const count = state.requests.length;
  await loadScript(page, { ...minimal, comics: ['page-a', 'page-b'] });
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  await status(page, 'page-b.*line|page-b.*reference');
  await loadScript(page, { ...minimal, lines: [{ speaker: 'reader', text: 'Oops', comic: 'page-b' }] });
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  await status(page, 'unselected');
  assert.equal(state.requests.length, count);
});

test('dialogue reorder and remove controls mutate the same script submitted to rendering', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page);
  const value = script(); value.lines.push({ speaker: 'friend', text: 'Second line', comic: 'page-a', face: { eye_open: 0.7 } });
  await loadScript(page, value);
  await page.getByRole('button', { name: 'Move up line 2', exact: true }).click();
  assert.equal(await page.getByLabel('Line 1 text', { exact: true }).inputValue(), 'Second line');
  await page.getByRole('button', { name: 'Remove line 2', exact: true }).click();
  await page.getByRole('button', { name: 'Generate video', exact: true }).click();
  await status(page, 'job-1');
  assert.deepEqual(state.requests.at(-1).body.script.lines, [{ speaker: 'friend', text: 'Second line', comic: 'page-a', face: { eye_open: 0.7 } }]);
});

test('jobs display the real server text progress as literal text', async t => {
  const f = await fixture(t); if (!f) return;
  const { page, state } = f; await ready(page);
  state.jobs = [{ id: 'text-progress', status: 'rendering', progress: `Rendering frames 1–12 ${hostile}` }];
  await page.getByRole('button', { name: 'Refresh jobs', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#jobs').textContent.includes('Rendering frames 1–12'));
  assert.ok((await page.locator('#jobs').textContent()).includes(hostile));
  assert.equal(await page.locator('#jobs img').count(), 0);
  assert.equal(await page.evaluate(() => window.injected), undefined);
});

for (const method of ['upload', 'paste']) {
  test(`${method} preserves an incoming stale source lock in an empty editor and backend validation rejects it`, async t => {
    const f = await fixture(t); if (!f) return;
    const { page, state } = f; await ready(page);
    const saved = { ...script(['page-b']), title: 'Saved stale source', sourceLock: [{ id: 'page-b', sha256: '0'.repeat(64), pdfPage: 11, pdfSha256: 'a'.repeat(64) }] };
    if (method === 'upload') {
      await page.locator('#upload-json').setInputFiles({ name: 'saved.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(saved)) });
      await status(page, 'JSON uploaded');
    } else await loadScript(page, saved);
    assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, saved.sourceLock);
    await page.getByRole('button', { name: 'Validate', exact: true }).click();
    await status(page, 'Source lock changed');
    assert.deepEqual(state.requests.at(-1).body.script.sourceLock, saved.sourceLock);
    assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, saved.sourceLock, 'Failed validation must not rebind a stale saved script');
    await page.getByLabel('Line 1 text', { exact: true }).fill('Edited words, same source');
    assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, saved.sourceLock);
    await page.getByRole('checkbox', { name: 'Select page-b', exact: true }).uncheck();
    await page.getByRole('checkbox', { name: 'Select page-a', exact: true }).check();
    await page.getByLabel('Line 1 comic', { exact: true }).selectOption('page-a');
    assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, undefined, 'Explicit form reselection may clear the old lock');
    await page.getByRole('button', { name: 'Validate', exact: true }).click();
    await status(page, 'validation passed');
    assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock[0].id, 'page-a');
  });
}

test('AI draft allows the writer repair window, aborts at its own deadline, and leaves normal request deadlines short', async t => {
  const f = await fixture(t, { clock: true }); if (!f) return;
  const { page, state } = f; await ready(page); await loadScript(page);
  state.draft = 'success';
  state.hold('/api/draft');
  let sent = page.waitForRequest(request => request.url().endsWith('/api/draft'));
  await page.getByRole('button', { name: 'AI Draft', exact: true }).click(); await sent;
  await page.clock.fastForward(240000);
  assert.equal(await page.getByRole('button', { name: 'AI Draft', exact: true }).isDisabled(), true, 'Draft must remain pending through both 120-second writer attempts');
  state.release('/api/draft');
  await status(page, 'AI draft applied');
  state.hold('/api/draft');
  sent = page.waitForRequest(request => request.url().endsWith('/api/draft'));
  await page.getByRole('button', { name: 'AI Draft', exact: true }).click(); await sent;
  await page.clock.fastForward(250001);
  await status(page, 'timed out');
  assert.equal(await page.getByRole('button', { name: 'AI Draft', exact: true }).isDisabled(), false);
  assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).lines[0].text, 'AI draft text');
  state.release('/api/draft');
  state.hold('/api/validate');
  sent = page.waitForRequest(request => request.url().endsWith('/api/validate'));
  await page.getByRole('button', { name: 'Validate', exact: true }).click(); await sent;
  await page.clock.fastForward(120001);
  await status(page, 'timed out');
  state.release('/api/validate');
});

test('real server integration: source images, authenticated sample and validation, preserved and renewed locks', { skip: !process.env.THEATRE_GUI_REAL_SERVER }, async t => {
  if (!browser) { t.skip('Playwright browser unavailable'); return; }
  const { startServer } = await import('../src/server.mjs');
  const server = await startServer();
  const context = await browser.newContext();
  t.after(async () => { await context.close(); await server.close(); });
  const page = await context.newPage(); page.setDefaultTimeout(7000);
  await page.goto(server.url); await ready(page);
  await page.waitForFunction(() => [...document.querySelectorAll('#gallery img')].every(img => img.complete && img.naturalWidth > 0));
  await page.locator('#seed').fill('7');
  await page.getByRole('button', { name: 'Random sample', exact: true }).click();
  await status(page, 'sample ready');
  const sampled = JSON.parse(await page.locator('#script-json').inputValue());
  assert.equal(sampled.comics.length, 1);
  assert.equal(sampled.sourceLock[0].id, sampled.comics[0]);
  await page.getByLabel('Line 1 text', { exact: true }).fill('A short manually authored reading.');
  await page.getByRole('button', { name: 'Validate', exact: true }).click();
  await status(page, 'validation passed');
  assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, sampled.sourceLock);
  const boxes = page.locator('#gallery input[type="checkbox"]');
  const nextId = await boxes.evaluateAll((inputs, selected) => inputs.find(input => input.getAttribute('aria-label') !== `Select ${selected}`).getAttribute('aria-label').slice(7), sampled.comics[0]);
  await page.getByRole('checkbox', { name: `Select ${sampled.comics[0]}`, exact: true }).uncheck();
  await page.getByRole('checkbox', { name: `Select ${nextId}`, exact: true }).check();
  await page.getByLabel('Line 1 comic', { exact: true }).selectOption(nextId);
  assert.equal(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, undefined);
  await page.getByRole('button', { name: 'Validate', exact: true }).click();
  await status(page, 'validation passed');
  const validated = JSON.parse(await page.locator('#script-json').inputValue());
  assert.equal(validated.sourceLock[0].id, nextId);
  assert.notDeepEqual(validated.sourceLock, sampled.sourceLock);
  assert.ok((await page.locator('#source-lock').textContent()).includes(nextId));
  // A saved stale lock must reach the real validator unchanged, even when the
  // imported selection differs from a freshly loaded, empty editor.
  await page.reload(); await ready(page);
  const stale = structuredClone(validated); stale.sourceLock[0].sha256 = '0'.repeat(64);
  await page.locator('#upload-json').setInputFiles({ name: 'stale.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(stale)) });
  await status(page, 'JSON uploaded');
  const validationResponse = page.waitForResponse(response => response.url().endsWith('/api/validate'));
  await page.getByRole('button', { name: 'Validate', exact: true }).click();
  assert.equal((await validationResponse).status(), 400);
  await status(page, 'Source lock changed');
  assert.deepEqual(JSON.parse(await page.locator('#script-json').inputValue()).sourceLock, stale.sourceLock);
});
