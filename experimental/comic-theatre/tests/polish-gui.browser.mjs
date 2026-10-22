import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';

// Real browser inputs, downloads and fetches; only HTTP responses are fixtures.
// No writer, voice synthesis or render process is started by these tests.
const root = new URL('../', import.meta.url);
const defaults = { enabled: true, title: 'Goosnav Book Two', text: 'A book of comics.', url: 'www.goosnav.shop', seconds: 3 };
const catalog = {
  templates: [{ id: 'book-duet', label: 'Book duet', minComics: 1, maxComics: 1, speakers: ['reader', 'friend'], scenes: ['library'] }],
  scenes: [{ id: 'library', label: 'Library' }],
  variants: ['blue', 'rust', 'olive', 'blue-beady', 'rust-beady', 'olive-beady'].map(id => ({ id, label: `${id} clothes`, asset: `actor-${id}` })),
  edition: { title: 'Fixture edition' },
  comics: [{ id: 'page-a', title: 'Fixture page', verified: true, sha256: 'a'.repeat(64), pdfPage: 10 }],
};
const script = () => ({ template: 'book-duet', title: 'My reading', comics: ['page-a'], lines: [{ speaker: 'reader', text: 'A reading.', comic: 'page-a' }] });
const authored = () => ({
  ...script(), seed: 7, scene: 'library', product: 'book2',
  characters: { reader: 'olive', friend: 'blue', extra: { retained: true } },
  endCard: { ...defaults, enabled: false, title: 'My book', text: 'My words.', url: 'example.test/book', seconds: 4.5, extra: { retained: true } },
  sourceLock: [{ id: 'page-a', sha256: 'a'.repeat(64), pdfPage: 10, pdfSha256: 'b'.repeat(64) }],
  output: { width: 1080, height: 1350, fps: 24 }, extra: { retained: true },
  lines: [{ speaker: 'reader', text: 'A reading.', comic: 'page-a', face: { eye_open: 0.7 }, reaction: { actor: 'friend', emotion: 'curious' }, audio: 'recordings/line.wav', pause: 0.6, extra: { retained: true } }],
});
let browser;
before(async () => { browser = await chromium.launch({ headless: true, ...(process.env.THEATRE_TEST_CHROMIUM ? { executablePath: process.env.THEATRE_TEST_CHROMIUM } : {}) }); });
after(async () => { await browser?.close(); });

async function fixture(t, { legacy = false } = {}) {
  const state = { requests: [], writer: false, rewrite: false, resolve: false, error: '' };
  const held = new Map();
  state.hold = path => { let release; const promise = new Promise(resolve => { release = resolve; }); held.set(path, { promise, release }); };
  state.release = path => { held.get(path)?.release(); held.delete(path); };
  const json = (res, status, body) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body)); };
  const server = http.createServer(async (req, res) => {
    try {
      const path = new URL(req.url, 'http://localhost').pathname;
      if (req.method === 'POST') {
        let raw = ''; for await (const chunk of req) raw += chunk;
        const body = JSON.parse(raw); state.requests.push({ path, body });
        assert.equal(req.headers['x-theatre-token'], 'polish-test-token');
        if (held.has(path)) await held.get(path).promise;
        if (state.error) return json(res, 400, { error: state.error });
        if (path === '/api/render') return json(res, 200, { id: 'manual-render', status: 'queued' });
        if (path === '/api/select') return json(res, 200, { script: script() });
        let value = structuredClone(body.script);
        if (path === '/api/draft') {
          if (!state.writer) return json(res, 409, { error: 'Optional writer is not configured' });
          value.lines = [{ speaker: 'reader', text: 'Draft text.', comic: 'page-a' }];
          if (state.rewrite) {
            value.characters = { reader: 'blue', friend: 'rust' };
            value.endCard = { ...defaults };
            delete value.product;
          }
        }
        if (state.resolve) value = { ...value, product: value.product ?? 'book2', characters: { reader: 'blue', friend: 'rust', ...value.characters }, endCard: { ...defaults, ...value.endCard } };
        return json(res, 200, { script: value });
      }
      if (path === '/api/session') return json(res, 200, { token: 'polish-test-token' });
      if (path === '/api/catalog') { const value = structuredClone(catalog); if (legacy) delete value.variants; return json(res, 200, value); }
      if (path === '/api/jobs') return json(res, 200, { jobs: [] });
      const files = { '/': ['index.html', 'text/html'], '/app.mjs': ['app.mjs', 'text/javascript'], '/style.css': ['style.css', 'text/css'] };
      if (files[path]) { const [file, type] = files[path]; res.writeHead(200, { 'Content-Type': type }); return res.end(await readFile(new URL(`web/${file}`, root))); }
      res.writeHead(404); res.end('Not found');
    } catch (error) { json(res, 500, { error: error.message }); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage(); page.setDefaultTimeout(4000);
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => dialog.accept());
  t.after(async () => { for (const path of held.keys()) state.release(path); await context.close(); await new Promise(resolve => server.close(resolve)); assert.deepEqual(errors, []); });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await status(page, 'Ready');
  return { page, state };
}
const current = async page => JSON.parse(await page.locator('#script-json').inputValue());
const status = async (page, pattern) => page.waitForFunction(pattern => new RegExp(pattern, 'i').test(document.querySelector('#editor-status').textContent), pattern);
async function load(page, value) {
  await page.locator('#script-json').fill(JSON.stringify(value));
  await page.getByRole('button', { name: 'Apply JSON', exact: true }).click();
  await status(page, 'JSON applied');
}
async function download(page) {
  const event = page.waitForEvent('download'); await page.locator('#download-json').click();
  const stream = await (await event).createReadStream(); const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks));
}

