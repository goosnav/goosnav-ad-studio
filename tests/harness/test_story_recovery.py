"""Recovery must finish the story, never replace it with its end card."""
import json
from pathlib import Path
import subprocess

import pytest

from harness.config import load_config
from harness.contracts import ContractError
from harness.execution import Budget, policy
from harness.store import Store
from harness.workflow import Engine, build_tasks


def story_run(tmp_path):
    store = Store(tmp_path/'home')
    c = load_config(overrides={'output': {'target_seconds': 9, 'folder': str(tmp_path/'out'),
        'end_card_clips': [{'product': 'Example Book', 'asset_id': 'book-floating'}]}})
    s = store.create(c); s['tasks'] = build_tasks(1, modern=True)
    for t in s['tasks']:
        if t['stage'] in ('research', 'write', 'select', 'direct', 'audio'):
            t.update(status='succeeded', result={'files': []})
    next(t for t in s['tasks'] if t['stage'] == 'write')['result']['scripts'] = [
        {'id': 's1', 'title': 'Story', 'product': 'Example Book'}]
    next(t for t in s['tasks'] if t['stage'] == 'select')['result']['selected'] = ['s1']
    next(t for t in s['tasks'] if t['stage'] == 'direct')['result']['direction'] = {'cast': []}
    s['execution']['active_seconds'] = 970
    return store, s


def test_deadline_recovery_keeps_story_pipeline_instead_of_publishing_a_card(tmp_path):
    store, s = story_run(tmp_path)
    engine = Engine(store); engine.budget = Budget(s, store.save)
    before = {t['stage']: t['result'] for t in s['tasks'] if t['status'] == 'succeeded'}
    assert engine.finish_pending(s, 'deadline') is True
    assert s['status'] == 'ready'
    assert s['execution']['finishing'] is True
    assert all(t['status'] == 'pending' for t in s['tasks'] if t['stage'] in ('animate', 'edit', 'frame', 'qa', 'package'))
    assert {t['stage']: t['result'] for t in s['tasks'] if t['status'] == 'succeeded'} == before
    assert not list(tmp_path.rglob('*.mp4'))
    assert engine.finish_pending(s, 'again') is False  # one bounded finishing pass, not a retry reset


def test_finishing_uses_existing_remaining_budget_not_a_second_cutoff(tmp_path):
    store, s = story_run(tmp_path)
    s['execution']['finishing'] = True
    b = Budget(s, store.save)
    b.check_production()
    assert 529 < b.production_remaining() <= 530
    assert s['execution']['hard_seconds'] == 1500


@pytest.mark.parametrize('blocked', [False, True])
def test_engine_runs_story_stages_in_one_bounded_finishing_pass(tmp_path, monkeypatch, blocked):
    from test_workflow import fake_models
    store, s = story_run(tmp_path)
    s.update(sources=[], sources_ready=True)
    next(t for t in s['tasks'] if t['stage'] == 'edit')['attempts'] = [
        {'kind':'invalid','revision':0,'started':0,'detail':'Wrong final resolution'}]
    store.save(s, 'fixture')
    engine = Engine(store, execute=lambda *a, **k: None, resolve=fake_models)
    stages = []
    def step(state, task, root):
        stages.append(task['stage'])
        task.update(status='failed' if blocked else 'succeeded', result={'files': [], 'verdict': 'pass'})
    def model_step(state,task,root):
        assert task['stage'] != 'edit', 'Do not spend a model retry on a mechanical identity edit'
        step(state,task,root)
    monkeypatch.setattr(engine, 'agent_task', model_step)
    monkeypatch.setattr(engine, 'builtin_task', step)
    result = engine.run(s['id'])
    if blocked:
        assert result['status'] == 'failed'
        assert stages == ['assets']
        assert not any(t['stage'] == 'package' and t['status'] == 'succeeded' for t in result['tasks'])
    else:
        assert result['status'] == 'complete'
        assert stages == ['assets','board_review','animate','edit','frame','qa','creative_qa','package']
    assert result['execution']['hard_seconds'] == 1500
    assert len([change for change in result['execution']['changes'] if change['reason'] != 'reserve finishing time']) == 1


def test_old_product_only_package_is_not_uploadable_or_complete(tmp_path):
    from harness.delivery import _completed_ads, upload_run
    from harness.delivery_queue import _pending
    store, s = story_run(tmp_path)
    s['config']['delivery']['drive'] = 'remote:ads'
    package = next(t for t in s['tasks'] if t['stage'] == 'package')
    package.update(status='succeeded', result={'delivery_mode': 'product_only',
        'files': [{'path': str(tmp_path/'card.mp4'), 'kind': 'video'}]})
    assert _completed_ads(s) == []
    assert _pending(s) is False
    assert Engine(store).aggregate(s) != 'complete'
    from harness.gui import videos
    assert videos(s) == []
    result = upload_run(store, s, run=lambda *a, **k: pytest.fail('must not contact Drive'))
    assert result['delivery']['status'] == 'failed'


