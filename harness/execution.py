"""Versioned active-time budgets. Pauses and provider waits never reset spending."""
from contextlib import contextmanager
from contextvars import ContextVar
import time


class BudgetExceeded(RuntimeError):
    pass


class FinishRequired(RuntimeError):
    """Stop creative work while a bounded finishing reserve is still available."""


_deadline = ContextVar('production_deadline', default=None)


@contextmanager
def deadline(seconds):
    token = _deadline.set(time.monotonic() + max(0, seconds))
    try:
        yield
    finally:
        _deadline.reset(token)


def bounded_timeout(seconds):
    end = _deadline.get()
    if end is None:
        return seconds
    remaining = end - time.monotonic()
    if remaining <= 0:
        raise BudgetExceeded('Active execution budget exhausted; checkpoints retained.')
    return min(seconds, remaining)


def policy(config):
    generation = config.get('generation', {})
    target = {'low': 600, 'medium': 1200, 'high': 2400}[generation.get('effort', 'medium')]
    target = round(target * config['output']['target_seconds'] / 9 * config['count'])
    if generation.get('fast'):
        target //= 2
    return {'version': 1, 'target_seconds': target, 'hard_seconds': round(target * 1.25),
            'active_seconds': 0.0, 'waiting_seconds': 0.0,
            'mode': 'fast' if generation.get('fast') else 'normal', 'changes': []}


# Relative stage weights reserve most of the budget for scene work, not deliberation.
WEIGHTS = {'research': 2, 'write': 7, 'select': 2, 'direct': 9, 'assets': 17,
           'audio': 9, 'board_review': 3, 'animate': 20, 'edit': 12,
           'frame': 3, 'qa': 6, 'creative_qa': 5, 'package': 1}

# These are attempt allowances, not reserved spending or extra global time.
# Mandatory local synthesis/scene setup/rendering needs more than a short review.
STAGE_FLOORS = {'direct': {'low': 90, 'medium': 120, 'high': 180},
                'assets': {'low': 120, 'medium': 180, 'high': 300},
                'animate': {'low': 120, 'medium': 180, 'high': 300}}


class Budget:
    def __init__(self, state, save):
        self.state, self.save = state, save
        self.data = state.get('execution')
        self.last = time.monotonic()

    def tick(self, force=False):
        if not self.data:
            return
        now = time.monotonic()
        elapsed = now - self.last
        if force or elapsed >= 2:
            self.data['active_seconds'] += elapsed
            self.last = now
            self.data['heartbeat_at'] = time.time()
            self.save(self.state, 'budget_checkpoint')

    def spent(self):
        return self.data['active_seconds'] + time.monotonic() - self.last if self.data else 0

    @contextmanager
    def external(self, metric):
        """Track bounded delivery I/O separately from the generation allowance."""
        self.tick(True)
        started = time.monotonic()
        try:
            yield
        finally:
            if self.data:
                self.data[metric] = self.data.get(metric, 0) + time.monotonic() - started
            self.last = time.monotonic()
            if self.data:
                self.save(self.state, 'external_time', {'metric': metric})

    def remaining(self):
        return max(0, self.data['hard_seconds'] - self.spent()) if self.data else float('inf')

    def check(self):
        if self.data and self.remaining() <= 0:
            self.tick(True)
            raise BudgetExceeded('Active execution budget including 25% overtime exhausted; '
                                 'work is checkpointed. Resume requires an explicit --extra-minutes allowance.')

    def production_remaining(self):
        if not self.data:
            return float('inf')
        if any(t['stage'] == 'script' for t in self.state['tasks']):
            # The animator now owns production. There is no storyboard phase to
            # interrupt and hand to a cheaper worker partway through the film.
            return self.remaining()
        if self.data.get('finishing'):
            return self.remaining()
        count = self.state['config']['count']
        target = self.data['target_seconds']
        reserve = min(target * .4, max(120 * count, min(300 * count, target * .2)))
        # Don't handicap a real animation that needs editing/QA. Unrendered
        # repair loops must stop earlier, before they eat the finishing reserve.
        unfinished = {t['ad'] for t in self.state['tasks'] if t['stage'] == 'package'
                      and t['status'] != 'succeeded'}
        has_cut = any(t['stage'] in ('animate', 'edit') and t['status'] == 'succeeded'
                      and t['ad'] in unfinished for t in self.state['tasks'])
        cutoff = (self.data['hard_seconds'] if has_cut else target) - reserve
        if not has_cut and self.state['config'].get('generation', {}).get('effort', 'medium') in ('low','medium'):
            # Finishing now includes real animation, acting checks and a closing
            # card, not a cheap product-only substitute. Switch before repair
            # loops consume the time those mandatory stages actually need.
            cutoff = min(cutoff, target * .6)
        return max(0, cutoff - self.spent())

    def check_production(self):
        self.check()
        if self.data and self.production_remaining() <= 0:
            raise FinishRequired('Creative deadline reached; finish the existing story with reduced production scope.')

    def simplify(self):
        if any(t['stage'] == 'script' for t in self.state['tasks']):
            return False  # keep the requested creative model; reduce render cost in its workspace
        if self.data and self.spent() >= self.data['target_seconds'] * .75 and self.data['mode'] != 'recovery':
            self.data['mode'] = 'recovery'
            self.data['changes'].append({'at_seconds': round(self.spent(), 1),
                                        'reason': 'reserve finishing time', 'scope': 'reuse; no optional builds or auditions'})
            self.tick(True)
            return True
        return False

    def stage_seconds(self, task, ceiling):
        if not self.data:
            return ceiling
        self.check()
        if any(t['stage'] == 'script' for t in self.state['tasks']):
            if task['stage'] == 'script':
                spent = sum(max(0, a.get('ended', a['started']) - a['started'])
                            for a in task.get('attempts', [])
                            if a.get('revision', 0) == task.get('revision', 0))
                allowance = max(0.01, min(120, 45 + 15 * self.state['config']['count']) - spent)
            else:
                unfinished = sum(t['stage'] == 'package' and t['status'] != 'succeeded'
                                 for t in self.state['tasks']) or 1
                per_ad = self.remaining() / unfinished
                # Reserve editing and deterministic finishing before animation starts.
                allowance = (per_ad * .72 if task['stage'] == 'animate' else
                             per_ad * .65 if task['stage'] == 'edit' else per_ad)
            return max(.01, min(ceiling, allowance, self.remaining()))
        pending = [t for t in self.state['tasks'] if t['status'] != 'succeeded']
        weight = sum(WEIGHTS.get(t['stage'], 5) for t in pending) or 1
        normal_left = max(0, self.data['target_seconds'] - self.spent())
        # Give each attempt a fair share, retaining the reserve for fallback/validation.
        # Direction includes mandatory local synthesis plus measured-plan assembly.
        # Real low-fast trials spent 3x30s handing off a productive cold take batch.
        # One adequate attempt is cheaper; this floor never extends the global cap.
        minimum = 30
        if task['stage'] in STAGE_FLOORS:
            effort = self.state['config'].get('generation', {}).get('effort', 'medium')
            minimum = STAGE_FLOORS[task['stage']][effort]
        if self.data.get('finishing'):
            minimum = min(minimum, 120 if task['stage'] == 'animate' else 60)
            if task['stage'] == 'creative_qa':
                minimum = 60  # inspect the completed film once, not repeated unusable 30s sessions
        share = max(minimum, max(normal_left, self.remaining() * .6) * WEIGHTS.get(task['stage'], 5) / weight)
        return max(.01, min(ceiling, share, self.remaining()))
