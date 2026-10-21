"""Concurrent provider failures cannot bring an existing reset deadline forward."""
import multiprocessing
import time

from harness.store import Store


def _shorten(root, ready):
    store = Store(root)
    ready.wait(5)
    store.cooldown('codex', 300)


def _contend(root, ready, seconds):
    store = Store(root)
    ready.wait(5)
    store.cooldown('codex', seconds)


def test_short_capacity_response_preserves_long_quota_cooldown(tmp_path):
    store = Store(tmp_path)
    store.cooldown('codex', 3600)
    ctx = multiprocessing.get_context('spawn')
    ready = ctx.Event()
    child = ctx.Process(target=_shorten, args=(str(tmp_path), ready))
    child.start()
    try:
        ready.set()
        child.join(10)
        assert child.exitcode == 0
        assert store.cooldown('codex') > 3500
    finally:
        if child.is_alive():
            child.terminate()
        child.join(5)


def test_cooldowns_extend_expire_and_explicitly_clear(tmp_path, monkeypatch):
    store = Store(tmp_path)
    monkeypatch.setattr(time, 'time', lambda: 1000)
    assert store.cooldown('codex') == 0
    assert store.cooldown('codex', 300) == 300
    assert store.cooldown('codex', 3600) == 3600
    assert store.cooldown('claude', 90) == 90
    store.clear_cooldowns('codex')
    assert store.cooldown('codex') == 0
    assert store.cooldown('claude') == 90
    monkeypatch.setattr(time, 'time', lambda: 1200)
    assert store.cooldown('claude') == 0
    assert store.cooldown('claude', 10) == 10


def test_concurrent_updates_keep_the_longest_deadline(tmp_path):
    store = Store(tmp_path)
    ctx = multiprocessing.get_context('spawn')
    ready = ctx.Barrier(4)
    children = [ctx.Process(target=_contend, args=(str(tmp_path), ready, seconds))
                for seconds in (60, 300, 3600, 86400)]
    for child in children:
        child.start()
    try:
        for child in children:
            child.join(10)
            assert child.exitcode == 0
        assert 86300 < store.cooldown('codex') <= 86400
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
            child.join(5)