def test_resume_reopens_skipped_story_stages_without_deleting_old_receipts(tmp_path):
    store, s = story_run(tmp_path)
    for t in s['tasks']:
        if t['ad'] == 0 and t['status'] == 'pending':
            t['status'] = 'skipped'
    package = next(t for t in s['tasks'] if t['stage'] == 'package')
    package.update(status='succeeded', result={'delivery_mode': 'product_only', 'files': []})
    s['delivery'] = {'status': 'uploaded', 'verified': {'ad-01.mp4': {'sha256': 'old'}}}
    engine = Engine(store); engine.budget = Budget(s, store.save)
    engine.reconcile(s)
    assert package['status'] != 'succeeded'
    assert all(t['status'] == 'pending' for t in s['tasks'] if t['stage'] in ('assets', 'animate', 'edit', 'frame'))
    assert s['delivery']['verified']['ad-01.mp4']['sha256'] == 'old'


@pytest.mark.parametrize('start', [0, .2, None])
def test_story_gate_rejects_end_card_for_entire_film(tmp_path, start):
    from harness.media import check_story_content
    c = load_config(overrides={'output': {'target_seconds': 9}})
    with pytest.raises(ContractError, match='story|end.card'):
        check_story_content(tmp_path/'card.mp4', tmp_path/'story.mp4', {'end_card_start': start}, c)


def test_story_gate_checks_picture_before_short_closing_card(tmp_path):
    from harness.media import check_story_content
    tools = ['ffmpeg', '-v', 'error', '-y']
    source, good, bad = (tmp_path/n for n in ('story.mp4','good.mp4','card-only.mp4'))
    subprocess.run([*tools, '-f', 'lavfi', '-i', 'testsrc2=s=108x136:r=24',
                    '-t', '4', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)], check=True)
    subprocess.run([*tools, '-i', str(source), '-vf', "drawbox=y=0:w=iw:h=ih:color=white:t=fill:enable='gte(t,2)'",
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(good)], check=True)
    subprocess.run([*tools, '-f', 'lavfi', '-i', 'color=white:s=108x136:r=24',
                    '-t', '4', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(bad)], check=True)
    c = load_config(overrides={'output': {'width':108,'height':136,'target_seconds':4,'min_seconds':4,'max_seconds':4}})
    assert check_story_content(good, source, {'end_card_start': 2}, c)['story_seconds'] == 2
    with pytest.raises(ContractError, match='[Ss]tory'):
        check_story_content(bad, source, {'end_card_start': 2}, c)
    early = tmp_path/'early-card.mp4'
    subprocess.run([*tools, '-i', str(source), '-vf', "drawbox=y=0:w=iw:h=ih:color=white:t=fill:enable='gte(t,1.7)'",
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(early)], check=True)
    with pytest.raises(ContractError, match='[Ss]tory'):
        check_story_content(early, source, {'end_card_start': 2}, c)


def test_explicitly_skipped_cta_keeps_and_checks_the_whole_story(tmp_path):
    from harness.media import check_story_content
    source = tmp_path/'story.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=108x136:r=24',
                    '-t','2','-c:v','libx264','-pix_fmt','yuv420p',str(source)], check=True)
    c = load_config(overrides={'output': {'target_seconds':2,'min_seconds':2,'max_seconds':2}})
    report = check_story_content(source, source, {'cta_skipped': True, 'end_card_start': None}, c)
    assert report['story_seconds'] == 2


def test_pending_rejection_is_processed_before_deadline_packaging(tmp_path, monkeypatch):
    store, s = story_run(tmp_path)
    for t in s['tasks']:
        if t['ad'] == 0 and t['stage'] != 'package':
            t.update(status='succeeded', result={'files': []})
    next(t for t in s['tasks'] if t['stage'] == 'direct')['result']['direction'] = {'cast': []}
    review = next(t for t in s['tasks'] if t['stage'] == 'creative_qa')
    review['result'].update(verdict='revise', restart='assets', findings=[
        {'severity':'blocking','target':'shot','problem':'missing payoff','fix':'restore reaction'}])
    engine = Engine(store); engine.budget = Budget(s, store.save)
    monkeypatch.setattr(engine, 'builtin_task', lambda *a, **k: pytest.fail('rejected film cannot be packaged'))
    engine.finish_pending(s, 'deadline')
    assert next(t for t in s['tasks'] if t['stage'] == 'assets')['status'] == 'pending'
    assert next(t for t in s['tasks'] if t['stage'] == 'package')['status'] == 'pending'


