import * as THREE from 'three';

const defaults = { enabled: true, title: 'Goosnav Book Two', text: 'A book of comics.', url: 'www.goosnav.shop', seconds: 3 };
export const endCardFields = (timeline, event) => Object.fromEntries(Object.entries(defaults).map(([key, value]) =>
  [key, event?.[key] ?? timeline.endCard?.[key] ?? value]));

// A standalone, deterministic card. Only this product thumbnail is dithered;
// book/source textures never enter this canvas or undergo pixel processing.
function productImage(image, width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(width / 3)); canvas.height = Math.max(1, Math.round(height / 3));
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const bayer = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
  for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
    const offset = (y * canvas.width + x) * 4;
    const bias = (bayer[(y % 4) * 4 + x % 4] / 16 - .5) * (255 / 31);
    for (let c = 0; c < 3; c++) data.data[offset + c] = Math.round(Math.max(0, Math.min(255, data.data[offset + c] + bias)) / 255 * 31) * 255 / 31;
  }
  ctx.putImageData(data, 0, 0); return canvas;
}

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

export function createEndcard({ width, height, card, cover, coverAsset }) {
  const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d'); ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, width, height);
  const landscape = width > height * 1.15, unit = Math.min(width, height), margin = unit * .065;
  const imageArea = landscape
    ? { x: margin, y: height * .12, width: width * .38, height: height * .76 }
    : { x: margin, y: height * .19, width: width - 2 * margin, height: height * .42 };
  const ratio = cover.width / cover.height;
  const h = Math.min(imageArea.height, imageArea.width / ratio), w = h * ratio;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(productImage(cover, w, h), Math.round(imageArea.x + (imageArea.width - w) / 2), Math.round(imageArea.y + (imageArea.height - h) / 2), Math.round(w), Math.round(h));
  // Threshold type alpha at output resolution. Small fitted text keeps every
  // pixel of its glyphs instead of becoming illegible when enlarged from 6px.
  const type = document.createElement('canvas'); type.width = width; type.height = height;
  const tc = type.getContext('2d', { willReadFrequently: true });
  const x = landscape ? width * .46 : margin, textWidth = landscape ? width * .49 : width - 2 * margin;
  const block = (y, h) => ({ x, y: y * height, width: textWidth, height: h * height });
  const typography = {
    title: textBlock(tc, card.title, block(landscape ? .2 : .045, landscape ? .18 : .13), { font: '"ComicTheatreSans", "Helvetica", "Arial", sans-serif', weight: 'bold', size: unit * .068 }),
    text: textBlock(tc, card.text, block(landscape ? .43 : .65, .15), { font: '"ComicTheatreTimes", "Times New Roman", "Liberation Serif", Times, serif', size: unit * .045 }),
    url: textBlock(tc, card.url, block(landscape ? .66 : .83, .12), { font: '"ComicTheatreTimes", "Times New Roman", "Liberation Serif", Times, serif', size: unit * .053, color: '#0000ee', underline: true }),
  };
  const pixels = tc.getImageData(0, 0, type.width, type.height);
  for (let i = 3; i < pixels.data.length; i += 4) pixels.data[i] = pixels.data[i] >= 96 ? 255 : 0;
  tc.putImageData(pixels, 0, 0); ctx.drawImage(type, 0, 0, width, height);
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  texture.generateMipmaps = false; texture.minFilter = THREE.NearestFilter; texture.magFilter = THREE.NearestFilter;
  const scene = new THREE.Scene();
  scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial({ map: texture, toneMapped: false })));
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 5); camera.position.z = 2;
  return { scene, camera, diagnostics: () => ({ ...card, cover: coverAsset, typography, treatment: 'white / aliased type / ordered product dither' }) };
}
