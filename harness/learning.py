"""Small, source-linked production memory. Ratings are evidence, not new instructions."""
import hashlib
import json
import time


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def product_key(config):
    return signature({k: config[k] for k in ('website', 'products')})


def feedback(store, run_id, rating, note):
    if rating not in ('good', 'okay', 'bad') or not isinstance(note, str) or len(note) > 4000:
        raise ValueError('Use good|okay|bad and a note of at most 4000 characters')
    with store.worker_lock():
        state = store.get(run_id)
        item = {'rating': rating, 'note': note, 'at': time.time()}
        state.setdefault('user_feedback', []).append(item)
        store.save(state, 'user_feedback', item)
    return {'run': run_id, **item}


def lessons(store, config, limit=8):
    results = []
    key = product_key(config)
    for s in store.list():
        if product_key(s['config']) != key:
            continue
        scripts = [t['result'].get('scripts', []) for t in s['tasks']
                   if t['stage'] == 'write' and t.get('result')]
        premise = [x.get('premise', '') for group in scripts for x in group][:2]
        ratings = s.get('user_feedback', [])
        findings = [dict(f, stage=t['stage']) for t in s['tasks']
                    if t['stage'] in ('select', 'board_review', 'creative_qa') and t.get('result')
                    for f in t['result'].get('findings', [])]
        if ratings or premise or findings:
            results.append({'run': s['id'], 'premises': premise,
                            'user_feedback': ratings[-2:], 'review_findings': findings[:3],
                            'status': s['status'], 'technical_success_is_not_aesthetic_approval': True})
        if len(results) == limit:
            break
    return results


def research_key(config, sources):
    # Absolute paths are deliberately absent: moving an unchanged document is not a new fact.
    return signature({'products': product_key(config), 'brand': {k: config['brand'][k] for k in ('name', 'direction')},
                      'concept': config['concept'], 'look': config['output']['look'],
                      'sources': [{k: s[k] for k in ('kind', 'source_sha256', 'url') if k in s} for s in sources]})


def character_voices(store, config):
    voices = {}
    for state in store.list():
        if product_key(state['config']) != product_key(config) or state['status'] not in ('complete', 'partial'):
            continue
        paths = {path: identifier for identifier, path in state.get('asset_paths', {}).items()}
        for task in state['tasks']:
            if task['stage'] == 'direct' and task.get('result'):
                for cast in task['result']['direction'].get('cast', []):
                    identity = paths.get(cast.get('model'))
                    if identity and identity not in voices:
                        voices[identity] = {'voice': cast['voice'], 'performance': cast.get('performance'), 'source_run': state['id']}
        if len(voices) >= 8:
            break
    return voices


def cached_research(store, config, sources, now=None):
    now = time.time() if now is None else now
    key = research_key(config, sources)
    for state in store.list():
        if not 0 <= now - state['created'] < 6 * 3600 or state.get('research_key') != key:
            continue
        for t in state['tasks']:
            if t['stage'] == 'research' and t['status'] == 'succeeded' and t.get('result'):
                from .contracts import verify_accepted, ContractError
                try:
                    verify_accepted(t['result'])
                except (ContractError, OSError, KeyError):
                    continue
                # Accepted files are immutable, hash-verified references, never writable workspaces.
                return {'run': state['id'], 'result': t['result']}
    return None


def metrics(state):
    stages = []
    for t in state['tasks']:
        attempts = t.get('attempts', [])
        stages.append({'task': t['id'], 'status': t['status'], 'attempts': len(attempts),
                       'wall_seconds': round(t.get('wall_seconds', 0), 2),
                       'worker_seconds': round(sum(max(0, a.get('ended', a['started']) - a['started']) for a in attempts), 2),
                       'failures': [a.get('kind') for a in attempts if a.get('kind') != 'ok'],
                       'usage': [a['usage'] for a in attempts if a.get('usage')],
                       'models': list(dict.fromkeys(a['model'] for a in attempts))})
    return {'run': state['id'], 'status': state['status'], 'execution': state.get('execution'),
            'stages': stages, 'monetary_cost': None,
            'cost_note': 'Subscription CLI billing is unavailable; worker time/attempts are measured, not a dollar estimate.'}


def catalog_brief(store, config, entries):
    scores = {}
    for state in store.list()[:40]:
        if product_key(state['config']) != product_key(config) or not state.get('user_feedback'):
            continue
        value = {'good': 1, 'okay': 0, 'bad': -1}[state['user_feedback'][-1]['rating']]
        for task in state['tasks']:
            if task['stage'] == 'assets' and task.get('result'):
                for identifier in task['result'].get('used_asset_ids', []):
                    scores[identifier] = scores.get(identifier, 0) + value
    compact = [{k: e[k] for k in ('id', 'kind', 'path', 'sha256', 'capabilities', 'preview') if k in e}
               for e in entries]
    for e in compact:
        e['user_reuse_score'] = scores.get(e['id'], 0)
    # Characters stay visible; feedback sorts the remaining reusable inventory.
    return sorted(compact, key=lambda e: (e['kind'] != 'character', -e['user_reuse_score'], e['id']))[:80]
