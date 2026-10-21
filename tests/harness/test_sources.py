from pathlib import Path

from harness.config import load_config
from harness.store import Store
from harness.workflow import Engine

from test_workflow import fake_models, research_result


def test_run_recovers_moved_character_and_skips_missing_inspiration(tmp_path):
    library = tmp_path / 'library'
    current = library / 'ps1guy' / 'astronaut.blend'
    current.parent.mkdir(parents=True)
    current.write_bytes(b'character fixture')
    config = load_config(None, {'sources': {
        'assets': [str(library)],
        'characters': [str(library / 'old' / 'astronaut.blend')],
        'inspiration': [str(library / 'characters' / 'README.md')]}})
    store = Store(tmp_path / 'state'); run = store.create(config)
    def worker(profile, work, *args, **kwargs):
        research_result(work)
        return {'kind': 'ok'}
    state = Engine(store, execute=worker, resolve=fake_models, auth=lambda _: True).run(
        run['id'], max_steps=1)
    assert state['tasks'][0]['status'] == 'succeeded', state.get('error')
    assert state['config']['sources']['characters'] == [str(current)]
    assert state['config']['sources']['inspiration'] == []
    assert {w['kind'] for w in state['source_warnings']} == {'relocated', 'unavailable'}
    assert 'sources_reconciled' in [e['kind'] for e in store.events(run['id'])]
    assert store.get(run['id'])['config']['sources']['characters'] == [str(current)]


def test_optional_reference_disappearing_does_not_break_frozen_snapshot_on_resume(tmp_path):
    inspiration = tmp_path / 'inspiration.txt'; inspiration.write_text('Original direction')
    config = load_config(None, {'sources': {'inspiration': [str(inspiration)]}})
    store = Store(tmp_path / 'state'); run = store.create(config)
    engine = Engine(store, execute=lambda *a, **k: None, resolve=fake_models, auth=lambda _: True)
    first = engine.run(run['id'], max_steps=0)
    frozen = Path(first['sources'][0]['text'])
    inspiration.unlink()
    resumed = engine.run(run['id'], max_steps=0)
    assert resumed['status'] == 'ready'
    assert frozen.read_text() == 'Original direction'
    assert resumed['sources'] == first['sources']


def test_ambiguous_or_archived_character_is_not_silently_substituted(tmp_path):
    library = tmp_path / 'library'
    for folder in ('first', 'second', 'archive'):
        path = library / folder / 'actor.blend'
        path.parent.mkdir(parents=True); path.write_bytes(b'fixture')
    config = load_config(None, {'sources': {'assets': [str(library)],
        'characters': [str(library / 'old' / 'actor.blend')]}})
    store = Store(tmp_path / 'state'); run = store.create(config)
    state = Engine(store, execute=lambda *a, **k: None, resolve=fake_models).run(run['id'])
    assert state['status'] == 'failed'
    assert 'No usable configured characters' in state['error']
    assert not state['models']  # Fail before spending worker quota.


def test_missing_brand_document_remains_a_blocker(tmp_path):
    config = load_config(None, {'brand': {'documents': [str(tmp_path / 'brand.txt')]}})
    store = Store(tmp_path / 'state'); run = store.create(config)
    state = Engine(store, execute=lambda *a, **k: None, resolve=fake_models).run(run['id'])
    assert state['status'] == 'failed'
    assert 'Missing configured source' in state['error']


def test_existing_archived_character_is_excluded_even_if_configured(tmp_path):
    from harness.sources import reconcile_sources
    library = tmp_path / 'library'
    current = library / 'current.blend'; retired = library / 'archive' / 'bad.blend'
    retired.parent.mkdir(parents=True)
    current.write_bytes(b'current'); retired.write_bytes(b'retired')
    config = load_config(None, {'sources': {'assets': [str(library)],
        'characters': [str(current), str(retired)]}})
    warnings = reconcile_sources(config)
    assert config['sources']['characters'] == [str(current)]
    assert warnings[0]['reason'] == 'archived asset excluded'


def test_missing_character_does_not_relocate_to_unique_archived_model(tmp_path):
    from harness.sources import reconcile_sources
    library = tmp_path / 'library'
    current = library / 'current.blend'; retired = library / 'archive' / 'bad.blend'
    retired.parent.mkdir(parents=True)
    current.write_bytes(b'current'); retired.write_bytes(b'retired')
    config = load_config(None, {'sources': {'assets': [str(library)],
        'characters': [str(current), str(library / 'bad.blend')]}})
    reconcile_sources(config)
    assert config['sources']['characters'] == [str(current)]


def test_character_symlink_cannot_reintroduce_an_archived_model(tmp_path):
    from harness.sources import reconcile_sources
    library = tmp_path / 'library'
    current = library / 'current.blend'; retired = library / 'archive' / 'bad.blend'
    retired.parent.mkdir(parents=True)
    current.write_bytes(b'current'); retired.write_bytes(b'retired')
    alias = library / 'alias.blend'; alias.symlink_to(retired)
    config = load_config(None, {'sources': {'assets': [str(library)],
        'characters': [str(current), str(alias)]}})
    reconcile_sources(config)
    assert config['sources']['characters'] == [str(current)]


def test_resume_replans_an_accepted_direction_using_retired_characters(tmp_path):
    from harness.workflow import build_tasks
    library = tmp_path / 'library'; library.mkdir()
    current = library / 'current.blend'; current.write_bytes(b'current')
    config = load_config(None, {'sources': {'assets': [str(library)], 'characters': [str(current)]}})
    store = Store(tmp_path / 'state'); run = store.create(config)
    run['tasks'] = build_tasks(1)
    # Frozen plans are not safe to reuse merely because their JSON was accepted
    # before the model was retired. Preserve the campaign and redo production.
    for task in run['tasks']:
        if task['ad'] is None:
            task.update(status='succeeded', result={'files': []})
        if task['stage'] == 'direct':
            task.update(status='succeeded', result={'files': [], 'direction': {'cast': [
                {'speaker': 'A', 'model': str(library / 'archive' / 'retired.blend')}]}})
    store.save(run, 'fixture')
    engine = Engine(store, execute=lambda *a, **k: None, resolve=fake_models)
    state = engine.run(run['id'], max_steps=0)
    direct = next(t for t in state['tasks'] if t['stage'] == 'direct')
    assert direct['status'] == 'pending'
    assert 'retired' in direct['feedback']
    assert all(t['status'] == 'succeeded' for t in state['tasks'] if t['ad'] is None)
