"""Durable delivery retry policy, independent of generation status/budget.

Failed attempts stay queued without an attempt limit. A saved due time prevents
both production hooks and a restarted background worker from retrying in a burst.
"""
import random
import math
import time

from .delivery import _already_verified, _completed_ads, _error, _rate_limited, upload_run
from .store import Busy


RETRY_BASE_SECONDS = 2
RETRY_MAX_SECONDS = 64
RETRY_POLICY = 2
DRIVE_COOLDOWN = 'drive-delivery'


def prepare_retry(store, state):
    """Return the effective deadline; caller holds run and transfer leases.

    Upgrade old half-hour backoffs in place, including their shared cooldown.
    A malformed receipt must not hold every other queued run hostage.
    """
    info = state.get('delivery')
    if not isinstance(info, dict):
        return time.time() + store.cooldown(DRIVE_COOLDOWN)
    now = time.time()
    raw = info.get('next_retry_at', 0)
    valid = type(raw) in (int, float) and math.isfinite(raw) and raw >= 0
    due = raw if valid else 0
    changed = not valid
    if not valid:
        info.update(next_retry_at=0, error='Invalid saved upload retry time; checking delivery again')
    if 'next_retry_at' in info and info.get('retry_policy') != RETRY_POLICY:
        ceiling = now + RETRY_MAX_SECONDS
        due = min(due, ceiling)
        info.update(next_retry_at=due, retry_policy=RETRY_POLICY)
        # Only the obsolete delivery cooldown changes. Model/provider limits
        # and all current-policy deadlines retain their original authority.
        with store.connect() as db:
            db.execute('UPDATE cooldowns SET until=MIN(until, ?) WHERE provider=?',
                       (ceiling, DRIVE_COOLDOWN))
        changed = True
    if changed:
        state['delivery'] = info
        store.save(state, 'delivery_retry_migrated', info)
    return max(due, now + store.cooldown(DRIVE_COOLDOWN))


def _retry(store, state):
    info = state['delivery']
    previous = info.get('retry_failures', 0)
    failures = (previous if type(previous) is int and previous >= 0 else 0) + 1
    base = min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * 2 ** min(failures - 1, 6))
    delay = random.uniform(base, base + 1)
    info.update(status='retrying', retry_failures=failures, retry_policy=RETRY_POLICY,
                next_retry_at=time.time() + delay)
    if _rate_limited(info.get('error', '')):
        store.cooldown(DRIVE_COOLDOWN, delay)
    store.save(state, 'delivery_retry_scheduled', info)


def deliver_ready(store, state):
    # Hold the transfer lease through the cooldown check and receipt/retry saves.
    # Busy is a deferral, not a failed attempt or an invitation to rewrite state.
    try:
        with store.delivery_lock():
            return _deliver_ready(store, state)
    except Busy:
        return state
    except Exception as exc:
        _failed(store, state, exc)
        return state


def _failed(store, state, exc):
    info = state.get('delivery')
    if not isinstance(info, dict):
        info = state['delivery'] = {}
    info.update(status='failed', error=_error(exc))
    try:
        _retry(store, state)
    except Exception:
        # A broken state backend cannot make delivery fatal to rendering.
        # Keep the failed receipt in memory for the caller's next save.
        pass


def _deliver_ready(store, state):
    """Attempt due deliveries only; persist retries and never fail production.

    The caller owns when this runs and excludes delivery time from its production
    budget. Mutate and return the supplied snapshot, as upload_run does.
    """
    try:
        config = state['config']
        if (not config.get('delivery', {}).get('drive', '').strip()
                or not config.get('output', {}).get('folder')
                or not _completed_ads(state)):
            return state
        info = state.get('delivery') or {}
        if _already_verified(state):
            return state
        due = prepare_retry(store, state)
        if due > time.time():
            if info.get('next_retry_at') != due:
                info.update(status='retrying', next_retry_at=due,
                            error=info.get('error') or 'Drive API is cooling down after a quota response')
                state['delivery'] = info
                store.save(state, 'delivery_deferred', info)
            return state
        previous = info.get('attempts', 0)
        attempts = (previous if type(previous) is int and previous >= 0 else 0) + 1
        info['attempts'] = attempts
        info['last_attempt_at'] = time.time()
        state['delivery'] = info
        store.save(state, 'delivery_attempt_started', info)
        upload_run(store, state)
        info = state['delivery']
        info['attempts'] = attempts
        if info['status'] == 'uploaded':
            info.pop('next_retry_at', None)
            info.pop('retry_failures', None)
            info.pop('worker_error', None)
            store.save(state, 'delivery_complete', info)
        else:
            _retry(store, state)
    except Exception as exc:
        _failed(store, state, exc)
    return state
