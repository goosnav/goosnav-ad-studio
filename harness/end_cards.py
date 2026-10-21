"""Reuse catalogued product videos; identity and paths belong to configuration."""
import re
from pathlib import Path

from .contracts import ContractError


def prepare_clip(script, direction, config, work, seconds):
    from .library import catalog_file
    from .media import run

    card = (direction or {}).get('end_card') or {}
    product = str(card.get('product') or script.get('product', '')).strip()
    configured = config['output'].get('end_card_clips', [])
    exact = [entry for entry in configured if entry['product'].strip().casefold() == product.casefold()]
    matches = exact or [entry for entry in configured
               if re.match(re.escape(entry['product'].strip()) + r'(?!\w)', product, re.I)]
    fallback = {'mode': 'master', 'reason': 'No configured clip for the selected product'}
    if not matches:
        return fallback
    if len(matches) != 1:
        return {**fallback, 'reason': 'Ambiguous product clip mapping; set end_card.product explicitly'}
    chosen = matches[0]
    output = Path(work) / 'end_card_clip.mp4'
    try:
        library = config['output'].get('end_card_library')
        scoped = {**config, 'library': {**config.get('library', {}), 'root': library}} if library else config
        entry = catalog_file(scoped, chosen['asset_id'], kind='end_card_video')
        # Decode a short video-only excerpt. Loop a short source rather than freezing
        # its last frame, and never replace the ad's dialogue with the clip's sound.
        run([config['tools']['ffmpeg'], '-v', 'error', '-y', '-stream_loop', '-1',
             '-i', entry['path'], '-ss', str(chosen.get('start', 0)), '-t', str(seconds),
             '-map', '0:v:0', '-an', '-vf', f"fps={config['output']['fps']}",
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p',
             str(output)], timeout=120)
        return {'mode': 'library_clip', 'product': chosen['product'], 'asset_id': entry['id'], 'sha256': entry['sha256'],
                'start': chosen.get('start', 0), 'path': output.name}
    except (ContractError, OSError, ValueError) as exc:
        output.unlink(missing_ok=True)
        return {'mode': 'master', 'reason': f'Configured clip unavailable; using rendered hero: {exc}'}