for (const legacy of [false, true]) test(`clothing and Book Two defaults display without rewriting old scripts (legacy catalog: ${legacy})`, async t => {
  const { page, state } = await fixture(t, { legacy });
  const value = script(); await load(page, value);
  assert.equal(await page.getByLabel('Reader clothing', { exact: true }).inputValue(), 'blue');
  assert.equal(await page.getByLabel('Friend clothing', { exact: true }).inputValue(), 'rust');
  assert.deepEqual(await page.locator('#reader-clothing option').evaluateAll(nodes => nodes.map(node => node.value)), legacy ? ['blue', 'rust', 'olive'] : catalog.variants.map(v => v.id));
  if (!legacy) assert.equal(await page.locator('#reader-clothing option').first().textContent(), 'blue clothes');
  assert.equal(await page.locator('#product').inputValue(), 'book2');
  assert.equal(await page.locator('#product option').count(), 1);
  assert.equal(await page.getByLabel('Show end card', { exact: true }).isChecked(), true);
  for (const key of ['title', 'text', 'url', 'seconds']) assert.equal(await page.locator(`#end-card-${key}`).inputValue(), String(defaults[key]));
  assert.equal(await page.getByLabel('Line 1 shot', { exact: true }).inputValue(), 'auto');
  assert.deepEqual(await download(page), value);
  await page.locator('#validate').click(); await status(page, 'validation passed');
  assert.deepEqual(state.requests.at(-1).body.script, value);
});

