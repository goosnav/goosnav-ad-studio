"""Durable delivery retry policy, independent of generation status/budget.

Failed attempts stay queued without an attempt limit. A saved due time prevents
both production hooks and a restarted background worker from retrying in a burst.
"""
import random
import time

from .delivery import _already_verified, _completed_ads, _error, _rate_limited, upload_run


RETRY_BASE_SECONDS = 60
RETRY_MAX_SECONDS = 1800
DRIVE_COOLDOWN = 'drive-delivery'


def _retry(store, state):
    info = state['delivery']
    failures = info.get('retry_failures', 0) + 1
    # Reserve room for jitter even at the cap, so long outages don't synchronize workers.
    base = min(RETRY_MAX_SECONDS / 1.25, RETRY_BASE_SECONDS * 2 ** min(failures - 1, 5))
    delay = random.uniform(base, base * 1.25)
    info.update(status='retrying', retry_failures=failures, next_retry_at=time.time() + delay)
    if _rate_limited(info.get('error', '')):
        store.cooldown(DRIVE_COOLDOWN, delay)
    store.save(state, 'delivery_retry_scheduled', info)


def deliver_ready(store, state):
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
        due = max(info.get('next_retry_at', 0), time.time() + store.cooldown(DRIVE_COOLDOWN))
        if due > time.time():
            if info.get('next_retry_at') != due:
                info.update(status='retrying', next_retry_at=due,
                            error=info.get('error') or 'Drive API is cooling down after a quota response')
                state['delivery'] = info
                store.save(state, 'delivery_deferred', info)
            return state
        attempts = info.get('attempts', 0) + 1
        info['attempts'] = attempts
        state['delivery'] = info
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
    return state
