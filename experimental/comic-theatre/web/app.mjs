const $ = id => document.getElementById(id);
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const state = { catalog: null, script: null, token: null, dirtyJSON: false, revision: 0, busy: false, connecting: false, polling: false };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const clone = value => structuredClone(value);
const stringify = value => JSON.stringify(value, null, 2);
const templates = () => state.catalog?.templates ?? [];
const templateFor = script => templates().find(item => item.id === script.template);
const comicFor = id => state.catalog?.comics.find(item => item.id === id);
const characterDefaults = { reader: 'blue', friend: 'rust' };
const endCardDefaults = { enabled: true, title: 'Goosnav Book Two', text: 'A book of comics.', url: 'www.goosnav.shop', seconds: 3 };
const variants = () => state.catalog?.variants ?? ['blue', 'rust', 'olive'].map(id => ({ id, label: id[0].toUpperCase() + id.slice(1) }));
const shots = [
  { id: 'auto', label: 'Auto' }, { id: 'speaker', label: 'Speaker' },
  { id: 'two-shot', label: 'Two-shot' }, { id: 'over-shoulder', label: 'Over-shoulder' },
  { id: 'book', label: 'Book' }, { id: 'source', label: 'Source' },
];

// A new sample or writer changes pages/dialogue, not the author's presentation.
// Keep server-resolved defaults for omitted fields and preserve advanced keys.
function keepPresentation(result, original) {
  const next = clone(result);
  for (const key of ['characters', 'endCard']) {
    if (original[key] !== undefined) next[key] = { ...(object(next[key]) ? next[key] : {}), ...clone(original[key]) };
  }
  if (original.product !== undefined) next.product = original.product;
  return next;
}

function message(text, error = false) {
  $('editor-status').textContent = text;
  $('editor-status').classList.toggle('error', error);
}
function controls() {
  const paused = !state.script || state.dirtyJSON;
  $('source-fields').disabled = paused;
  $('author-fields').disabled = paused;
  $('script-json').disabled = !state.script;
  $('json-state').textContent = state.dirtyJSON ? 'Unapplied edits · form paused' : 'In sync';
  for (const button of document.querySelectorAll('[data-post]')) button.disabled = state.busy;
}
function requireReady() {
  if (!state.token || !state.catalog || !state.script) throw new Error('Connect to the local theatre first. Use Retry connection.');
  if (state.dirtyJSON) throw new Error('Apply JSON or Revert JSON before continuing. Your unapplied edits have been kept.');
}
function syncJSON() { $('script-json').value = stringify(state.script); state.dirtyJSON = false; controls(); }
function changed() { state.revision++; syncJSON(); renderSelection(); }

