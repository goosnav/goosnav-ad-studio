import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def cli(tmp_path,*args):
    return subprocess.run([sys.executable,'-m','harness','--home',str(tmp_path),*args],
                          cwd=ROOT,capture_output=True,text=True)


def test_cli_minimal_plan_and_status(tmp_path):
    cfg=tmp_path/'blank.json';cfg.write_text('{}')
    r=cli(tmp_path,'make','--config',str(cfg),'--website','example.com','--count','2','--plan')
    assert r.returncode==0,r.stderr
    d=json.loads(r.stdout)
    assert d['status']=='ready' and len(d['tasks'])==11
    assert d['tasks'][0]['id'] == 'campaign-script'
    s=cli(tmp_path,'status',d['id'])
    assert json.loads(s.stdout)['config']['website']=='https://example.com'


def test_cli_unknown_run_and_invalid_input_are_clean_errors(tmp_path):
    r=cli(tmp_path,'status','../../escape')
    assert r.returncode!=0 and 'Traceback' not in r.stderr
    r=cli(tmp_path,'make','--count','0','--plan')
    assert r.returncode!=0 and 'count' in r.stderr


def test_cli_seconds_sets_target_length(tmp_path):
    cfg=tmp_path/'blank.json';cfg.write_text('{}')
    d=json.loads(cli(tmp_path,'make','--config',str(cfg),'--seconds','15','--plan').stdout)
    assert d['config']['output']['target_seconds']==15 and d['config']['output']['max_seconds']==20
    assert cli(tmp_path,'make','--config',str(cfg),'--seconds','0','--plan').returncode==2


def test_drive_waits_for_provider_reset_then_continues(tmp_path):
    from harness.cli import drive
    from harness.store import Store
    store = Store(tmp_path); outcomes = ['waiting_provider', 'complete']; slept = []
    class Fake:
        def run(self, run_id, max_steps=None):
            status = outcomes.pop(0)
            if status == 'waiting_provider':
                store.cooldown('claude', 90)
            return {'id': run_id, 'status': status}
    run = store.create({'count': 1})
    assert drive(Fake(), store, run['id'], wait=True, sleep=slept.append)['status'] == 'complete'
    assert 0 < sum(slept) <= 91
    outcomes[:] = ['waiting_provider']
    with store.connect() as db:
        db.execute('DELETE FROM cooldowns')
    class NoCooldown(Fake):
        def run(self, run_id, max_steps=None):
            return {'id': run_id, 'status': 'waiting_provider'}
    assert drive(NoCooldown(), store, run['id'], wait=True, sleep=slept.append)['status'] == 'waiting_provider'


def test_drive_queues_behind_a_running_controller(tmp_path, capsys):
    from harness.cli import drive
    from harness.store import Store, Busy
    store = Store(tmp_path); run = store.create({'count': 1}); attempts = []; slept = []
    class Fake:
        def run(self, run_id, max_steps=None):
            attempts.append(1)
            if len(attempts) < 3:
                raise Busy('Another controller owns this workspace; status/pause/cancel still work')
            return {'id': run_id, 'status': 'complete'}
    assert drive(Fake(), store, run['id'], sleep=slept.append)['status'] == 'complete'
    assert len(attempts) == 3 and slept
    assert 'Controller queued: Another controller owns this workspace' in capsys.readouterr().err
    store.control(run['id'], 'cancel')
    before = store.get(run['id'])
    events = store.events(run['id'])
    class AlwaysBusy:
        def run(self, run_id, max_steps=None):
            raise Busy('another controller')
    assert drive(AlwaysBusy(), store, run['id'], sleep=slept.append)['status'] == 'cancelled'
    assert store.get(run['id']) == before
    assert store.events(run['id']) == events


def test_quick_launch_same_second_keeps_logs_and_explicit_run_controls(tmp_path, monkeypatch, capsys):
    import runpy
    start = runpy.run_path(str(ROOT / 'ad'))['start']
    monkeypatch.setitem(start.__globals__, 'HOME', tmp_path)
    monkeypatch.setattr(start.__globals__['time'], 'strftime', lambda *_: '20261020-154021')
    monkeypatch.setattr(start.__globals__['time'], 'sleep', lambda *_: None)
    logs = []
    def launch(command, **kwargs):
        out = kwargs['stdout']
        logs.append(Path(out.name))
        run_id = f'run-{len(logs)}'
        out.write(f'Run {run_id} — inspect with status\n')
        out.write('Controller queued: Another controller owns this workspace; status/pause/cancel still work\n')
        assert kwargs['start_new_session'] is True
    monkeypatch.setattr(start.__globals__['subprocess'], 'Popen', launch)
    for index in (1, 2):
        start('make', '--concept', f'film {index}')
        output = capsys.readouterr().out
        assert f'Queued run-{index}' in output
        for control in ('watch', 'status', 'pause'):
            assert f'./ad {control} run-{index}' in output
        assert 'owns this workspace' in output
    assert logs[0] != logs[1]
    assert 'Run run-1' in logs[0].read_text()
    assert 'Run run-2' in logs[1].read_text()
    start('resume', 'saved-run')
    output = capsys.readouterr().out
    assert 'Queued saved-run' in output
    assert './ad watch saved-run' in output


