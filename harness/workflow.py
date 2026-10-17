"""A small deterministic scheduler around long-lived creative workers."""
import json
import os
from pathlib import Path
import shutil
import signal
import time

from .briefs import brief
from .contracts import ContractError, validate, promote, verify_accepted
from .models import resolve_workers
from .sources import snapshot
from .workers import command, reset_delay, subscription_status, supervise

ROLES = {'research': 'researcher', 'write': 'writer', 'critique': 'critic', 'revise': 'writer',
         'critique_final': 'critic', 'select': 'selector', 'assets': 'producer', 'audio': 'producer',
         'animate': 'producer', 'review': 'director', 'edit': 'producer', 'creative_qa': 'director',
         'direct': 'director', 'board_review': 'director'}
CAMPAIGN = ['research', 'write', 'critique', 'revise', 'critique_final', 'select']
PRODUCTION = ['direct', 'assets', 'board_review', 'audio', 'animate', 'review', 'edit', 'frame', 'qa', 'creative_qa', 'package']


def build_tasks(count):
    pairs = [(s, None) for s in CAMPAIGN] + [(s, ad) for ad in range(count) for s in PRODUCTION]
    return [{'id': f'{"campaign" if ad is None else f"ad-{ad+1:02}"}-{s}', 'stage': s, 'ad': ad,
             'status': 'pending', 'attempts': [], 'result': None, 'revision': 0, 'feedback': ''} for s, ad in pairs]


def process_identity(pid):
    try:
        # comm may contain spaces; fields after its closing parenthesis are stable.
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def execute_worker(profile, work, prompt, log, cancelled, timeout, started):
    return supervise(command(profile, work), cwd=work, prompt=prompt, log=log,
                     timeout=timeout, cancelled=cancelled, started=started,
                     max_log_mb=profile.get('log_mb', 32))