// Asset and output links must remain under their local allowlisted route. Never
// assign catalog/job strings directly as a URL (including protocol-relative URLs).
function localPath(value, prefix) {
  if (typeof value !== 'string') return null;
  try {
    const path = decodeURIComponent(value.startsWith('/') ? value : `/${value}`);
    if (!path.startsWith(prefix) || /[\\\u0000-\u001f\u007f?#]/.test(path)) return null;
    const parts = path.split('/');
    if (parts.slice(1).some(part => !part || part === '.' || part === '..')) return null;
    return parts.map(encodeURIComponent).join('/');
  } catch { return null; }
}

async function api(path, body, { timeoutMs = body ? 120000 : 15000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    if (body && !state.token) throw new Error('Session token unavailable. Use Retry connection.');
    const response = await fetch(path, {
      method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      headers: body ? { 'Content-Type': 'application/json', 'X-Theatre-Token': state.token } : {},
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    let data;
    try { data = await response.json(); } catch { throw new Error(`Server returned non-JSON data (${response.status}). Check the local server and retry.`); }
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) $('retry').hidden = false;
      throw new Error(typeof data?.error === 'string' ? data.error : `Request failed (${response.status}).`);
    }
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Request timed out. Check the server; refresh jobs before resubmitting a render.');
    if (error instanceof TypeError) throw new Error('Cannot reach the local server. Check that it is running and retry.');
    throw error;
  } finally { clearTimeout(timer); }
}

function structureErrors(script) {
  const errors = [];
  if (!object(script)) return ['The script must be a JSON object.'];
  if (script.version !== undefined && script.version !== 1) errors.push('Use script version 1.');
  if (!templateFor(script)) errors.push('Choose a template from the catalog.');
  if (typeof script.title !== 'string') errors.push('title must be text.');
  if (script.seed !== undefined && !Number.isSafeInteger(script.seed)) errors.push('Seed must be a safe integer or omitted.');
  if (script.scene !== undefined && !state.catalog.scenes.some(item => item.id === script.scene)) errors.push('Choose a scene from the catalog or omit scene.');
  // These are form shape checks. The server contract owns text limits and all
  // production validation; unknown advanced fields remain intact for that check.
  if (script.product !== undefined && script.product !== 'book2') errors.push('product must be book2 or omitted.');
  if (script.characters !== undefined) {
    if (!object(script.characters)) errors.push('characters must be an object.');
    else for (const role of ['reader', 'friend']) {
      if (script.characters[role] !== undefined && !variants().some(item => item.id === script.characters[role])) errors.push(`characters.${role} must be a clothing variant from the catalog.`);
    }
  }
  if (script.endCard !== undefined) {
    if (!object(script.endCard)) errors.push('endCard must be an object.');
    else {
      if (script.endCard.enabled !== undefined && typeof script.endCard.enabled !== 'boolean') errors.push('endCard.enabled must be true or false.');
      for (const key of ['title', 'text', 'url']) if (script.endCard[key] !== undefined && typeof script.endCard[key] !== 'string') errors.push(`endCard.${key} must be text.`);
      if (script.endCard.seconds !== undefined && (typeof script.endCard.seconds !== 'number' || !Number.isFinite(script.endCard.seconds) || script.endCard.seconds <= 0)) errors.push('endCard.seconds must be a positive number.');
    }
  }
  if (!Array.isArray(script.comics)) errors.push('comics must be an array of catalog page IDs.');
  else {
    if (new Set(script.comics).size !== script.comics.length) errors.push('Selected page IDs must be unique.');
    for (const id of script.comics) if (typeof id !== 'string' || !comicFor(id)) errors.push(`Unknown catalog page: ${String(id)}.`);
  }
  if (!Array.isArray(script.lines)) errors.push('lines must be an array.');
  else script.lines.forEach((line, index) => {
    const at = `Line ${index + 1}: `;
    if (!object(line)) { errors.push(`${at}use a dialogue or action object.`); return; }
    if (line.action !== undefined) {
      if (!['open', 'turn', 'hold', 'read', 'place', 'close', 'slam'].includes(line.action)) errors.push(`${at}unknown book action.`);
      if (line.speaker !== undefined || line.text !== undefined) errors.push(`${at}an action cannot also be dialogue.`);
      if (line.seconds !== undefined && (typeof line.seconds !== 'number' || !Number.isFinite(line.seconds) || line.seconds <= 0)) errors.push(`${at}seconds must be positive.`);
    } else {
      if (!['reader', 'friend'].includes(line.speaker)) errors.push(`${at}speaker must be reader or friend.`);
      if (typeof line.text !== 'string') errors.push(`${at}text must be a string.`);
      for (const key of ['emotion', 'gesture', 'audio']) if (line[key] !== undefined && typeof line[key] !== 'string') errors.push(`${at}${key} must be text.`);
      for (const key of ['face', 'reaction']) if (line[key] !== undefined && !object(line[key])) errors.push(`${at}${key} must be a JSON object.`);
      if (line.pause !== undefined && (typeof line.pause !== 'number' || !Number.isFinite(line.pause) || line.pause < 0)) errors.push(`${at}pause must be a nonnegative number.`);
      if (line.shot !== undefined && !shots.some(item => item.id === line.shot)) errors.push(`${at}shot must be ${shots.map(item => item.id).join(', ')}.`);
    }
    if (line.comic !== undefined && (typeof line.comic !== 'string' || !comicFor(line.comic))) errors.push(`${at}comic must be a known catalog ID.`);
  });
  if (script.output !== undefined) {
    if (!object(script.output)) errors.push('output must be an object.');
    else for (const key of ['width', 'height', 'fps']) if (script.output[key] !== undefined && (!Number.isInteger(script.output[key]) || script.output[key] <= 0)) errors.push(`output.${key} must be a positive integer.`);
  }
  if (script.sourceLock !== undefined && (!Array.isArray(script.sourceLock) || script.sourceLock.some(lock => !object(lock)))) errors.push('sourceLock must be an array of source records returned by the server.');
  return errors;
}
function selectionErrors(script) {
  const template = templateFor(script);
  const errors = [];
  if (!template) return ['Choose a catalog template.'];
  const count = script.comics.length;
  if (count < template.minComics || count > template.maxComics) errors.push(`${template.id} needs ${template.minComics === template.maxComics ? template.minComics : `${template.minComics}–${template.maxComics}`} selected page(s); you have ${count}. Adjust the selection explicitly.`);
  for (const id of script.comics) if (comicFor(id)?.verified !== true) errors.push(`Page ${id} is not verified. Select a reviewed source page.`);
  if (script.scene && !template.scenes.includes(script.scene)) errors.push(`Scene ${script.scene} is unavailable for ${template.id}. Choose ${template.scenes.join(' or ')} or Template default.`);
  return errors;
}
function usedPages(script) {
  let current = script.comics[0];
  const used = new Set();
  for (const line of script.lines) {
    if (line.comic !== undefined) current = line.comic;
    if (!line.action && current) used.add(current);
  }
  return used;
}
function completeErrors(script) {
  const structural = structureErrors(script);
  if (structural.length) return structural;
  const errors = selectionErrors(script);
  if (!script.title.trim()) errors.push('Give the film a title.');
  if (!script.lines.length) errors.push('Add dialogue or book actions before generating.');
  const template = templateFor(script);
  script.lines.forEach((line, index) => {
    if (line.comic !== undefined && !script.comics.includes(line.comic)) errors.push(`Line ${index + 1} references unselected page ${line.comic}. Select that page or edit the reference.`);
    if (!line.action) {
      if (!line.text.trim()) errors.push(`Line ${index + 1} needs spoken text.`);
      if (!template?.speakers.includes(line.speaker)) errors.push(`Line ${index + 1}: ${line.speaker} is not in this template. Choose ${template?.speakers.join(' or ')}.`);
    }
  });
  const used = usedPages(script);
  for (const id of script.comics) if (!used.has(id)) errors.push(`Selected page ${id} needs a dialogue line referencing that comic ID.`);
  return errors;
}
function check(errors) { if (errors.length) throw new Error(errors.join('\n')); }
function option(select, value, text) { const node = el('option', text); node.value = value; select.append(node); }
function choose(select, choices, value, blank) {
  select.replaceChildren();
  if (blank !== undefined) option(select, '', blank);
  for (const item of choices) option(select, item.id ?? item, item.label ?? item);
  if (value && ![...select.options].some(item => item.value === value)) option(select, value, `${value} (not available here)`);
  select.value = value ?? '';
}

function renderGallery() {
  $('edition').textContent = state.catalog.edition?.title ?? 'Local source catalog';
  $('gallery').replaceChildren();
  if (!state.catalog.comics.length) $('gallery').append(el('p', 'No source pages in this catalog. Ask the server operator to add reviewed assets.', 'muted'));
  for (const comic of state.catalog.comics) {
    const card = el('article', undefined, 'comic');
    card.dataset.comicId = comic.id;
    const path = localPath(comic.path, '/assets/');
    if (path) {
      const link = el('a'); link.href = path; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.setAttribute('aria-label', `View source page ${comic.id}`);
      const img = el('img'); img.src = path; img.alt = `Source page ${comic.id}: ${comic.title}`; img.loading = 'lazy';
      img.addEventListener('error', () => { img.hidden = true; link.textContent = `Image unavailable for ${comic.id}. Open source or check catalog assets.`; }, { once: true });
      link.append(img); card.append(link);
    } else card.append(el('p', 'Source image path is unavailable. Check the local catalog.', 'hint'));
    const label = el('label');
    const checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.setAttribute('aria-label', `Select ${comic.id}`); checkbox.disabled = comic.verified !== true;
    checkbox.addEventListener('change', () => {
      delete state.script.sourceLock;
      if (checkbox.checked) state.script.comics.push(comic.id);
      else state.script.comics = state.script.comics.filter(id => id !== comic.id);
      changed(); renderLines();
    });
    label.append(checkbox, el('span', comic.title)); card.append(label);
    card.append(el('p', `${comic.id} · PDF page ${comic.pdfPage ?? 'unknown'} · Printed page ${comic.printedPage ?? 'not supplied'}`, 'page-meta'));
    if (comic.verified === true) card.append(el('p', 'Catalog-reviewed source', 'page-meta'));
    if (comic.verified !== true) card.append(el('p', 'Unreviewed source — selection unavailable.', 'hint'));
    const details = el('details'); details.append(el('summary', 'Read transcript'));
    details.append(el('p', Array.isArray(comic.transcript) ? comic.transcript.join('\n\n') : comic.transcript || 'No transcript supplied.', 'transcript'));
    if (comic.observations) details.append(el('p', `Source notes: ${comic.observations}`, 'transcript'));
    card.append(details); $('gallery').append(card);
  }
}
function renderSelection() {
  if (!state.script) return;
  const selected = $('selected-pages'); selected.replaceChildren();
  if (!state.script.comics.length) selected.textContent = 'No pages selected. Choose thumbnails or request a random sample.';
  else {
    const list = el('ol');
    for (const id of state.script.comics) {
      const comic = comicFor(id);
      const item = el('li'); item.append(el('strong', id), document.createTextNode(` · ${comic?.title ?? 'Unknown page'} · PDF ${comic?.pdfPage ?? '?'} / printed ${comic?.printedPage ?? '?'}`)); list.append(item);
    }
    selected.append(list);
  }
  const errors = selectionErrors(state.script);
  $('selection-help').textContent = errors.length ? errors.join(' ') : 'Selection ready. These IDs will be sent to drafting and rendering.';
  const lockBox = $('source-lock'); lockBox.replaceChildren();
  if (state.script.sourceLock?.length) {
    const details = el('details'); details.append(el('summary', `Recorded source lock · ${state.script.sourceLock.length} page(s)`));
    for (const lock of state.script.sourceLock) details.append(el('p', `${lock.id} · PDF page ${lock.pdfPage}\nPage SHA-256: ${lock.sha256}\nPDF SHA-256: ${lock.pdfSha256}`));
    details.append(el('p', 'Dialogue edits and JSON imports preserve this lock. Changing pages or template in the form clears it; Validate records the new lock.'));
    lockBox.append(details);
  } else lockBox.textContent = 'No source lock yet. Validate records the selected pages and their hashes.';
  for (const card of $('gallery').children) {
    const checkbox = card.querySelector('input');
    if (checkbox) { checkbox.checked = state.script.comics.includes(card.dataset.comicId); card.classList.toggle('is-selected', checkbox.checked); }
  }
}
function field(labelText, input) {
  const box = el('div'); const label = el('label', labelText); label.htmlFor = input.id; box.append(label, input); return box;
}
function lineInput(index, key, multiline = false) {
  const input = el(multiline ? 'textarea' : 'input'); input.id = `line-${index}-${key}`;
  input.setAttribute('aria-label', `Line ${index + 1} ${key}`);
  if (multiline) input.rows = 3;
  input.value = state.script.lines[index][key] ?? '';
  input.addEventListener('input', () => {
    if (input.value || key === 'text') state.script.lines[index][key] = input.value;
    else delete state.script.lines[index][key];
    changed();
  });
  return field(key[0].toUpperCase() + key.slice(1), input);
}
function renderLines() {
  $('dialogue').replaceChildren();
  if (!state.script.lines.length) $('dialogue').append(el('p', 'Start with a line of dialogue, or request an optional AI draft after choosing pages.', 'muted'));
  state.script.lines.forEach((line, index) => {
    const card = el('section', undefined, 'line');
    const heading = el('div', undefined, 'line-heading'); heading.append(el('h4', `Line ${index + 1}${line.action ? ' · Book action' : ''}`));
    const actions = el('div', undefined, 'line-actions');
    for (const [label, delta] of [['Move up', -1], ['Move down', 1], ['Remove', 0]]) {
      const button = el('button', label); button.type = 'button'; button.setAttribute('aria-label', `${label} line ${index + 1}`);
      button.disabled = delta === -1 && index === 0 || delta === 1 && index === state.script.lines.length - 1;
      button.addEventListener('click', () => {
        if (!delta) state.script.lines.splice(index, 1);
        else [state.script.lines[index], state.script.lines[index + delta]] = [state.script.lines[index + delta], state.script.lines[index]];
        changed(); renderLines();
      }); actions.append(button);
    }
    heading.append(actions); card.append(heading);
    if (line.action) {
      card.append(el('p', stringify(line), 'action-summary'), el('p', 'Edit this book action in JSON. Server validation checks book-state order.', 'hint'));
    } else {
      const pair = el('div', undefined, 'field-pair');
      const speaker = el('select'); speaker.id = `line-${index}-speaker`; speaker.setAttribute('aria-label', `Line ${index + 1} speaker`);
      choose(speaker, templateFor(state.script)?.speakers ?? ['reader', 'friend'], line.speaker);
      speaker.addEventListener('change', () => { line.speaker = speaker.value; changed(); });
      const source = el('select'); source.id = `line-${index}-comic`; source.setAttribute('aria-label', `Line ${index + 1} comic`);
      choose(source, state.script.comics.map(id => ({ id, label: `${id} · printed ${comicFor(id)?.printedPage ?? '?'}` })), line.comic, 'Continue current page');
      source.addEventListener('change', () => { if (source.value) line.comic = source.value; else delete line.comic; changed(); });
      pair.append(field('Speaker', speaker), field('Source page', source)); card.append(pair, lineInput(index, 'text', true));
      const performance = el('div', undefined, 'field-pair'); performance.append(lineInput(index, 'emotion'), lineInput(index, 'gesture')); card.append(performance);
      const shot = el('select'); shot.id = `line-${index}-shot`; shot.setAttribute('aria-label', `Line ${index + 1} shot`);
      choose(shot, shots, line.shot ?? 'auto');
      shot.addEventListener('change', () => { line.shot = shot.value; changed(); });
      card.append(field('Shot', shot));
      if (['face', 'reaction', 'pause', 'audio'].some(key => line[key] !== undefined)) card.append(el('p', 'Advanced fields present; edit them in JSON. Form edits preserve them.', 'hint'));
    }
    $('dialogue').append(card);
  });
}
function renderForm() {
  choose($('template'), templates().map(item => ({ id: item.id, label: `${item.id} · ${item.label}` })), state.script.template);
  choose($('scene'), state.catalog.scenes, state.script.scene, 'Template default');
  $('seed').value = state.script.seed ?? '';
  $('title').value = state.script.title;
  for (const role of ['reader', 'friend']) choose($(`${role}-clothing`), variants(), state.script.characters?.[role] ?? characterDefaults[role]);
  $('product').value = state.script.product ?? 'book2';
  const endCard = { ...endCardDefaults, ...state.script.endCard };
  $('end-card-enabled').checked = endCard.enabled;
  for (const key of ['title', 'text', 'url', 'seconds']) $(`end-card-${key}`).value = endCard[key];
  const template = templateFor(state.script);
  $('template-help').textContent = template ? `${template.minComics === template.maxComics ? template.minComics : `${template.minComics}–${template.maxComics}`} page(s) · cast: ${template.speakers.join(', ')}. Changing templates keeps your pages and dialogue; adjust any incompatibilities explicitly.` : 'Choose a catalog template.';
  renderSelection(); renderLines(); controls();
}
function install(script) {
  check(structureErrors(script));
  const next = clone(script);
  // Cast and timeline IDs are template/engine details. Keep sourceLock so ordinary
  // dialogue editing cannot silently rebind the source to a different asset hash.
  delete next.cast;
  for (const line of next.lines) { delete line.id; delete line.bookState; }
  // An incoming lock belongs to the imported script, not the current selection.
  // Preserve even stale locks for backend rejection. Only explicit selection
  // controls (or an author's removal in JSON) may discard a previous source lock.
  state.script = next; state.revision++; syncJSON(); renderForm();
}
function unchanged(revision) {
  if (revision !== state.revision) throw new Error('The editor changed while the request was running. The response was not applied. Your newer edits are safe; retry when ready.');
}

async function operate(kind, work) {
  if (state.busy) return;
  try {
    requireReady(); state.busy = true; controls(); message(`${kind}…`);
    await work();
  } catch (error) { message(`${kind}: ${error.message}`, true); }
  finally { state.busy = false; controls(); }
}

$('template').addEventListener('change', () => { state.script.template = $('template').value; delete state.script.sourceLock; changed(); renderForm(); });
$('scene').addEventListener('change', () => { if ($('scene').value) state.script.scene = $('scene').value; else delete state.script.scene; changed(); });
$('seed').addEventListener('input', () => { if ($('seed').value === '') delete state.script.seed; else state.script.seed = Number($('seed').value); changed(); });
$('title').addEventListener('input', () => { state.script.title = $('title').value; changed(); });
for (const role of ['reader', 'friend']) $(`${role}-clothing`).addEventListener('change', () => {
  state.script.characters = { ...state.script.characters, [role]: $(`${role}-clothing`).value }; changed();
});
$('product').addEventListener('change', () => { state.script.product = $('product').value; changed(); });
$('end-card-enabled').addEventListener('change', () => {
  state.script.endCard = { ...state.script.endCard, enabled: $('end-card-enabled').checked }; changed();
});
for (const key of ['title', 'text', 'url', 'seconds']) $(`end-card-${key}`).addEventListener('input', () => {
  const input = $(`end-card-${key}`);
  // A cleared/invalid number stays invalid until corrected; never restore a
  // default silently or serialize NaN as a valid duration.
  const value = key === 'seconds' ? (Number.isFinite(input.valueAsNumber) ? input.valueAsNumber : null) : input.value;
  state.script.endCard = { ...state.script.endCard, [key]: value }; changed();
});
$('add-line').addEventListener('click', () => {
  const comic = state.script.comics.find(id => !state.script.lines.some(line => line.comic === id)) ?? state.script.comics[0];
  state.script.lines.push({ speaker: templateFor(state.script)?.speakers[0] ?? 'reader', text: '', ...(comic ? { comic } : {}) });
  changed(); renderLines(); $(`line-${state.script.lines.length - 1}-text`).focus();
});
$('script-json').addEventListener('input', () => { state.revision++; state.dirtyJSON = true; controls(); });
$('apply-json').addEventListener('click', () => {
  try { if (!state.catalog) throw new Error('Connect to the local theatre first.'); install(JSON.parse($('script-json').value)); message('JSON applied. Form and JSON are in sync. Validate before generating.'); }
  catch (error) { message(`JSON not applied: ${error.message}`, true); }
});
$('revert-json').addEventListener('click', () => { if (state.script) { state.revision++; syncJSON(); message('Unapplied JSON reverted to the current form script.'); } });
$('download-json').addEventListener('click', () => {
  try {
    requireReady();
    const url = URL.createObjectURL(new Blob([`${stringify(state.script)}\n`], { type: 'application/json' }));
    const link = el('a'); link.href = url; link.download = 'comic-theatre-script.json'; document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000); message('Script downloaded.');
  } catch (error) { message(error.message, true); }
});
$('upload-json').addEventListener('change', async () => {
  const file = $('upload-json').files[0]; if (!file) return;
  try {
    requireReady();
    if (file.size > 2 * 1024 * 1024) throw new Error('Choose a script JSON file smaller than 2 MB.');
    const revision = state.revision; const script = JSON.parse(await file.text()); unchanged(revision); install(script);
    message('JSON uploaded. Review selected pages, then validate the script.');
  } catch (error) { message(`Upload not applied: ${error.message}`, true); }
  finally { $('upload-json').value = ''; }
});
$('random').addEventListener('click', () => operate('Random sample', async () => {
  if (state.script.lines.length && !window.confirm('Replace the current selected pages and dialogue with a random sample? Download JSON first if you want to keep this script.')) { message('Random sample cancelled. Your script is unchanged.'); return; }
  check(structureErrors(state.script));
  const revision = state.revision;
  const original = clone(state.script);
  const request = { template: state.script.template, ...(state.script.seed === undefined ? {} : { seed: state.script.seed }) };
  const result = await api('/api/select', request); unchanged(revision);
  check(structureErrors(result.script)); check(selectionErrors(result.script));
  if (result.script.template !== request.template) throw new Error('Server returned a different template. Sample not applied; retry or check the server.');
  install(keepPresentation(result.script, original)); message('Random sample ready. Review the selected pages and edit its dialogue before generating.');
}));
$('validate').addEventListener('click', () => operate('Validate', async () => {
  const script = clone(state.script); const revision = state.revision;
  check(completeErrors(script)); const result = await api('/api/validate', { script }); unchanged(revision);
  check(structureErrors(result.script));
  if (result.script.template !== script.template || JSON.stringify(result.script.comics) !== JSON.stringify(script.comics)) throw new Error('Validation returned different sources or template. Response not applied; check the server.');
  install(result.script);
  message('Server validation passed. Source lock and resolved defaults recorded; your script remains editable.');
}));
$('draft').addEventListener('click', () => operate('AI Draft', async () => {
  const script = clone(state.script); const revision = state.revision;
  check(structureErrors(script)); check(selectionErrors(script));
  // The writer endpoint resolves its input before writing. Supply placeholders
  // only in this request when starting from unwritten pages; never auto-render them.
  for (const line of script.lines) if (!line.action && !line.text.trim()) line.text = 'Draft commentary for this selected page.';
  const used = usedPages(script);
  for (const comic of script.comics) if (!used.has(comic)) script.lines.push({ speaker: templateFor(script).speakers[0], text: 'Draft commentary for this selected page.', comic });
  check(completeErrors(script));
  let result;
  // Allow both bounded 120-second writer attempts plus response overhead.
  try { result = await api('/api/draft', { script }, { timeoutMs: 250000 }); }
  catch (error) { throw new Error(`${error.message}. You can write manually and Generate video, or ask the operator to configure the optional writer.`); }
  unchanged(revision);
  result.script = keepPresentation(result.script, script);
  check(structureErrors(result.script));
  if (result.script.template !== script.template || JSON.stringify(result.script.comics) !== JSON.stringify(script.comics)) throw new Error('Writer changed the selected source pages or template. Draft rejected; your source selection and script are unchanged.');
  if (['seed', 'scene', 'sourceLock'].some(key => script[key] !== undefined && JSON.stringify(result.script[key]) !== JSON.stringify(script[key]))) throw new Error('Writer changed the seed, scene or source lock. Draft rejected; retry with the current settings.');
  check(completeErrors(result.script)); install(result.script); message('AI draft applied for the same selected pages. Review the wording and validate before generating.');
}));
$('generate').addEventListener('click', () => operate('Generate video', async () => {
  const script = clone(state.script); check(completeErrors(script));
  const voice = $('voice').value;
  if (voice === 'recorded' && script.lines.some(line => !line.action && (typeof line.audio !== 'string' || !line.audio.trim()))) throw new Error('Recorded mode needs an audio path on every spoken line. Add audio in JSON, or choose Local Kokoro.');
  const result = await api('/api/render', { script, voice });
  if (!result || typeof result.id !== 'string') throw new Error('Server did not return a job ID. Refresh jobs before trying again.');
  message(`Submitted ${result.id} (${result.status ?? 'queued'}). It uses the script sent when you clicked Generate; later edits stay in the editor.`);
  await refreshJobs();
}));

function renderJobs(jobs) {
  $('jobs').replaceChildren();
  if (!jobs.length) $('jobs').append(el('p', 'No films yet. Your first render will appear here.', 'muted'));
  for (const job of jobs) {
    const card = el('article', undefined, 'job'); card.append(el('h3', String(job.id ?? 'Unknown job')));
    let progress = '';
    if (typeof job.progress === 'number' && Number.isFinite(job.progress)) {
      const percent = Math.round(Math.max(0, Math.min(100, job.progress <= 1 ? job.progress * 100 : job.progress)));
      progress = ` · ${percent}%`;
      const meter = el('progress'); meter.max = 100; meter.value = percent; meter.setAttribute('aria-label', `Job ${job.id} progress`); card.append(meter);
    }
    card.append(el('p', `${job.status ?? 'unknown'}${progress}`));
    if (typeof job.progress === 'string' && job.progress) card.append(el('p', job.progress));
    if (job.error) card.append(el('p', `${typeof job.error === 'string' ? job.error : stringify(job.error)}\nCheck the script and local server setup, then Generate again when corrected.`, 'status error'));
    if (job.video) {
      const path = localPath(job.video, '/output/');
      if (path) { const link = el('a', 'Open video ↗'); link.href = path; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(link); }
      else card.append(el('p', 'Video link is not a local /output/ path. Check the job output on the server.', 'hint'));
    }
    $('jobs').append(card);
  }
}
async function refreshJobs() {
  if (state.polling) return;
  state.polling = true;
  try {
    const result = await api('/api/jobs');
    if (!Array.isArray(result?.jobs) || result.jobs.some(job => !object(job))) throw new Error('Server returned an invalid jobs list.');
    renderJobs(result.jobs); $('jobs-status').textContent = ''; $('jobs-status').classList.remove('error');
  } catch (error) { $('jobs-status').textContent = `${error.message} Use Refresh jobs to retry. Editor contents are safe.`; $('jobs-status').classList.add('error'); }
  finally { state.polling = false; }
}
$('refresh-jobs').addEventListener('click', refreshJobs);
async function connect() {
  if (state.connecting) return;
  state.connecting = true;
  try {
    message('Connecting to the local theatre…');
    const [session, catalog] = await Promise.all([api('/api/session'), api('/api/catalog')]);
    if (typeof session?.token !== 'string' || !session.token) throw new Error('No session token returned. Check the server and retry.');
    if (!object(catalog) || !Array.isArray(catalog.comics) || !Array.isArray(catalog.templates) || !catalog.templates.length || !Array.isArray(catalog.scenes)) throw new Error('Catalog is missing comics, templates or scenes. Check the server catalog.');
    state.token = session.token; state.catalog = catalog;
    renderGallery();
    if (!state.script) {
      const template = templates().find(item => item.id === 'book-duet') ?? templates()[0];
      install({ version: 1, template: template.id, title: 'Untitled reading', comics: [], lines: [] });
    } else { renderForm(); }
    $('retry').hidden = true; message('Ready. Choose source pages to begin.');
  } catch (error) { state.token = null; message(`Connection failed: ${error.message} Use Retry connection.`, true); $('retry').hidden = false; }
  finally { state.connecting = false; controls(); }
}
$('retry').addEventListener('click', connect);
await connect();
await refreshJobs();
setInterval(() => { if (!document.hidden) void refreshJobs(); }, 2500);
