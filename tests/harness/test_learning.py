from harness.config import load_config
from harness.store import Store


def test_feedback_retrieval_is_product_scoped_and_keeps_source(tmp_path):
    from harness.learning import feedback, lessons
    store = Store(tmp_path)
    a = store.create(load_config(overrides={'website': 'https://one.example'}))
    feedback(store, a['id'], 'bad', 'The pause before the reply felt empty.')
    assert lessons(store, a['config'])[0]['run'] == a['id']
    other = load_config(overrides={'website': 'https://two.example'})
    assert lessons(store, other) == []


def test_research_cache_expires_and_does_not_ignore_product_changes(tmp_path):
    from harness.learning import research_key, cached_research
    store = Store(tmp_path)
    c = load_config()
    s = store.create(c)
    s['research_key'] = research_key(c, [])
    s['tasks'] = [{'stage': 'research', 'status': 'succeeded', 'result': {'summary': 'facts', 'files': []}}]
    s['created'] = 100
    store.save(s, 'fixture')
    assert cached_research(store, c, [], now=101)['run'] == s['id']
    assert cached_research(store, c, [], now=100000) is None
    c['products'] = [{'name': 'new', 'description': 'different'}]
    assert cached_research(store, c, [], now=101) is None


def test_rejected_storyboards_inform_future_runs_before_final_qa(tmp_path):
    from harness.learning import lessons
    store = Store(tmp_path)
    state = store.create(load_config())
    state['status'] = 'needs_review'
    state['tasks'] = [{'id': 'ad-01-board_review', 'stage': 'board_review',
                       'status': 'needs_review', 'result': {'verdict': 'revise',
                       'findings': [{'target': 'door wedge', 'severity': 'blocking',
                                     'problem': 'Product too small to read',
                                     'fix': 'Use a visible supported product beat'}]}}]
    store.save(state, 'fixture')
    memory = lessons(store, state['config'])
    assert memory[0]['run'] == state['id']
    finding = memory[0]['review_findings'][0]
    assert finding['stage'] == 'board_review'
    assert finding['problem'] == 'Product too small to read'


def test_compact_learning_preserves_metadata_across_catalog_moves(tmp_path):
    from harness.learning import lessons, character_voices, catalog_brief
    store = Store(tmp_path)
    state = store.create(load_config())
    state.update(status='complete', asset_paths={'hero': '/old/catalog/hero.blend'},
                 user_feedback=[{'rating': 'good'}], tasks=[
        {'id': 'campaign-script', 'stage': 'script', 'result': {'scripts': [{'premise': 'A visual joke'}]}},
        {'stage': 'animate', 'result': {
            'direction': {'cast': [{'asset_id': 'hero', 'model': '/new/catalog/hero.blend',
                                    'voice': 'am_michael', 'performance': 'dry'}]},
            'used_asset_ids': ['hero']}},
        {'stage': 'edit', 'result': {'findings': [{'problem': 'Long pause', 'fix': 'Trim'}]}}])
    store.save(state, 'fixture')
    memory = lessons(store, state['config'])[0]
    assert memory['premises'] == ['A visual joke']
    assert memory['review_findings'][0]['stage'] == 'edit'
    assert character_voices(store, state['config'])['hero']['voice'] == 'am_michael'
    entries = [{'id': 'hero', 'kind': 'character', 'path': '/new/catalog/hero.blend'}]
    assert catalog_brief(store, state['config'], entries)[0]['user_reuse_score'] == 1
    # Legacy path-based identity remains readable, and transitional stages do
    # not double-count a single user's rating of an asset.
    state['tasks'][1]['stage'] = 'direct'
    cast = state['tasks'][1]['result']['direction']['cast'][0]
    cast.pop('asset_id')
    cast['model'] = '/old/catalog/hero.blend'
    state['tasks'].extend([{'stage': stage, 'result': {'used_asset_ids': ['hero']}}
                           for stage in ('assets', 'animate')])
    store.save(state, 'legacy_fixture')
    assert character_voices(store, state['config'])['hero']['voice'] == 'am_michael'
    assert catalog_brief(store, state['config'], entries)[0]['user_reuse_score'] == 1
