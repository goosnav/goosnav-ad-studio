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
from .sources import archived_asset, reconcile_sources, snapshot
from .workers import CODEX_CLI_DEFAULT, command, last_actions, reset_delay, subscription_status, supervise

ROLES = {'research': 'researcher', 'write': 'writer', 'critique': 'critic', 'revise': 'writer',
         'critique_final': 'critic', 'select': 'selector', 'script_sense': 'director',
          'assets': 'producer', 'audio': 'producer',
         'animate': 'animator', 'review': 'director', 'edit_plan': 'editor',
          'edit': 'editor', 'edit_review': 'director', 'creative_qa': 'reviewer',
         'direct': 'director', 'board_review': 'director'}
CAMPAIGN = ['research', 'write', 'select']
# Reviews are consolidated: one story/selection check and one review of the completed ad.
# Frame and media QA remain deterministic, not additional model calls.
PRODUCTION = ['direct', 'assets', 'audio', 'animate', 'edit', 'frame', 'qa', 'creative_qa', 'package']
# Long operations render or build assets; planning/review should never consume a render-length budget.
HEAVY_STAGES = {'assets', 'audio', 'animate', 'edit'}
# Worker stopped mid-task with its work intact; the next route continues it.
INTERRUPTIONS = {'quota': 'ran out of usage', 'capacity': 'hit provider capacity',
                 'context': 'ran out of context', 'timeout': 'timed out',
                 'idle_timeout': 'stalled', 'log_limit': 'hit the log limit'}


def continuation_note(task, attempt, work):
    since = min(a['started'] for a in task['attempts'] if a['revision'] == task['revision'])
    written = sorted(str(p.relative_to(work)) for p in work.rglob('*')
                     if p.is_file() and p.stat().st_mtime >= since
                     and p.name not in ('TASK.md', '.worker-input.txt') and not p.name.startswith('result.previous-'))
    lines = [f'HANDOFF: the previous {attempt["provider"]} worker {INTERRUPTIONS[attempt["kind"]]} mid-task. '
             'Continue its work in this workspace; do not start over. Check and reuse what it built, '
             'finish the remaining steps, then write result.json.']
    if written:
        lines.append('Files written so far: ' + ', '.join(written[:15]) + (' ...' if len(written) > 15 else ''))
    handoff = work / 'handoff.md'
    if handoff.is_file():
        lines.append('Its handoff.md ends: ' + ' '.join(handoff.read_text(errors='replace')[-500:].split()))
    actions = last_actions(attempt['log']) if attempt.get('log') else []
    if actions:
        lines.append('Its last actions: ' + ' | '.join(actions))
    note = '\n'.join(lines)[:1400]
    if task.get('assignment'):
        note += '\nThe original notes for this task follow.\n' + task['assignment']
    return note


