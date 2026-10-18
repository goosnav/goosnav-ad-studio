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
    assert d['status']=='ready' and len(d['tasks'])==28
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


def test_drive_queues_behind_a_running_controller(tmp_path):
    from harness.cli import drive
    from harness.store import Store, Busy
    store = Store(tmp_path); run = store.create({'count': 1}); attempts = []; slept = []
    class Fake:
        def run(self, run_id, max_steps=None):
            attempts.append(1)
            if len(attempts) < 3:
                raise Busy('another controller')
            return {'id': run_id, 'status': 'complete'}
    assert drive(Fake(), store, run['id'], sleep=slept.append)['status'] == 'complete'
    assert len(attempts) == 3 and slept
    store.control(run['id'], 'cancel')
    class AlwaysBusy:
        def run(self, run_id, max_steps=None):
            raise Busy('another controller')
    assert drive(AlwaysBusy(), store, run['id'], sleep=slept.append)['status'] == 'cancelled'


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


def test_upload_accepts_drive_folder_link_and_uses_folder_id(tmp_path):
    from harness.delivery import upload_run
    from harness.store import Store
    store = Store(tmp_path)
    state = store.create({'delivery': {'drive': 'https://drive.google.com/drive/folders/folder123'},
                          'output': {'folder': str(tmp_path)}})
    run_folder = tmp_path / state['id']; run_folder.mkdir()
    (run_folder / 'ad-01.mp4').write_bytes(b'video')
    (run_folder / 'ad-01.zip').write_bytes(b'zip')
    state['tasks'] = [{'stage': 'package', 'status': 'succeeded', 'ad': 0}]
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        class Result: stdout = 'ad-01.mp4\nad-01.zip\n'
        return Result()
    result = upload_run(store, state, run=fake_run, which=lambda _: '/usr/bin/rclone')
    assert result['delivery']['status'] == 'uploaded'
    assert calls[0][:3] == ['rclone', '--drive-root-folder-id', 'folder123']
    assert calls[1][:3] == ['rclone', '--drive-root-folder-id', 'folder123']
    assert 'agent-exchange:' + state['id'] in calls[0]
