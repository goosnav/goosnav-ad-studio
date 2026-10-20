"""Best-effort delivery at production boundaries, independent of run status."""
from .delivery import _already_verified, _error, upload_run


def deliver_ready(store, state):
    """Deliver newly packaged or failed pending videos; never fail production.

    The caller owns when this runs and excludes delivery time from its production
    budget. Mutate and return the supplied snapshot, as upload_run does.
    """
    try:
        config = state['config']
        if (not config.get('delivery', {}).get('drive', '').strip()
                or not config.get('output', {}).get('folder')
                or not any(t['stage'] == 'package' and t['status'] == 'succeeded'
                           for t in state['tasks'])):
            return state
        if not _already_verified(state):
            upload_run(store, state)
    except Exception as exc:
        info = state.get('delivery')
        if not isinstance(info, dict):
            info = state['delivery'] = {}
        info.update(status='failed', error=_error(exc))
        try:
            store.save(state, 'delivery_failed', info)
        except Exception:
            # A broken state backend cannot make delivery fatal to rendering.
            # Keep the failed receipt in memory for the caller's next save.
            pass
    return state