def test_cli_requests_compact_graph_without_launching_agents(tmp_path, monkeypatch, capsys):
    import harness.cli as module
    calls = []
    def build(count, *, modern, compact):
        calls.append((count, modern, compact))
        return [{'id': 'campaign-script', 'stage': 'script', 'status': 'pending'}]
    monkeypatch.setattr(module, 'build_tasks', build)
    cfg = tmp_path / 'blank.json'
    cfg.write_text('{}')
    assert module.main(['--home', str(tmp_path / 'state'), 'make', '--config', str(cfg),
                        '--count', '2', '--plan']) == 0
    assert calls == [(2, True, True)]
    assert json.loads(capsys.readouterr().out)['tasks'][0]['id'] == 'campaign-script'


def test_ad_status_explains_waiting_provider_and_watch_finishes(tmp_path):
    from harness.config import load_config
    from harness.store import Store
    from harness.workflow import build_tasks
    store = Store(tmp_path)
    state = store.create(load_config())
    state['tasks'] = build_tasks(1)
    state['status'] = 'waiting_provider'
    task = state['tasks'][0]
    task['status'] = 'waiting_provider'
    task['feedback'] = 'codex (auto:balanced): model catalog unavailable; claude: usage limit'
    store.save(state, 'fixture')

    env = {**os.environ, 'STUDIO_HARNESS_HOME': str(store.root)}
    for action in ('status', 'watch'):
        result = subprocess.run([sys.executable, str(ROOT / 'ad'), action, state['id']],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert 'Provider blockers:' in result.stdout
        assert 'model catalog unavailable' in result.stdout
        assert './ad resume ' in result.stdout


def test_cli_can_clear_stale_provider_cooldowns(tmp_path):
    from harness.store import Store
    store = Store(tmp_path)
    store.cooldown('codex', 3600)
    store.cooldown('claude', 3600)
    result = cli(tmp_path, 'cooldown', 'clear', 'codex')
    assert result.returncode == 0
    assert store.cooldown('codex') == 0
    assert store.cooldown('claude') > 0
    assert json.loads(cli(tmp_path, 'cooldown', 'status').stdout) == {
        'codex': 0, 'claude': round(store.cooldown('claude'))}


def test_ad_status_shows_source_failure_before_a_worker_started(tmp_path):
    from harness.config import load_config
    from harness.store import Store
    from harness.workflow import build_tasks
    store = Store(tmp_path)
    state = store.create(load_config())
    state.update(tasks=build_tasks(1), status='failed', error='ContractError: Missing configured source: old/README.md')
    store.save(state, 'fixture')
    env = {**os.environ, 'STUDIO_HARNESS_HOME': str(store.root)}
    result = subprocess.run([sys.executable, str(ROOT / 'ad'), 'status', state['id']],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert 'Missing configured source: old/README.md' in result.stdout


def test_upload_accepts_drive_folder_link_and_uses_folder_id(tmp_path):
    from harness.delivery import upload_run
    from harness.store import Store
    from tests.harness.test_delivery import Drive
    store = Store(tmp_path)
    state = store.create({'delivery': {'drive': 'https://drive.google.com/drive/folders/folder123'},
                          'output': {'folder': str(tmp_path)}})
    run_folder = tmp_path / state['id']; run_folder.mkdir()
    (run_folder / 'ad-01.mp4').write_bytes(b'video')
    (run_folder / 'ad-01.zip').write_bytes(b'zip')
    state['tasks'] = [{'stage': 'package', 'status': 'succeeded', 'ad': 0}]
    transport = Drive()
    result = upload_run(store, state, run=transport, which=lambda _: '/usr/bin/rclone')
    calls = transport.calls
    assert result['delivery']['status'] == 'uploaded'
    assert calls[0][:3] == ['rclone', '--drive-root-folder-id', 'folder123']
    assert all(call[:3] == ['rclone', '--drive-root-folder-id', 'folder123'] for call in calls)
    assert calls[0][-1].startswith('agent-exchange:ad-video-')
    assert calls[0][-1].endswith('-ad-01.mp4')
    assert '--stat' in calls[1] and '--hash' in calls[1]
    assert 'agent-exchange:' in calls[2]
    assert '--files-only' in calls[2]


def test_manual_upload_cannot_overwrite_a_running_controllers_state(tmp_path):
    from harness.store import Store
    from harness.config import load_config
    store = Store(tmp_path)
    state = store.create(load_config())
    state.update(status='running', tasks=[{'id': 'still-rendering', 'stage': 'animate',
                                         'status': 'running', 'ad': 0}])
    store.save(state, 'fixture')
    with store.worker_lock(state['id']):
        state['tasks'][0]['status'] = 'succeeded'
        store.save(state, 'advanced')
        result = cli(tmp_path, 'upload', state['id'])
    assert result.returncode != 0
    assert 'Another' in result.stderr or 'worker' in result.stderr.lower()
    assert store.get(state['id'])['tasks'][0]['status'] == 'succeeded'
    assert 'delivery' not in store.get(state['id'])


def test_explicit_resume_reopens_failures_but_preserves_success_and_review_gates():
    from harness.cli import reopen
    error = "TypeError: unsupported operand type(s) for +: 'dict' and 'int'"
    state = {'error': error, 'tasks': [
        {'status': 'failed', 'feedback': error},
        {'status': 'failed', 'feedback': 'Previous claude attempt: invalid. Missing result.json'},
        {'status': 'cancelled', 'feedback': ''},
        {'status': 'succeeded', 'feedback': ''}, {'status': 'needs_review', 'feedback': 'blocking finding'}]}
    assert [t['status'] for t in reopen(state)['tasks']] == [
        'pending', 'pending', 'pending', 'succeeded', 'needs_review']
    assert state['tasks'][1]['revision'] == 1


def test_render_controller_starts_detached_delivery_worker(tmp_path, monkeypatch):
    from harness import delivery_queue
    from harness.cli import drive
    from tests.harness.test_delivery import fixture
    store, state, _ = fixture(tmp_path)
    started = []
    monkeypatch.setattr(delivery_queue, 'ensure_worker', lambda s: started.append(s.root))
    class Finished:
        def run(self, run_id, max_steps=None):
            assert started == [store.root]  # Worker is armed before rendering can finish or crash.
            return store.get(run_id)
    store.save(state, 'fixture')
    drive(Finished(), store, state['id'])


def test_status_reports_retry_time_error_and_worker_health(tmp_path, capsys, monkeypatch):
    import runpy
    import time
    from harness import delivery_queue
    from tests.harness.test_delivery import fixture
    store, state, _ = fixture(tmp_path)
    state.update(status='complete', delivery={'status': 'retrying', 'attempts': 3,
                 'next_retry_at': time.time() + 120, 'error': 'rateLimitExceeded'})
    module = runpy.run_path(str(ROOT / 'ad'))
    summary = module['summary']
    monkeypatch.setitem(summary.__globals__, 'harness', lambda *args: state)
    monkeypatch.setitem(summary.__globals__, 'HOME', store.root)
    monkeypatch.setattr(delivery_queue, 'worker_running', lambda _: True)
    assert summary(state['id']) == 'waiting_delivery'  # watch must not stop at render completion.
    output = capsys.readouterr().out
    assert 'automatic retry' in output.lower()
    assert 'attempt 3' in output.lower()
    assert 'rateLimitExceeded' in output
    assert 'worker running' in output.lower()
    store.control(state['id'], 'pause')
    assert summary(state['id']) == 'complete'
    assert 'retries paused' in capsys.readouterr().out.lower()


def test_watch_does_not_exit_while_background_attempt_is_uploading(tmp_path, monkeypatch):
    import runpy
    from tests.harness.test_delivery import fixture
    store, state, _ = fixture(tmp_path)
    state.update(status='complete', delivery={'status': 'uploading', 'verified': {}})
    summary = runpy.run_path(str(ROOT / 'ad'))['summary']
    monkeypatch.setitem(summary.__globals__, 'harness', lambda *args: state)
    monkeypatch.setitem(summary.__globals__, 'HOME', store.root)
    assert summary(state['id']) == 'waiting_delivery'
