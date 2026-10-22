// Reusable v10 facial performance v1. Identical portable copy in the 3D library:
// exports/theatre-performance.mjs. Pure absolute-time sampling, no frame history.
export const clamp = (n, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, Number.isFinite(n) ? n : lo));
export const ease = n => { const x = clamp(n); return x * x * (3 - 2 * x); };
const number = (n, fallback = 0) => Number.isFinite(n) ? n : fallback;
export const clothing = Object.freeze({ blue: '#527fa5', rust: '#ae6149', olive: '#78834e',
  'blue-beady': '#527fa5', 'rust-beady': '#ae6149', 'olive-beady': '#78834e' });
export const emotions = Object.freeze({
  neutral: Object.freeze({ brow: 0, asymmetry: 0, tilt: 0, smile: 0, eye_open: 1 }),
  thoughtful: Object.freeze({ brow: .12, asymmetry: .06, tilt: .06, smile: -.12, eye_open: .88 }),
  curious: Object.freeze({ brow: .22, asymmetry: .18, tilt: -.10, smile: 0, eye_open: 1 }),
  skeptical: Object.freeze({ brow: -.26, asymmetry: .38, tilt: .10, smile: -.16, eye_open: .76 }),
  dry: Object.freeze({ brow: -.04, asymmetry: .09, tilt: .015, smile: 0, eye_open: .72 }),
  pleased: Object.freeze({ brow: .18, asymmetry: 0, tilt: -.03, smile: .7, eye_open: .9 }),
  concerned: Object.freeze({ brow: .35, asymmetry: -.12, tilt: .06, smile: -.9, eye_open: .92 }),
  exasperated: Object.freeze({ brow: -.38, asymmetry: .18, tilt: -.09, smile: -.75, eye_open: .6 }),
});
const aliases = { calm: 'neutral', deadpan: 'dry', amused: 'pleased', happy: 'pleased',
  surprised: 'curious', annoyed: 'exasperated', sad: 'concerned' };

export function envelope(age, duration, attack = .18, release = .24) {
  return ease(age / attack) * ease((duration - age) / release);
}

export function sampleMouth(curve, seconds) {
  if (!Number.isFinite(seconds) || !curve?.length) return 0;
  const first = curve[0], last = curve.at(-1);
  if (seconds <= first.t || seconds >= last.t || last.t <= first.t) return 0;
  let value = 0;
  for (let i = 1; i < curve.length; i++) {
    const a = curve[i - 1], b = curve[i];
    if (seconds <= b.t) {
      const u = ease((seconds - a.t) / (b.t - a.t || 1));
      value = clamp(a.value) + (clamp(b.value) - clamp(a.value)) * u;
      break;
    }
  }
  // Short onset/offset taper also handles imported curves with nonzero endpoints.
  // No speech energy is invented outside the measured support or through silence.
  return clamp(value) * envelope(seconds - first.t, last.t - first.t, .035, .045);
}

export function sampleExpression(emotion = 'neutral', face = {}, weight = 1) {
  const exp = emotions[aliases[emotion] || emotion] || emotions.neutral;
  const w = clamp(weight);
  const brow = number(face.brow, exp.brow), asymmetry = number(face.asymmetry, exp.asymmetry);
  return {
    brows: [number(face.brow_left, brow), number(face.brow_right, brow + asymmetry)].map(n => clamp(n, -1, 1) * w || 0),
    tilt: clamp(number(face.tilt, exp.tilt), -.5, .5) * w,
    smile: clamp(number(face.mouth_curve, number(face.smile, exp.smile)), -1, 1) * w,
    eyeOpen: 1 + (clamp(number(face.eye_open, exp.eye_open)) - 1) * w,
  };
}

export function sampleVisemes(energy, seconds, seed = 0, index = 0) {
  const value = clamp(energy);
  const phase = number(seconds) * 8.1 + number(seed) % 97 * .17 + index * 1.3;
  // Audio supplies jaw energy, not phonemes. These restrained deterministic
  // coarticulation weights must not be described as phoneme-accurate lip sync.
  const round = .14 + .10 * Math.sin(phase);
  const wide = .15 + .10 * Math.sin(phase * .73 + 1.1);
  return { open: value * (1 - round - wide), round: value * round, wide: value * wide };
}
