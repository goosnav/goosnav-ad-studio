import * as THREE from 'three';
import { seekEndcardVideo } from './endcard-video.mjs';
export { loadEndcardVideo } from './endcard-video.mjs';

const defaults = { enabled: true, title: 'Goosnav Book Two', text: 'A book of comics.', url: 'www.goosnav.shop', seconds: 3 };
export const endCardFields = (timeline, event) => Object.fromEntries(Object.entries(defaults).map(([key, value]) =>
  [key, event?.[key] ?? timeline.endCard?.[key] ?? value]));

function wrappedLines(ctx, text, maxWidth) {
  const lines = [];
  for (const paragraph of String(text).split('\n')) {
    let line = '';
    for (const word of paragraph.split(/\s+/)) {
      if (ctx.measureText(line ? `${line} ${word}` : word).width <= maxWidth) { line += `${line ? ' ' : ''}${word}`; continue; }
      if (line) lines.push(line);
      line = '';
      for (const character of word) {
        if (line && ctx.measureText(line + character).width > maxWidth) { lines.push(line); line = ''; }
        line += character;
      }
    }
    lines.push(line);
  }
  return lines;
}

function textBlock(ctx, text, rect, { font, size, weight = 'normal', color = '#000000', underline = false }) {
  const initial = Math.max(1, Math.floor(size));
  function fit(value, minimum) {
    for (let fitted = initial; fitted >= minimum; fitted--) {
      ctx.font = `${weight} ${fitted}px ${font}`;
      const lines = wrappedLines(ctx, value, rect.width);
      if (lines.length * fitted * 1.22 <= rect.height && lines.every(line => ctx.measureText(line).width <= rect.width)) return { lines, fitted };
    }
    return null;
  }
  // Preserve normal multiline authoring. Pathological explicit line counts are
  // reflowed before making glyphs too small; no authored words are discarded.
  const minimum = Math.min(12, initial), reflowed = String(text).replace(/\s+/g, ' ').trim();
  const layout = fit(text, minimum) || fit(reflowed, minimum) || fit(reflowed, 1) || { lines: [reflowed], fitted: 1 };
  const { lines, fitted } = layout;
  ctx.font = `${weight} ${fitted}px ${font}`;
  ctx.save(); ctx.beginPath(); ctx.rect(rect.x, rect.y, rect.width, rect.height); ctx.clip();
  ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = color;
  const top = rect.y + Math.max(0, (rect.height - lines.length * fitted * 1.22) / 2);
  for (const [i, line] of lines.entries()) {
    const y = Math.round(top + i * fitted * 1.22);
    ctx.fillText(line, Math.round(rect.x + rect.width / 2), y);
    if (underline && line) {
      const w = ctx.measureText(line).width;
      ctx.fillRect(Math.round(rect.x + (rect.width - w) / 2), Math.round(y + fitted * 1.02), Math.ceil(w), Math.max(1, Math.round(fitted / 16)));
    }
  }
  ctx.restore();
  return { lines, size: fitted, color, underline, font, rect };
}

export function createEndcard({ width, height, card, video, videoAsset, coverAsset, sourceOffset = 2 }) {
  if (!video?.videoWidth || !video.videoHeight || !Number.isFinite(video.duration) || video.duration <= 0) throw new Error('Endcard requires a loaded video');
  if (!Number.isFinite(sourceOffset)) throw new Error('Endcard source offset must be finite');
  const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d');
  const landscape = width > height * 1.15, unit = Math.min(width, height), margin = unit * .065;
  const imageArea = landscape
    ? { x: 0, y: 0, width: width * .46, height }
    : { x: 0, y: 0, width, height };
  const ratio = video.videoWidth / video.videoHeight;
  const h = Math.min(imageArea.height, imageArea.width / ratio), w = h * ratio;
  const videoRect = { x: Math.round(imageArea.x + (imageArea.width - w) / 2), y: Math.round(imageArea.y + (imageArea.height - h) / 2), width: Math.round(w), height: Math.round(h) };
  ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
  // Type is drawn once at output resolution with the fonts loaded by the player.
  const type = document.createElement('canvas'); type.width = width; type.height = height;
  const tc = type.getContext('2d');
  const x = landscape ? width * .46 : margin, textWidth = landscape ? width * .49 : width - 2 * margin;
  const block = (y, h) => ({ x, y: y * height, width: textWidth, height: h * height });
  const typography = {
    title: textBlock(tc, card.title, block(landscape ? .2 : .025, landscape ? .18 : .105), { font: '"ComicTheatreSans", "Helvetica", "Arial", sans-serif', weight: 'bold', size: unit * .068 }),
    text: textBlock(tc, card.text, block(landscape ? .43 : .80, landscape ? .15 : .09), { font: '"ComicTheatreTimes", "Times New Roman", "Liberation Serif", Times, serif', size: unit * .045 }),
    // Three 12px lines need 43.92px at 4:5/432x540. Expand around the
    // existing URL center, keeping a gap below body text and clear of the book.
    url: textBlock(tc, card.url, block(landscape ? .66 : .90, landscape ? .12 : .09), { font: '"ComicTheatreTimes", "Times New Roman", "Liberation Serif", Times, serif', size: unit * .053, color: '#0000ee', underline: true }),
  };
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  texture.generateMipmaps = false; texture.minFilter = THREE.LinearFilter; texture.magFilter = THREE.LinearFilter;
  const scene = new THREE.Scene();
  scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial({ map: texture, toneMapped: false })));
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 5); camera.position.z = 2;
  let sourceTime = null, pending = Promise.resolve();
  const renderAt = seconds => {
    const render = async () => {
      if (!Number.isFinite(seconds)) throw new Error('Endcard time must be finite');
      sourceTime = await seekEndcardVideo(video, sourceOffset + seconds);
      ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, width, height);
      ctx.drawImage(video, videoRect.x, videoRect.y, videoRect.width, videoRect.height);
      ctx.drawImage(type, 0, 0); texture.needsUpdate = true;
    };
    const result = pending.then(render);
    pending = result.catch(() => {});
    return result;
  };
  return { scene, camera, renderAt, diagnostics: () => ({ ...card, video: videoAsset, cover: coverAsset, sourceOffset, sourceTime, videoRect, typography, treatment: 'white / full-resolution type / original spinning product video' }) };
}
