"""Discover current account-visible Codex models through the CLI's own protocol."""
import copy
import json
import selectors
import shutil
import subprocess
import time

from .workers import worker_env, terminate_group


class ModelError(RuntimeError):
    pass


def choose_model(models, tier):
    matches = []
    for index, m in enumerate(models):
        d = m.get('description', '').lower()
        if m.get('hidden') or m.get('upgrade') or any(w in d for w in ('older', 'previous', 'deprecated')):
            continue
        score = 0
        if tier == 'quality':
            score = 100 if any(w in d for w in ('frontier', 'most capable', 'most demanding')) else 0
            score = max(score, 60 if 'latest' in d and 'workhorse' in d else 0)
        elif tier == 'economy':
            score = 100 if any(w in d for w in ('affordable', 'cheapest', 'low-cost', 'cost-efficient')) else 0
            score = max(score, 50 if 'fast' in d and any(w in d for w in ('small', 'efficient', 'easy', 'easier')) else 0)
        elif tier == 'balanced':
            score = 100 if 'latest' in d and any(w in d for w in ('workhorse', 'balanced', 'coding')) else 0
            score = max(score, 80 if m.get('isDefault') else 0)
        else:
            raise ModelError(f'Unknown model tier: {tier}')
        if score:
            matches.append((score, -index, m))
    if not matches:
        raise ModelError(f'No confidently classified current {tier} model. Inspect `models` or configure an explicit model.')
    return max(matches, key=lambda v: v[:2])[2]


def codex_catalog(timeout=30):
    """Metadata only: no inference, no direct credential access, no stale cache fallback."""
    proc = subprocess.Popen(['codex', 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, env=worker_env(), start_new_session=True)
    sel = selectors.DefaultSelector(); sel.register(proc.stdout, selectors.EVENT_READ)
    def send(payload):
        proc.stdin.write(json.dumps(payload) + '\n'); proc.stdin.flush()
    send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'ad-studio', 'version': '0.1'}}})
    deadline = time.monotonic() + timeout
    models = []
    try:
        while time.monotonic() < deadline:
            if not sel.select(.2):
                continue
            line = proc.stdout.readline()
            if not line:
                break
            message = json.loads(line)
            if 'error' in message:
                raise ModelError(str(message['error']))
            if message.get('id') == 1:
                send({'method': 'initialized', 'params': {}})
                send({'id': 2, 'method': 'model/list', 'params': {'limit': 100}})
            if message.get('id') == 2:
                result = message['result']; models.extend(result['data'])
                if result.get('nextCursor'):
                    send({'id': 2, 'method': 'model/list', 'params': {'limit': 100, 'cursor': result['nextCursor']}})
                else:
                    return models
        raise ModelError('Codex model discovery timed out or closed; run `codex login` and retry')
    finally:
        sel.close(); terminate_group(proc)
        proc.stdin.close(); proc.stdout.close()


def resolve_workers(workers):
    resolved = copy.deepcopy(workers)
    catalog = None; discovery_error = None
    if any(p['provider'] == 'codex' and p['model'].startswith('auto:') for ps in workers.values() for p in ps):
        try:
            catalog = codex_catalog()
        except (OSError, ValueError, ModelError) as e:
            discovery_error = str(e)
    for role, profiles in resolved.items():
        for p in profiles:
            p['selector'] = p['model']
            if not shutil.which(p['provider']):
                p['unavailable'] = 'CLI is not installed'; continue
            if not p['model'].startswith('auto:'):
                p['resolution'] = 'explicit override'; continue
            tier = p['model'].split(':', 1)[1]
            if p['provider'] == 'claude':
                if tier not in ('quality', 'balanced', 'economy'):
                    raise ModelError(f'Unknown tier: {tier}')
                p['model'] = {'quality': 'opus', 'balanced': 'sonnet', 'economy': 'haiku'}[tier]
                p['resolution'] = 'CLI-maintained role alias; actual model recorded from session events'
            else:
                if discovery_error:
                    p['unavailable'] = discovery_error; continue
                try:
                    chosen = choose_model(catalog, tier)
                    p['model'] = chosen['model']
                    efforts = [e['reasoningEffort'] for e in chosen.get('supportedReasoningEfforts', [])]
                    wanted = p.get('effort', 'high' if tier == 'quality' else 'medium' if tier == 'balanced' else 'low')
                    if efforts and wanted not in efforts:
                        raise ModelError(f'{chosen["model"]} does not support effort {wanted}')
                    p['effort'] = wanted
                    p['resolution'] = chosen.get('description', '')
                except ModelError as e:
                    p['unavailable'] = str(e)
    return {'checked_at': time.time(), 'workers': resolved, 'catalog': catalog or [],
            'discovery_error': discovery_error}