test('real form input, every shot, upload and download preserve advanced fields and source locks', async t => {
  const { page } = await fixture(t); const value = authored(); await load(page, value);
  await page.getByLabel('Reader clothing', { exact: true }).selectOption('rust-beady');
  await page.getByLabel('Friend clothing', { exact: true }).selectOption('olive');
  await page.getByLabel('Show end card', { exact: true }).check();
  const text = { title: 'A custom title', text: 'A custom closing line.', url: 'www.goosnav.shop/custom', seconds: 5.5 };
  for (const [key, val] of Object.entries(text)) await page.locator(`#end-card-${key}`).fill(String(val));
  for (const shot of ['auto', 'speaker', 'two-shot', 'over-shoulder', 'book', 'source']) {
    await page.getByLabel('Line 1 shot', { exact: true }).selectOption(shot);
    assert.equal((await current(page)).lines[0].shot, shot);
  }
  const expected = { ...value, characters: { ...value.characters, reader: 'rust-beady', friend: 'olive' }, endCard: { ...value.endCard, ...text, enabled: true }, lines: [{ ...value.lines[0], shot: 'source' }] };
  assert.deepEqual(await current(page), expected);
  assert.deepEqual(await download(page), expected);
  await page.locator('#upload-json').setInputFiles({ name: 'saved.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(expected)) });
  await status(page, 'JSON uploaded');
  assert.deepEqual(await current(page), expected);
  assert.equal(await page.locator('#end-card-text').inputValue(), text.text);
  assert.equal(await page.getByLabel('Line 1 shot', { exact: true }).inputValue(), 'source');
  await page.getByLabel('Show end card', { exact: true }).uncheck();
  assert.deepEqual((await current(page)).endCard, { ...expected.endCard, enabled: false });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
});

test('partial authored objects retain omitted defaults; validation records resolved fields', async t => {
  const { page, state } = await fixture(t);
  const value = { ...script(), characters: { reader: 'olive' }, endCard: { text: '' } };
  await load(page, value);
  assert.equal(await page.locator('#end-card-text').inputValue(), '');
  assert.equal(await page.locator('#end-card-title').inputValue(), defaults.title);
  await page.locator('#end-card-title').fill('Chosen title');
  assert.deepEqual((await current(page)).endCard, { text: '', title: 'Chosen title' });
  state.resolve = true;
  await page.locator('#validate').click(); await status(page, 'validation passed');
  const resolved = await current(page);
  assert.deepEqual(resolved.characters, { reader: 'olive', friend: 'rust' });
  assert.deepEqual(resolved.endCard, { ...defaults, title: 'Chosen title', text: '' });
  assert.equal(resolved.product, 'book2');
});

test('draft preserves authored clothing/product/end card; unavailable writer still allows local manual render', async t => {
  const { page, state } = await fixture(t); const value = authored(); await load(page, value);
  await page.locator('#draft').click(); await status(page, 'not configured');
  assert.deepEqual(state.requests.at(-1).body.script, value);
  assert.deepEqual(await current(page), value);
  await page.locator('#generate').click(); await status(page, 'manual-render');
  assert.deepEqual(state.requests.at(-1), { path: '/api/render', body: { script: value, voice: 'kokoro' } });
  state.writer = true; state.rewrite = true;
  await page.locator('#draft').click(); await status(page, 'AI draft applied');
  const drafted = await current(page);
  for (const key of ['characters', 'product', 'endCard', 'sourceLock']) assert.deepEqual(drafted[key], value[key]);
  assert.equal(drafted.lines[0].text, 'Draft text.');
});

test('invalid input blocks POSTs and unapplied JSON pauses every new control', async t => {
  const { page, state } = await fixture(t); await load(page, authored());
  await page.locator('#end-card-seconds').fill('0');
  for (const id of ['generate', 'validate', 'draft']) { await page.locator(`#${id}`).click(); await status(page, 'seconds'); }
  assert.equal(state.requests.length, 0);
  await page.locator('#end-card-seconds').fill('');
  await page.locator('#generate').click(); await status(page, 'seconds');
  assert.equal(state.requests.length, 0);
  const invalid = [
    { characters: null }, { characters: { reader: 'hat' } }, { product: 'book3' },
    { endCard: [] }, { endCard: { enabled: 'false' } }, { endCard: { text: 2 } }, { endCard: { seconds: -1 } },
    { lines: [{ speaker: 'reader', text: 'Hello', shot: 'unknown' }] },
  ];
  for (const patch of invalid) {
    const raw = JSON.stringify({ ...script(), ...patch });
    await page.locator('#script-json').fill(raw); await page.locator('#apply-json').click(); await status(page, 'JSON not applied');
    for (const id of ['reader-clothing', 'friend-clothing', 'product', 'end-card-enabled', 'end-card-title', 'end-card-text', 'end-card-url', 'end-card-seconds', 'line-0-shot']) assert.equal(await page.locator(`#${id}`).isDisabled(), true);
    await page.locator('#generate').click(); await status(page, 'Apply JSON');
    assert.equal(await page.locator('#script-json').inputValue(), raw);
  }
  assert.equal(state.requests.length, 0);
});

for (const endpoint of ['draft', 'validate', 'select']) test(`${endpoint} cannot overwrite clothing, end-card or shot edits made while pending`, async t => {
  const { page, state } = await fixture(t); await load(page, authored()); state.writer = true;
  const path = `/api/${endpoint}`; state.hold(path);
  const sent = page.waitForRequest(request => request.url().endsWith(path));
  await page.locator(endpoint === 'select' ? '#random' : `#${endpoint}`).click(); await sent;
  await page.locator('#reader-clothing').selectOption('rust');
  await page.locator('#end-card-text').fill('Keep this newer ending.');
  await page.getByLabel('Line 1 shot', { exact: true }).selectOption('over-shoulder');
  const edited = await current(page);
  state.release(path); await status(page, 'editor changed');
  assert.deepEqual(await current(page), edited);
  assert.equal(state.requests.length, 1);
});

test('source reselection and random samples keep authored presentation settings', async t => {
  const { page, state } = await fixture(t); const value = authored(); await load(page, value);
  await page.getByRole('checkbox', { name: 'Select page-a', exact: true }).uncheck();
  await page.getByRole('checkbox', { name: 'Select page-a', exact: true }).check();
  assert.equal((await current(page)).sourceLock, undefined);
  await page.locator('#random').click(); await status(page, 'sample ready');
  const sampled = await current(page);
  for (const key of ['characters', 'product', 'endCard']) assert.deepEqual(sampled[key], value[key]);
  assert.equal(sampled.sourceLock, undefined);
  state.error = 'Source lock changed. Re-select and review the source.';
  await load(page, value); await page.locator('#validate').click(); await status(page, 'Source lock changed');
  assert.deepEqual(await current(page), value);
});

test('real server integration: new controls validate with the public contract and preserve source locks', { skip: !process.env.THEATRE_GUI_REAL_SERVER }, async t => {
  const { startServer } = await import('../src/server.mjs');
  const server = await startServer(); const context = await browser.newContext();
  t.after(async () => { await context.close(); await server.close(); });
  const page = await context.newPage(); page.setDefaultTimeout(7000);
  await page.goto(server.url); await status(page, 'Ready');
  await page.locator('#random').click(); await status(page, 'sample ready');
  const lock = (await current(page)).sourceLock;
  await page.locator('#reader-clothing').selectOption('olive');
  await page.locator('#friend-clothing').selectOption('blue');
  await page.locator('#end-card-enabled').uncheck();
  await page.locator('#end-card-title').fill('An authored ending');
  await page.locator('#end-card-text').fill('My closing words.');
  await page.locator('#end-card-url').fill('www.goosnav.shop');
  await page.locator('#end-card-seconds').fill('4.25');
  await page.getByLabel('Line 1 shot', { exact: true }).selectOption('over-shoulder');
  const response = page.waitForResponse(response => response.url().endsWith('/api/validate'));
  await page.locator('#validate').click(); assert.equal((await response).status(), 200);
  await status(page, 'validation passed');
  const saved = await current(page);
  assert.deepEqual(saved.characters, { reader: 'olive', friend: 'blue' });
  assert.deepEqual(saved.endCard, { enabled: false, title: 'An authored ending', text: 'My closing words.', url: 'www.goosnav.shop', seconds: 4.25 });
  assert.equal(saved.product, 'book2'); assert.equal(saved.lines[0].shot, 'over-shoulder');
  assert.deepEqual(saved.sourceLock, lock);
  // Bounds are owned by the main contract, not duplicated in this GUI slice.
  await page.locator('#end-card-seconds').fill('1000');
  const rejected = page.waitForResponse(response => response.url().endsWith('/api/validate'));
  await page.locator('#validate').click(); assert.equal((await rejected).status(), 400);
  await status(page, 'seconds');
  assert.deepEqual(await current(page), { ...saved, endCard: { ...saved.endCard, seconds: 1000 } });
});
