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
