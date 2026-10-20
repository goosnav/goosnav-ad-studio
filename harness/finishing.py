"""Bounded, model-free product film when the creative pipeline runs out of time.

This is a different deliverable, not a pass for a rejected story. Only active
catalogued product footage is used; abandoned dialogue and claims are omitted.
"""
import json
from pathlib import Path

from .contracts import ContractError
from .execution import bounded_timeout


def product_film(script, config, work, cancelled):
    from .end_cards import prepare_clip
    from .frame_policy import LINK, CARD
    from .media import balance, check_picture, check_video, link_text, run
    from .workers import supervise

    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    if cancelled():
        raise ContractError('Finishing cancelled')
    output, tools = config['output'], config['tools']
    seconds = output['target_seconds']
    # Resolve by configured product identity; never search archived characters or
    # guess a filename after an asset-root refactor.
    clip = prepare_clip(script, None, config, work, seconds)
    if clip['mode'] != 'library_clip':
        raise ContractError('No approved configured product footage: ' + clip['reason'])
    product = str(script.get('product', '')).strip()
    name = clip['product']
    if not product or not config.get('website'):
        raise ContractError('Product film requires a product and shop website')
    root, python = Path(tools['frame_root']), tools['frame_python']
    if not (root/'app/src/goosnav_frame').is_dir() or not Path(python).is_file():
        raise ContractError('Product finishing requires the configured Frame runtime')
    request = {'root': str(root), 'input': str(work/clip['path']), 'scale': output['width']/1080,
               'jobs': [{'output': str(work/'card.mp4'), 'still': str(work/'end_card.png'),
                         'still_time': seconds/2, 'settings': {
                             'canvas': {'preset': 'custom', 'width': output['width'],
                                        'height': output['height'], 'background': '#ffffff', 'layout': 'stacked'},
                             'title': {'visible': True, 'text': balance(name)},
                             'link': {**LINK, 'visible': True, 'text': link_text(config['website'])},
                             'media': {'fit': 'contain', 'trim_start': 0, 'trim_duration': seconds, 'keep_audio': False},
                             'export': {'format': 'mp4', 'fps': output['fps'], 'quality': 'high'}, **CARD}}]}
    (work/'frame.json').write_text(json.dumps(request, indent=2))
    outcome = supervise([python, str(Path(__file__).with_name('frame_runner.py')), str(work/'frame.json')],
                        cwd=work, prompt='', log=work/'frame.log',
                        timeout=bounded_timeout(300), cancelled=cancelled)
    if outcome['kind'] != 'ok' or cancelled():
        raise ContractError('Product finishing failed: ' + outcome['kind'])
    # Silence is intentional: story dialogue over an unrelated spinning product
    # would be misleading. Don't run a LUFS normalizer against negative infinity.
    run([tools['ffmpeg'], '-v', 'error', '-y', '-i', str(work/'card.mp4'),
         '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-map', '0:v:0', '-map', '1:a:0',
         '-c:v', 'copy', '-c:a', 'aac', '-t', str(seconds), '-movflags', '+faststart', str(work/'final.mp4')])
    # The full-film product card deliberately has wide white margins. Story
    # percentiles on those margins can call a readable product "washed out".
    # Check contrast on the actual source picture, freeze/black on the final,
    # and the final card's dark type/light ground against its unframed source.
    source_picture = check_picture(work/clip['path'], config, seconds)
    card_picture = check_picture(work/'final.mp4', config, seconds, check_contrast=False)
    readability = check_picture(work/'final.mp4', config, 0, master=work/clip['path'], check_contrast=False)
    report = {'video': check_video(work/'final.mp4', config),
              'picture': {'source': source_picture, 'card': card_picture,
                          'readability': readability['end_card'], 'contrast_scope': 'unframed product footage'},
              'sound': {'intentional_silence': True, 'dialogue': [],
                        'rationale': 'Product-only fallback; omitted dialogue from the abandoned story.'},
              'source': clip, 'delivery_mode': 'product_only'}
    (work/'qa.json').write_text(json.dumps(report, indent=2))
    return {'summary': 'Product-only fallback: approved moving product, name and shop link; intentional silence.',
            'delivery_mode': 'product_only', 'master': 'final.mp4', 'product': name,
            'source_asset': clip, 'files': [
                {'path': 'final.mp4', 'kind': 'video'}, {'path': 'end_card.png', 'kind': 'image'},
                {'path': 'qa.json', 'kind': 'notes'}, {'path': 'frame.json', 'kind': 'source'}]}