def agent_deadline(config, stage):
    limits = config['limits']
    if stage in HEAVY_STAGES:
        return limits['production_timeout_seconds'], None
    ceilings = {'research': 180, 'select': 240, 'creative_qa': 300, 'direct': 600}
    if stage in ceilings:
        total = min(ceilings[stage], limits.get('quick_timeout_seconds', 600))
        return total, min(total, limits.get('idle_timeout_seconds', 300))
    if stage in CAMPAIGN:
        total = min(limits['timeout_seconds'], limits.get('quick_timeout_seconds', 600))
    else:
        total = min(limits['production_timeout_seconds'], limits.get('review_timeout_seconds', 900))
    return total, min(total, limits.get('idle_timeout_seconds', 300))


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
                     max_log_mb=profile.get('log_mb', 32),
                     idle_timeout=profile.get('idle_timeout'))


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
                warnings = reconcile_sources(state['config'])
                if warnings:
                    state.setdefault('source_warnings', []).extend(warnings)
                    self.store.save(state, 'sources_reconciled', {'warnings': warnings})
                self.reconcile_cast(state)
                if not state.get('sources_ready'):
                    state['sources'] = snapshot(state['config'], root/'sources')
                    state['sources_ready'] = True
                    self.store.save(state, 'sources_ready')
                if not state['models']:
                    state['models'] = self.resolve(state['config']['workers'])
                    self.store.save(state, 'models_resolved')
                else:
                    self.refresh_unavailable_codex(state)
                state['error'] = ''
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

    def refresh_unavailable_codex(self, state):
        """Recover Codex routes disabled by an earlier transient discovery error.

        Resumed runs retain their model snapshots. Only re-resolve unavailable Codex
        entries, never successful/pinned routes from another provider.
        """
        routes = state['models'].get('workers', {})
        stale = [(role, index) for role, profiles in routes.items()
                 for index, profile in enumerate(profiles)
                 if profile['provider'] == 'codex' and profile.get('unavailable')]
        if not stale:
            return
        refreshed = self.resolve(state['config']['workers'])
        newer = refreshed.get('workers', {})
        for role, index in stale:
            candidates = newer.get(role, [])
            if index < len(candidates) and candidates[index].get('provider') == 'codex':
                routes[role][index] = candidates[index]
        state['models']['checked_at'] = time.time()
        state['models']['discovery_error'] = refreshed.get('discovery_error')
        self.store.save(state, 'codex_routes_refreshed', {'count': len(stale)})

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

    def reconcile_cast(self, state):
        """A resumed plan must not bring retired characters back into production."""
        library = state['config']['sources']['characters']
        for task in state['tasks']:
            if task['stage'] != 'direct' or task['status'] != 'succeeded':
                continue
            cast = task['result']['direction'].get('cast', [])
            retired = [c.get('model') for c in cast if
                       (c.get('model') and archived_asset(c['model'])) or
                       (library and c.get('model') not in library)]
            if retired:
                self.rewind(state, task['ad'], 'direct',
                            f'The accepted cast is retired or no longer approved: {retired}. '
                            'Replan with the configured active sources.characters; never use archived models.')
                self.store.save(state, 'cast_replanned', {'ad': task['ad'], 'retired': retired})

    def prepare_retry(self, run_id, task_id):
        with self.store.worker_lock():
            state=self.store.get(run_id)
            target=next((t for t in state['tasks'] if t['id']==task_id),None)
            if target is None:raise ValueError('Unknown task ID')
            if target['status'] not in ('failed','needs_review','waiting_provider','succeeded'):
                raise ValueError('Retry failed, review, waiting or finished tasks')
            if target['status']=='succeeded':
                # Redo from here: this stage and everything after it for the same ad.
                self.rewind(state,target['ad'],target['stage'],f'Operator asked to redo {target["stage"]} and later stages.')
            elif target['status']=='needs_review':
                feedback=json.dumps(target['result'],indent=2)
                if target['ad'] is None:
                    start = 'write' if target['stage'] == 'select' and any(
                        t['stage'] == 'write' for t in state['tasks']) else 'revise'
                else:
                    start = target['result'].get('restart', 'direct')
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
            scripts = next(t['result']['scripts'] for t in reversed(state['tasks'])
                           if t['stage'] in ('revise', 'write') and t['status'] == 'succeeded')
            inputs['selected_script'] = next(s for s in scripts if s['id'] == selection['selected'][task['ad']])
        return inputs

    def contract_retry_available(self, state, task, route, routes):
        """One bounded format correction after ordinary provider fallback is spent.

        This cannot authorize bad media, choose scripts, or bypass a review. Quota
        interruptions do not spend the correction, and the budget survives resume.
        """
        attempts = [a for a in task['attempts'] if a['revision'] == task['revision']
                    and a.get('kind') not in ('cancelled', 'quota', 'capacity', 'auth', 'model',
                                              'permission', 'dependency', None)]
        if not attempts or attempts[-1].get('failure_phase') != 'contract':
            return False
        used = sum(bool(a.get('contract_repair')) for a in attempts)
        if used >= state['config']['limits'].get('contract_repairs', 1):
            return False
        return not any(not p.get('unavailable') and not self.store.cooldown(p['provider'])
                       for p in routes[route + 1:])

    def agent_task(self, state, task, root):
        c = state['config']; work = root/'workspaces'/task['id']; work.mkdir(parents=True, exist_ok=True)
        context = {'count': c['count']}
        if task['stage'] == 'script_sense':
            context['selected_ids'] = next(t['result']['selected'] for t in state['tasks'] if t['stage'] == 'select')
        if task['stage'] == 'select':
            context['candidate_ids'] = [s['id'] for t in state['tasks'] if t['stage'] in ('write', 'revise')
                                        and t['status'] == 'succeeded' for s in t['result']['scripts']]
        workers = state['models']['workers']
        role = ROLES[task['stage']]
        # Saved runs from before the dedicated animator role keep their routes.
        routes = (workers.get(role, workers['director']) if role == 'reviewer' else
                  workers.get(role, workers['producer']) if role in ('animator', 'editor') else workers[role])
        unavailable = []; blocked_routes = set(); last_failure = None
        # A cheap stage's single retry normally comes from the next provider. When every
        # other route is cooled down or unavailable, the usable route keeps that retry.
        usable = sum(not p.get('unavailable') and not self.store.cooldown(p['provider']) for p in routes)
        for route, profile in enumerate(routes):
            provider = profile['provider']
            reason = profile.get('unavailable')
            if not reason and self.store.cooldown(provider):
                reason = 'provider is on usage-limit cooldown'
            if not reason:
                authenticated = self.auth(provider)
                if not authenticated and not (provider == 'codex' and self.auth is subscription_status):
                    reason = 'subscription login unavailable'
                # Codex login-status wording varies across CLI versions. The CLI
                # itself is authoritative: try its ChatGPT session and classify
                # any real auth error, rather than silently disabling the route.
            if reason:
                unavailable.append(f'{provider} ({profile.get("model")}): {reason}')
                blocked_routes.add(route)
                continue
            # Attempts are durable. Resume cannot silently reset a consumed budget.
            # Budgets are per route; attempts from before routes were recorded count against
            # the provider's first route.
            first = next(i for i, r in enumerate(routes) if r['provider'] == provider)
            used = sum(a.get('route', first if a['provider'] == provider else -1) == route
                       and a['revision'] == task['revision']
                       and a.get('kind') not in ('cancelled', 'quota', 'capacity', 'model', None)
                       for a in task['attempts'])
            # Cheap tasks never retry the same expensive session repeatedly. They may
            # fall back to the next configured provider once.
            attempt_cap = (c['limits']['repairs'] + 1 if task['stage'] in HEAVY_STAGES
                           else 1 if usable > 1 else 2)
            remaining = max(0, attempt_cap - used)
            repairing_contract = remaining == 0 and self.contract_retry_available(state, task, route, routes)
            if repairing_contract:
                remaining = 1
                prior_error = next(a['detail'] for a in reversed(task['attempts'])
                                   if a['revision'] == task['revision'] and a.get('failure_phase') == 'contract')
                task['feedback'] = f'Correct the previous result format: {prior_error}\n' + task['feedback']
            while remaining > 0:
                remaining -= 1
                if self.store.control_value(state['id']) == 'cancel':
                    task['status'] = 'cancelled'; return
                number = len(task['attempts']) + 1
                if not any(a['revision'] == task['revision'] for a in task['attempts']):
                    # Repair findings for this revision; failure notes replace feedback later.
                    task['assignment'] = task['feedback']
                attempt = {'number': number, 'route': route, 'provider': provider, 'model': profile['model'],
                           'effort': profile.get('effort'), 'revision': task['revision'], 'started': time.time()}
                if repairing_contract:
                    attempt['contract_repair'] = True
                    repairing_contract = False
                task['attempts'].append(attempt)
                result_file = work/'result.json'
                if result_file.exists():
                    result_file.rename(work/f'result.previous-{number}.json')
                prompt = brief(task, c, self.inputs(state, task), state['sources'], task['feedback'])
                attempt['prompt_chars'] = len(prompt)
                (work/'TASK.md').write_text(prompt)
                log = root/'logs'/f'{task["id"]}-{number}.jsonl'
                attempt['log'] = str(log)
                self.store.save(state, 'attempt_started', {'task': task['id'], **attempt})
                def started(pid):
                    attempt['pid'] = pid; attempt['identity'] = process_identity(pid)
                    self.store.save(state, 'worker_started', {'task': task['id'], 'pid': pid})
                timeout, idle = agent_deadline(c, task['stage'])
                try:
                    outcome = self.execute({**profile, 'log_mb': c['limits']['log_mb'],
                                            'idle_timeout': idle}, work, prompt, log,
                        cancelled=lambda: self.store.control_value(state['id']) == 'cancel',
                        timeout=timeout, started=started)
                except Exception as exc:
                    # Unexpected provider/CLI failures are an attempt failure,
                    # not a crash of the entire state machine.
                    outcome = {'kind': 'dependency', 'detail': f'{type(exc).__name__}: {exc}'}
                attempt.update(outcome, ended=time.time()); attempt.pop('pid', None); attempt.pop('identity', None)
                # Claude aliases move over time. Pin the concrete observed model for the rest of this run.
                observed=outcome.get('observed_models',[])
                if provider=='claude' and profile['model'] in ('opus','sonnet','haiku') and len(observed)==1:
                    alias=profile['model']
                    if alias in observed[0]:
                        for profiles in state['models']['workers'].values():
                            for pinned in profiles:
                                if pinned['provider']=='claude' and pinned['model']==alias:
                                    pinned['model']=observed[0];pinned['resolved_alias']=alias
                self.verify_history(state)
                if outcome['kind'] == 'ok' and not result_file.is_file():
                    attempt['kind'] = 'invalid'
                    attempt['detail'] = 'Missing result.json'
                # If a deadline hit after a worker wrote a COMPLETE valid result,
                # salvage it rather than discarding good work. Partial text isn't
                # accepted: the same contract/media checks still apply.
                if outcome['kind'] in ('ok', 'timeout', 'idle_timeout') and result_file.is_file():
                    phase = 'contract'
                    try:
                        if not result_file.is_file() or result_file.stat().st_size > 2 * 1024 * 1024:
                            raise ContractError('Missing result.json or result larger than 2 MB')
                        data = validate(task['stage'], json.loads(result_file.read_text()), work, context)
                        phase = 'media'
                        self.validate_media(task, data, work, c, state)
                        phase = 'promote'
                        task['result'] = promote(data, work, root/'artifacts'/task['id']/f'attempt-{number}')
                        task['status'] = 'succeeded'
                        if outcome['kind'] != 'ok':
                            attempt['recovered_from'] = outcome['kind']
                        self.store.save(state, 'task_succeeded', {'task': task['id']}); return
                    except Exception as e:
                        # A timed-out or idle worker may have left an incomplete draft.
                        # Keep the timeout classification and switch routes promptly.
                        if outcome['kind'] == 'ok':
                            attempt['kind'] = 'invalid'
                            attempt['failure_phase'] = phase
                        attempt['detail'] = str(e) if isinstance(e, ValueError) else f'{type(e).__name__}: {e}'
                task['feedback'] = last_failure = (
                    f'Previous {provider} attempt: {attempt["kind"]}. {attempt.get("detail", "")[-4000:]}')
                if attempt['kind'] in INTERRUPTIONS:
                    task['feedback'] = last_failure = continuation_note(task, attempt, work)
                self.store.save(state, 'attempt_failed', {'task': task['id'], 'kind': attempt['kind']})
                if remaining == 0 and self.contract_retry_available(state, task, route, routes):
                    remaining = 1
                    repairing_contract = True
                if attempt['kind'] == 'cancelled':
                    task['status'] = 'cancelled'; return
                if attempt['kind'] == 'quota':
                    self.store.cooldown(provider, reset_delay(attempt.get('detail', ''))
                                        or c['limits']['provider_cooldown_seconds'])
                if attempt['kind'] == 'capacity':
                    # Server-side overload clears in minutes; a short cooldown lets the
                    # waiting loop retry instead of the run failing outright.
                    self.store.cooldown(provider, c['limits'].get('capacity_cooldown_seconds', 300))
                if provider == 'codex' and attempt['kind'] == 'model' and profile['model'] != CODEX_CLI_DEFAULT:
                    # A pinned model may have disappeared after the run was created.
                    # A model-not-found error is not a creative repair; retry this
                    # same route once with Codex's native default model.
                    profile['model'] = CODEX_CLI_DEFAULT
                    profile['resolution'] = 'Codex CLI default after model error'
                    remaining += 1
                    self.store.save(state, 'codex_model_fallback', {'task': task['id'], 'route': route})
                    continue
                # Don't repeat a hung session on the same model; try the next
                # provider or cheaper route while retaining workspace notes.
                if attempt['kind'] in ('timeout', 'idle_timeout', 'log_limit'):
                    break
                if attempt['kind'] in ('quota', 'capacity', 'auth', 'model', 'permission', 'dependency'):
                    blocked_routes.add(route)
                    unavailable.append(task['feedback']); break
        # An earlier malformed result must not turn a later quota interruption
        # into a terminal failure. Wait only if a blocked route still has work
        # allowance; exhausted routes cannot keep a broken task waiting forever.
        current_attempts = [a for a in task['attempts'] if a['revision'] == task['revision']]
        transient = ('quota', 'capacity', 'auth', 'model', 'permission', 'dependency')
        # A merely skipped cooldown must not hide a subsequent real failure on
        # the usable route (such as never writing result.json).
        waiting_routes = blocked_routes if not current_attempts or current_attempts[-1].get('kind') in transient else ()
        can_wait = False
        for route in waiting_routes:
            provider = routes[route]['provider']
            first = next(i for i, p in enumerate(routes) if p['provider'] == provider)
            spent = sum(a.get('route', first if a['provider'] == provider else -1) == route
                        and a['revision'] == task['revision']
                        and a.get('kind') not in ('cancelled', 'quota', 'capacity', 'model', None)
                        for a in task['attempts'])
            cap = (c['limits']['repairs'] + 1 if task['stage'] in HEAVY_STAGES
                   else 1 if usable > 1 else 2)
            can_wait |= spent < cap or self.contract_retry_available(state, task, route, routes)
        task['status'] = 'waiting_provider' if can_wait else 'failed'
        if task['status'] == 'failed' and last_failure:
            # Lead with the error that actually failed; skipped routes are context, not the cause.
            task['feedback'] = '\n'.join([last_failure, *(u for u in unavailable if u != last_failure)])
        else:
            # A handoff leads so the brief's repair budget never truncates it away.
            task['feedback'] = '\n'.join(sorted(unavailable, key=lambda u: not u.startswith('HANDOFF'))) or task['feedback']
        self.store.save(state, 'task_stopped', {'task': task['id'], 'status': task['status'], 'reason': task['feedback']})

    def direction(self, state, ad):
        task = next((t for t in state['tasks'] if t['ad'] == ad and t['stage'] == 'direct'), None)
        return task['result']['direction'] if task and task['status'] == 'succeeded' else None

    def validate_media(self, task, data, work, config, state=None):
        self.check_changed(task, data, work)
        if task['stage'] == 'direct':
            from .direction import check_direction
            check_direction(data['direction'], config)
        if task['stage'] == 'edit_plan':
            from .editing import validate_plan
            prior = {t['stage']: t['result'] for t in state['tasks'] if t['ad'] == task['ad'] and t['status'] == 'succeeded'}
            timeline = json.loads(Path(prior['audio']['timeline']).read_text())
            validate_plan(data['plan'], timeline, config, prior['direct']['direction'])
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
                media = check_video(work/data['master'], config)
                from .editing import validate_conformance
                prior = {t['stage']: t['result'] for t in state['tasks'] if t['ad'] == task['ad'] and t['status'] == 'succeeded'}
                source = json.loads(Path(prior['audio']['timeline']).read_text())
                plan = (prior['edit_plan']['plan'] if 'edit_plan' in prior else data['plan'])
                validate_conformance(work/data['timeline'], plan, source,
                                     config, prior['direct']['direction'], media['duration'])

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
        if task['stage'] not in ('select', 'critique_final', 'script_sense', 'board_review', 'review',
                                 'edit_review', 'creative_qa') or task['result']['verdict'] == 'pass':
            return
        limits = state['config']['limits']
        budget = limits.get('board_repairs', 4) if task['stage'] == 'board_review' else limits['repairs']
        # Count this review's own requests; upstream rewinds also bump revision and must not spend them.
        if task.get('rounds', 0) >= budget:
            # Out of repair rounds: only blockers need a human. Other notes travel downstream.
            if task['stage'] == 'select' or any(f['severity'] == 'blocking' or
                   (task['stage'] in ('script_sense', 'edit_review') and f['severity'] == 'important')
                   for f in task['result']['findings']):
                task['status'] = 'needs_review'
            else:
                task['result']['accepted_with_notes'] = True
            return
        default = {'select': 'write', 'critique_final': 'revise', 'script_sense': 'write',
                   'board_review': 'assets', 'edit_review': 'edit_plan'}.get(task['stage'], 'audio')
        start_stage = default if task['stage'] in ('select', 'critique_final', 'script_sense') else task['result'].get('restart', default)
        # Old persisted reviews may refer to removed stages; avoid a dead-end rewind.
        if task['ad'] is not None and not any(t['ad'] == task['ad'] and t['stage'] == start_stage
                                                   for t in state['tasks']):
            start_stage = 'edit'
        feedback = json.dumps(task['result'], separators=(',', ':'))
        rounds = task.get('rounds', 0) + 1
        self.rewind(state,task['ad'],start_stage,feedback)
        task['rounds'] = rounds
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
                timeline = json.loads(Path(result('edit')['timeline']).read_text())
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
