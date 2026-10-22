const TIMEOUT_MS = 8000;
// Chromium reports fractional seeks a few microseconds off the requested time.
// 0.1ms covers one 1/12288s source clock tick, far below a 24fps frame (41.67ms).
const SEEK_TOLERANCE_SECONDS = .0001;

// HAVE_CURRENT_DATA after seeked means drawImage can consume the decoded frame.
// A video-frame callback alone can hang on paused/repeated-frame seeks.
function waitForFrame(video, start, label, target, timeoutMs = TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const events = ['loadeddata', 'durationchange', 'seeked', 'canplay'];
    const cleanup = () => {
      clearTimeout(timer);
      events.forEach(event => video.removeEventListener(event, check));
      video.removeEventListener('error', fail);
      video.removeEventListener('emptied', fail);
    };
    const fail = () => { cleanup(); reject(new Error(`Endcard video ${label} failed${video.error ? ` (media error ${video.error.code})` : ''}`)); };
    const check = () => {
      if (video.error) return fail();
      if (!video.seeking && video.readyState >= 2 && Number.isFinite(video.duration) && video.duration > 0 &&
          (target === undefined || Math.abs(video.currentTime - target) <= SEEK_TOLERANCE_SECONDS)) { cleanup(); resolve(); }
    };
    const timer = setTimeout(() => { cleanup(); reject(new Error(`Endcard video ${label} timed out after ${TIMEOUT_MS}ms`)); }, timeoutMs);
    events.forEach(event => video.addEventListener(event, check));
    video.addEventListener('error', fail);
    video.addEventListener('emptied', fail);
    try { start(); check(); } catch (error) { cleanup(); reject(error); }
  });
}

/** Caller owns this resource and must dispose it, including on player failure. */
export async function loadEndcardVideo(url) {
  if (typeof url !== 'string' || !url.trim()) throw new Error('Endcard video URL is required');
  const video = document.createElement('video');
  video.preload = 'auto'; video.muted = true; video.playsInline = true;
  video.crossOrigin = 'anonymous';
  let disposed = false, objectURL;
  const controller = new AbortController(), deadline = performance.now() + TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(new Error(`Endcard video load timed out after ${TIMEOUT_MS}ms`)), TIMEOUT_MS);
  const dispose = () => {
    if (disposed) return;
    disposed = true; video.pause(); video.removeAttribute('src'); video.load();
    if (objectURL) URL.revokeObjectURL(objectURL);
  };
  try {
    // Frozen production assets are full HTTP 200 responses without Range support.
    // Chromium may clamp HTTP media seeks to zero even with Content-Length.
    // Own the complete MP4 locally so absolute seeks do not depend on the server.
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`Endcard video load failed (HTTP ${response.status})`);
    const bytes = await response.blob(); // The same deadline covers headers AND body.
    controller.signal.throwIfAborted();
    objectURL = URL.createObjectURL(bytes.slice(0, bytes.size, 'video/mp4'));
    video.src = objectURL;
    // Setting src schedules loading; do not call load() here: its emptied event
    // would represent setup, rather than resource disposal while awaiting data.
    await waitForFrame(video, () => {}, 'load', undefined, Math.max(1, deadline - performance.now()));
    video.pause();
    return { video, dispose };
  } catch (error) { dispose(); throw error; }
  finally { clearTimeout(timer); }
}

export async function seekEndcardVideo(video, seconds) {
  if (!video?.getAttribute('src') || !Number.isFinite(video.duration) || video.duration <= 0) throw new Error('Endcard requires a loaded video');
  if (!Number.isFinite(seconds)) throw new Error('Endcard time must be finite');
  video.pause();
  const target = ((seconds % video.duration) + video.duration) % video.duration;
  await waitForFrame(video, () => {
    // Setting the same currentTime can trigger a new seek without a new frame.
    if (video.currentTime !== target) video.currentTime = target;
  }, 'seek', target);
  return target;
}