class Engine:
    def __init__(self, store, execute=execute_worker, resolve=resolve_workers, auth=subscription_status,
                 preflight=None):
        self.store, self.execute, self.resolve, self.auth = store, execute, resolve, auth
        # Real workers need real tools; scripted test workers do not.
        from .preflight import check_dependencies
        self.preflight = preflight or (check_dependencies if execute is execute_worker else lambda config: [])

    def run(self, run_id, max_steps=None):
        with self.store.worker_lock():
            state = self.store.get(run_id); root = self.store.path(run_id)
            try:
                if not state['tasks']:
                    state['tasks'] = build_tasks(state['config']['count'])
                    self.store.save(state, 'planned')
                self.reconcile(state)
                problems = self.preflight(state['config'])
                if problems:
                    raise ContractError('Missing dependencies (fix, then resume): ' + '; '.join(problems))
                if not state.get('sources_ready'):
                    state['sources'] = snapshot(state['config'], root/'sources')
                    state['sources_ready'] = True
                    self.store.save(state, 'sources_ready')
                if not state['models']:
                    state['models'] = self.resolve(state['config']['workers'])
                    self.store.save(state, 'models_resolved')
                steps = 0
                while max_steps is None or steps < max_steps:
                    action = self.store.control_value(run_id)
                    if action != 'run':
                        state['status'] = 'paused' if action == 'pause' else 'cancelled'; break
                    task = self.next_task(state)
                    if task is None:
                        state['status'] = self.aggregate(state); break
                    self.verify_history(state)
                    state['status'] = 'running'; task['status'] = 'running'
                    self.store.save(state, 'task_started', {'task': task['id']})
                    if task['stage'] in ROLES:
                        self.agent_task(state, task, root)
                    else:
                        self.builtin_task(state, task, root)
                    steps += 1
                    if task['status'] in ('waiting_provider', 'cancelled'):
                        state['status'] = task['status']; break
                    if task['status'] == 'succeeded':
                        self.review_transition(state, task)
                    if task['ad'] is None and task['status'] in ('failed', 'needs_review'):
                        state['status'] = task['status']; break
                else:
                    state['status'] = 'ready'
                self.store.save(state, 'run_status', {'status': state['status']})
            except (KeyboardInterrupt, SystemExit):
                state['status'] = 'interrupted'
                self.store.save(state, 'interrupted')
                raise
            except Exception as e:
                state['status'] = 'failed'; state['error'] = f'{type(e).__name__}: {e}'
                for t in state['tasks']:
                    if t['status'] == 'running':
                        t['status'] = 'failed'; t['feedback'] = state['error']
                self.store.save(state, 'exception', {'error': state['error']})
            return state

    def reconcile(self, state):
        for task in state['tasks']:
            if task['status'] == 'succeeded':
                verify_accepted(task['result'])
            if task['status'] == 'running':
                for attempt in task['attempts']:
                    pid = attempt.get('pid')
                    if pid and attempt.get('identity') and process_identity(pid) == attempt['identity']:
                        try:
                            os.killpg(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                task['status'] = 'pending'
                task['feedback'] = 'Controller interrupted. Inspect checkpoint/handoff and complete the task; no output was accepted.'
        for record in state.get('sources', []):
            if 'text' in record:
                from .contracts import digest
                if digest(record['text']) != record['sha256']:
                    raise ContractError('Source snapshot changed; create a new run')

    def verify_history(self, state):
        for task in state['tasks']:
            if task['status']=='succeeded':
                verify_accepted(task['result'])

    def prepare_retry(self, run_id, task_id):
        with self.store.worker_lock():
            state=self.store.get(run_id)
            target=next((t for t in state['tasks'] if t['id']==task_id),None)
            if target is None:raise ValueError('Unknown task ID')
            if target['status'] not in ('failed','needs_review','waiting_provider'):
                raise ValueError('Retry only failed/review/waiting tasks')
            if target['status']=='needs_review':
                feedback=json.dumps(target['result'],indent=2)
                start='revise' if target['ad'] is None else target['result'].get('restart','direct')
                self.rewind(state,target['ad'],start,feedback)
            else:
                target['revision']+=1;target['status']='pending';target['result']=None
            state['error']=''
            self.store.save(state,'retry_requested',{'task':task_id});self.store.control(run_id,'run')

    def rewind(self,state,ad,start,feedback):
        affected=False
        for t in state['tasks']:
            if t['ad']==ad and t['stage']==start:affected=True
            if affected and t['ad']==ad:
                if t['result']:
                    t['previous']=t['result']   # the rejected version, so a repair must differ from it
                t['status']='pending';t['result']=None;t['revision']+=1;t['feedback']=feedback

    def next_task(self, state):
        failed_ads = {t['ad'] for t in state['tasks'] if t['status'] in ('failed', 'needs_review', 'cancelled')}
        if None in failed_ads:
            return None
        for index, task in enumerate(state['tasks']):
            if task['status'] in ('pending', 'waiting_provider') and task['ad'] not in failed_ads:
                prerequisites=[t for t in state['tasks'][:index] if t['ad'] is None or t['ad']==task['ad']]
                if all(t['status']=='succeeded' for t in prerequisites):
                    return task
        return None

    def aggregate(self, state):
        complete = sum(t['stage'] == 'package' and t['status'] == 'succeeded' for t in state['tasks'])
        if complete == state['config']['count']:
            return 'complete'
        if complete:
            return 'partial'
        return 'needs_review' if any(t['status'] == 'needs_review' for t in state['tasks']) else 'failed'

    def inputs(self, state, task):
        inputs = {t['id']: t['result'] for t in state['tasks'] if t['status'] == 'succeeded'
                  and (t['ad'] is None or t['ad'] == task['ad'])}
        if task['ad'] is not None:
            selection = next(t['result'] for t in state['tasks'] if t['stage'] == 'select')
            scripts = next(t['result']['scripts'] for t in state['tasks'] if t['stage'] == 'revise')
            inputs['selected_script'] = next(s for s in scripts if s['id'] == selection['selected'][task['ad']])
        return inputs

    def agent_task(self, state, task, root):
        c = state['config']; work = root/'workspaces'/task['id']; work.mkdir(parents=True, exist_ok=True)
        context = {'count': c['count']}
        if task['stage'] == 'select':
            context['candidate_ids'] = [s['id'] for t in state['tasks'] if t['stage'] == 'revise' for s in t['result']['scripts']]
        routes = state['models']['workers'][ROLES[task['stage']]]
        unavailable = []
        for route, profile in enumerate(routes):
            provider = profile['provider']
            if profile.get('unavailable') or self.store.cooldown(provider) or not self.auth(provider):
                unavailable.append(f'{provider}: {profile.get("unavailable") or "cooldown or subscription login unavailable"}')
                continue
            # Attempts are durable. Resume cannot silently reset a consumed budget.
            # Budgets are per route; attempts from before routes were recorded count against
            # the provider's first route.
            first = next(i for i, r in enumerate(routes) if r['provider'] == provider)
            used = sum(a.get('route', first if a['provider'] == provider else -1) == route
                       and a['revision'] == task['revision']
                       and a.get('kind') not in ('cancelled', 'quota', None) for a in task['attempts'])
            for _ in range(max(0, c['limits']['repairs'] + 1 - used)):
                if self.store.control_value(state['id']) == 'cancel':
                    task['status'] = 'cancelled'; return
                number = len(task['attempts']) + 1
                attempt = {'number': number, 'route': route, 'provider': provider, 'model': profile['model'],
                           'effort': profile.get('effort'), 'revision': task['revision'], 'started': time.time()}
                task['attempts'].append(attempt)
                result_file = work/'result.json'
                if result_file.exists():
                    result_file.rename(work/f'result.previous-{number}.json')
                prompt = brief(task, c, self.inputs(state, task), state['sources'], task['feedback'], str(self.store.root/'runs'))
                (work/'TASK.md').write_text(prompt)
                log = root/'logs'/f'{task["id"]}-{number}.jsonl'
                attempt['log'] = str(log)
                self.store.save(state, 'attempt_started', {'task': task['id'], **attempt})
                def started(pid):
                    attempt['pid'] = pid; attempt['identity'] = process_identity(pid)
                    self.store.save(state, 'worker_started', {'task': task['id'], 'pid': pid})
                timeout = c['limits']['production_timeout_seconds' if task['ad'] is not None else 'timeout_seconds']
                outcome = self.execute({**profile, 'log_mb': c['limits']['log_mb']}, work, prompt, log,
                    cancelled=lambda: self.store.control_value(state['id']) == 'cancel', timeout=timeout, started=started)
                attempt.update(outcome, ended=time.time()); attempt.pop('pid', None); attempt.pop('identity', None)
                # Claude aliases move over time. Pin the concrete observed model for the rest of this run.
                observed=outcome.get('observed_models',[])
                if provider=='claude' and profile['model'] in ('opus','sonnet','haiku') and len(observed)==1:
                    alias=profile['model']
                    if alias in observed[0]:
                        for profiles in state['models']['workers'].values():
                            for route in profiles:
                                if route['provider']=='claude' and route['model']==alias:
                                    route['model']=observed[0];route['resolved_alias']=alias
                self.verify_history(state)
                if outcome['kind'] == 'ok':
                    try:
                        if not result_file.is_file() or result_file.stat().st_size > 2 * 1024 * 1024:
                            raise ContractError('Missing result.json or result larger than 2 MB')
                        data = validate(task['stage'], json.loads(result_file.read_text()), work, context)
                        self.validate_media(task, data, work, c, state)
                        task['result'] = promote(data, work, root/'artifacts'/task['id']/f'attempt-{number}')
                        task['status'] = 'succeeded'
                        self.store.save(state, 'task_succeeded', {'task': task['id']}); return
                    except Exception as e:
                        # Whatever the worker handed in, a bad result is a repair note, never a dead run.
                        attempt['kind'] = 'invalid'
                        attempt['detail'] = str(e) if isinstance(e, ValueError) else f'{type(e).__name__}: {e}'
                task['feedback'] = f'Previous {provider} attempt: {attempt["kind"]}. {attempt.get("detail", "")[-4000:]}'
                self.store.save(state, 'attempt_failed', {'task': task['id'], 'kind': attempt['kind']})
                if attempt['kind'] == 'cancelled':
                    task['status'] = 'cancelled'; return
                if attempt['kind'] == 'quota':
                    self.store.cooldown(provider, reset_delay(attempt.get('detail', ''))
                                        or c['limits']['provider_cooldown_seconds'])
                if attempt['kind'] in ('quota', 'auth', 'model', 'permission', 'dependency'):
                    unavailable.append(task['feedback']); break
        task['status'] = 'waiting_provider' if unavailable and all(
            a.get('kind') in ('quota', 'auth', 'model', 'permission', 'dependency', None)
            for a in task['attempts'] if a['revision'] == task['revision']) else 'failed'
        task['feedback'] = '\n'.join(unavailable) or task['feedback']
        self.store.save(state, 'task_stopped', {'task': task['id'], 'status': task['status'], 'reason': task['feedback']})

    def direction(self, state, ad):
        task = next((t for t in state['tasks'] if t['ad'] == ad and t['stage'] == 'direct'), None)
        return task['result']['direction'] if task and task['status'] == 'succeeded' else None

    def validate_media(self, task, data, work, config, state=None):
        self.check_changed(task, data, work)
        if task['stage'] == 'direct':
            from .direction import check_direction
            check_direction(data['direction'], config)
        if task['stage'] == 'assets':
            self.check_boards(state, task['ad'], data, config)
        if task['stage'] in ('audio', 'animate', 'edit'):
            from .media import check_audio, check_video
            if task['stage'] == 'audio':
                check_audio(work/data['mix'], work/data['timeline'], config,
                            self.direction(state, task['ad']) if state else None)
                self.measure_mouths(data, work, config)
                timeline = json.loads((work/data['timeline']).read_text())
                if timeline['dialogue']:
                    from .speech import check_presence, check_speech
                    data['speech'] = {'presence': check_presence(work/data['dialogue_stem'], timeline),
                                      'recognised': check_speech(work/data['mix'], timeline, config)}
            elif task['stage'] == 'animate':
                check_video(work/data['preview'], config, preview=True)
                from .media import check_picture
                direction = self.direction(state, task['ad']) if state else None
                card = (direction or {}).get('end_card') or {}
                story_end = (direction['duration'] - card.get('seconds', 0)) if direction else config['output']['max_seconds']
                data['picture'] = check_picture(work/data['preview'], config, story_end)
                self.check_talking(state, task['ad'], data, work, config)
            else:
                check_video(work/data['master'], config)

    DELIVERABLES = {'assets': lambda d: [b['image'] for b in d.get('boards', []) if isinstance(b, dict)],
                    'audio': lambda d: [d.get('mix')], 'animate': lambda d: [d.get('preview')],
                    'edit': lambda d: [d.get('master')]}

    def check_changed(self, task, data, work):
        """After a review sent this stage back, handing in the same deliverables wastes a review round."""
        previous = task.get('previous')
        pick = self.DELIVERABLES.get(task['stage'])
        if not previous or not pick or not task['revision']:
            return
        from .contracts import digest
        before = sorted(digest(p) for p in pick(previous) if p and Path(p).is_file())
        after = sorted(digest(work/p) for p in pick(data) if p and (work/p).is_file())
        if before and before == after:
            raise ContractError('nothing changed since the rejected version: re-render the deliverables '
                                'with the review findings fixed')

    def check_boards(self, state, ad, data, config):
        """One storyboard still per directed beat (and the end-card picture), rendered from the scene."""
        direction = self.direction(state, ad) if state else None
        if direction is None:
            return
        declared = {f['path'] for f in data['files']}
        boards = data.get('boards')
        if not isinstance(boards, list) or not all(isinstance(b, dict) and b.get('image') in declared for b in boards):
            raise ContractError('boards must list {beat, image} with every image a declared file')
        if any(not b['image'].lower().endswith(('.png', '.jpg', '.jpeg')) for b in boards):
            raise ContractError('board images must be PNG or JPEG stills rendered from the blocked scene')
        wanted = set(range(len(direction['beats']))) | ({'end_card'} if direction.get('end_card') else set())
        missing = wanted - {b.get('beat') for b in boards}
        if missing:
            raise ContractError(f'Storyboard is missing beats {sorted(missing, key=str)}')

    def measure_mouths(self, data, work, config):
        """Jaw curves per speaker from the dialogue stem, delivered with the audio for the animator."""
        from .lipsync import mouth_curves
        timeline = json.loads((work/data['timeline']).read_text())
        if not timeline['dialogue']:
            return
        declared = {f['path'] for f in data['files']}
        if data.get('dialogue_stem') not in declared:
            raise ContractError('dialogue_stem must name a declared WAV of the voices alone, aligned to the mix')
        mouths = mouth_curves(work/data['dialogue_stem'], timeline, config['output']['fps'])
        (work/'mouths.json').write_text(json.dumps(mouths))
        data['files'] = [f for f in data['files'] if f['path'] != 'mouths.json'] + [{'path': 'mouths.json', 'kind': 'timeline'}]
        data['mouths'] = 'mouths.json'

    def check_talking(self, state, ad, data, work, config):
        """Each speaker's jaw moves on their lines and their face is on camera (saved scene)."""
        audio = next((t['result'] for t in (state or {}).get('tasks', []) if t['ad'] == ad and t['stage'] == 'audio'), None)
        if not audio:
            return
        timeline = json.loads(Path(audio['timeline']).read_text())
        if not timeline['dialogue']:
            return
        declared = {f['path'] for f in data['files']}
        if not str(data.get('scene', '')).endswith('.blend') or data['scene'] not in declared:
            raise ContractError('scene must name the declared, saved .blend of the animated film')
        speakers = {line['speaker'] for line in timeline['dialogue']}
        if not isinstance(data.get('rigs'), dict) or not speakers <= set(data['rigs']):
            raise ContractError(f'rigs must map every speaker {sorted(speakers)} to its armature object name')
        planned = (self.direction(state, ad) or {}).get('lines', [])
        rate = timeline['sample_rate']
        lines = [{'speaker': l['speaker'], 'text': l['text'], 'start': l['start_sample'] / rate,
                  'end': l['end_sample'] / rate, 'offscreen': bool((planned[i] if i < len(planned) else {}).get('offscreen'))}
                 for i, l in enumerate(timeline['dialogue'])]
        from .media import check_scene
        models = {c['speaker']: c['model'] for c in (self.direction(state, ad) or {}).get('cast', []) if c.get('model')}
        data['talking'] = check_scene(work/data['scene'], data['rigs'], lines, config['output']['fps'], models)

    def review_transition(self, state, task):
        if task['stage'] == 'critique' and task['result']['verdict'] == 'pass':
            # Nothing to fix: the drafts stand as the revision and this critique as the final one.
            stage = {t['stage']: t for t in state['tasks'] if t['ad'] is None}
            for name, source in (('revise', 'write'), ('critique_final', 'critique')):
                if stage[name]['status'] == 'pending':
                    stage[name].update(status='succeeded', result={**stage[source]['result'], 'skipped': True},
                                       feedback=f'Skipped: the first critique passed; reusing {source}.')
            self.store.save(state, 'revision_skipped', {'task': task['id']})
            return
        if task['stage'] not in ('critique_final', 'board_review', 'review', 'creative_qa') or task['result']['verdict'] == 'pass':
            return
        limits = state['config']['limits']
        rounds = limits.get('board_repairs', 4) if task['stage'] == 'board_review' else limits['repairs']
        if task['revision'] >= rounds:
            # Out of repair rounds: only blockers need a human. Other notes travel downstream.
            if any(f['severity'] == 'blocking' for f in task['result']['findings']):
                task['status'] = 'needs_review'
            else:
                task['result']['accepted_with_notes'] = True
            return
        default = {'critique_final': 'revise', 'board_review': 'assets'}.get(task['stage'], 'audio')
        start_stage = 'revise' if task['stage'] == 'critique_final' else task['result'].get('restart', default)
        feedback = json.dumps(task['result'], indent=2)
        self.rewind(state,task['ad'],start_stage,feedback)
        self.store.save(state, 'revision_requested', {'task': task['id']})

    def builtin_task(self, state, task, root):
        from .media import finish_frame, check_video, package
        work = root/'workspaces'/task['id']; work.mkdir(parents=True, exist_ok=True)
        inputs = self.inputs(state, task); ad = task['ad']
        def result(stage):
            return next(t['result'] for t in state['tasks'] if t['ad'] == ad and t['stage'] == stage)
        try:
            if task['stage'] == 'frame':
                data = finish_frame(result('edit')['master'], inputs['selected_script'], state['config'], work,
                    cancelled=lambda: self.store.control_value(state['id']) == 'cancel',
                    direction=self.direction(state, ad))
            elif task['stage'] == 'qa':
                from .media import check_final_mix
                report = check_video(result('frame')['master'], state['config'])
                timeline = json.loads(Path(result('audio')['timeline']).read_text())
                report['mix'] = check_final_mix(result('frame')['master'], timeline, state['config'], work)
                from .speech import check_speech, loudness, TRUE_PEAK
                report['speech'] = check_speech(result('frame')['master'], timeline, state['config'])
                from .media import check_picture
                framed = result('frame').get('end_card_start')
                report['picture'] = check_picture(result('frame')['master'], state['config'],
                                                  framed or report['duration'], master=result('edit')['master'] if framed else None)
                report['loudness'] = level = loudness(result('frame')['master'])
                target = state['config']['output']['loudness']
                if abs(level['integrated'] - target) > 1.5 or level['true_peak'] > TRUE_PEAK + 0.5:
                    raise ContractError(f'Final loudness {level} misses {target} LUFS / {TRUE_PEAK} dBTP')
                (work/'qa.json').write_text(json.dumps(report, indent=2))
                data = {'summary': 'Encoded media passed technical checks', 'files': [{'path':'qa.json','kind':'notes'}]}
            else:
                data = package(inputs, state, work)
            self.verify_history(state)
            if task['stage'] == 'package' and state['config']['output'].get('folder'):
                # Convenience copies for people; the accepted artifacts remain the record.
                out = Path(state['config']['output']['folder']) / state['id']; out.mkdir(parents=True, exist_ok=True)
                shutil.copy2(result('frame')['master'], out / f'ad-{ad+1:02}.mp4')
                shutil.copy2(work / 'ad.zip', out / f'ad-{ad+1:02}.zip')
            task['result'] = promote(data, work, root/'artifacts'/task['id']/f'revision-{task["revision"]}-{time.time_ns()}')
            task['status'] = 'succeeded'
        except Exception as e:
            task['feedback'] = f'{type(e).__name__}: {e}'
            task['status'] = 'cancelled' if self.store.control_value(state['id']) == 'cancel' else 'failed'
        self.store.save(state, 'builtin_finished', {'task': task['id'], 'status': task['status']})