def test_finishing_review_cannot_rewind_accepted_direction_and_audio(tmp_path):
    store, s = story_run(tmp_path)
    s['execution']['finishing'] = True
    review = next(t for t in s['tasks'] if t['stage'] == 'board_review')
    review.update(status='succeeded', result={'files': [], 'verdict':'revise','restart':'direct',
        'findings':[{'severity':'blocking','target':'plan','problem':'bad premise','fix':'rewrite'}]})
    Engine(store).review_transition(s, review)
    assert review['status'] == 'failed'
    assert all(t['status'] == 'succeeded' for t in s['tasks'] if t['stage'] in ('direct','audio'))


@pytest.mark.parametrize('with_card', [True, False])
@pytest.mark.parametrize('codec', ['libx264','mpeg4'])
def test_finishing_reuses_whole_animation_without_an_editor_model(tmp_path, with_card, codec):
    from harness.contracts import digest
    store, s = story_run(tmp_path)
    s['execution']['finishing'] = True
    s['config']['output'].update(width=108,height=136,target_seconds=4,min_seconds=4,max_seconds=4)
    s['config']['output']['cta'] = with_card
    for t in s['tasks']:
        if t['ad'] == 0 and t['stage'] in ('assets','board_review','animate'):
            t.update(status='succeeded', result={'files': [],'verdict':'pass'})
    source = tmp_path/'animation.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=108x136:r=24',
        '-f','lavfi','-i','sine=frequency=300:sample_rate=48000','-t','4','-c:v',codec,
        '-pix_fmt','yuv420p','-c:a','aac',str(source)],check=True)
    timeline = tmp_path/'timeline.json'
    timeline.write_text(json.dumps({'fps':24,'sample_rate':48000,'duration':4,'dialogue':[],
                                   'events':[],'sound_rationale':'Preserved accepted mix'}))
    next(t for t in s['tasks'] if t['stage'] == 'animate')['result'].update(preview=str(source),
        files=[{'path':str(source),'sha256':digest(source),'kind':'video'}])
    next(t for t in s['tasks'] if t['stage'] == 'audio')['result'].update(timeline=str(timeline),
        files=[{'path':str(timeline),'sha256':digest(timeline),'kind':'timeline'}])
    next(t for t in s['tasks'] if t['stage'] == 'direct')['result']['direction'].update(
        duration=4,mix='Preserve accepted mix')
    if with_card:
        next(t for t in s['tasks'] if t['stage'] == 'direct')['result']['direction']['end_card'] = {'seconds':2}
    task = next(t for t in s['tasks'] if t['stage'] == 'edit')
    engine = Engine(store); engine.budget = Budget(s, store.save)
    engine.builtin_task(s, task, store.path(s['id']))
    assert task['status'] == 'succeeded',task['feedback']
    if codec == 'libx264':
        assert Path(task['result']['master']).read_bytes() == source.read_bytes()
    else:
        from harness.media import check_video
        assert check_video(task['result']['master'],s['config'])['codec'] == 'h264'
    assert json.loads(Path(task['result']['timeline']).read_text()) == json.loads(timeline.read_text())
    assert task['result']['plan']['segments'][-1]['end'] == 4


def test_finishing_does_not_schedule_unstarted_other_ads(tmp_path):
    store, s = story_run(tmp_path)
    s['config']['count'] = 2
    s['tasks'] += [t for t in build_tasks(2,modern=True) if t['ad'] == 1]
    engine = Engine(store); engine.budget = Budget(s,store.save)
    assert engine.finish_pending(s,'deadline') is True
    for t in s['tasks']:
        if t['ad'] == 0:
            t.update(status='succeeded',result={'files':[]})
    assert engine.next_task(s) is None
    assert all(t['status']=='pending' for t in s['tasks'] if t['ad'] == 1)


def test_finishing_leaves_an_adequate_final_review_attempt(tmp_path):
    store, s = story_run(tmp_path)
    s['execution'].update(finishing=True,active_seconds=1400)
    for t in s['tasks']:
        if t['stage'] not in ('creative_qa','package'):
            t['status']='succeeded'
    review=next(t for t in s['tasks'] if t['stage']=='creative_qa')
    b=Budget(s,store.save)
    assert 59.5 <= b.stage_seconds(review,300) <= 100
