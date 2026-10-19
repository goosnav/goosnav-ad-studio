import json
import os
import sys

from harness.workers import command, classify, worker_env, supervise
from harness.workers import session_metadata


def test_explicit_models_and_no_shell(tmp_path):
    task = tmp_path / 'task'; task.mkdir()
    a = command({'provider': 'codex', 'model': 'gpt-6-luna', 'effort': 'low'}, task)
    assert a[a.index('-m') + 1] == 'gpt-6-luna'
    # Owner decision: workers need unsandboxed, prompt-free access (Blender, renders, caches).
    assert '--dangerously-bypass-approvals-and-sandbox' in a and '-s' not in a
    b = command({'provider': 'claude', 'model': 'haiku'}, task)
    assert b[b.index('--model') + 1] == 'haiku'
    assert '--dangerously-skip-permissions' in b and '--permission-mode' not in b


def test_subscription_environment():
    env = worker_env({'OPENAI_API_KEY': 'secret', 'ANTHROPIC_API_KEY': 'secret',
        'ANTHROPIC_BASE_URL': 'https://gateway', 'PATH': '/bin', 'CLAUDECODE': '1'})
    assert 'OPENAI_API_KEY' not in env and 'ANTHROPIC_API_KEY' not in env
    assert 'ANTHROPIC_BASE_URL' not in env and 'CLAUDECODE' not in env
    assert env['PATH'] == '/bin'


def test_error_classification():
    assert classify(1, 'You have hit your usage limit') == 'quota'
    assert classify(1, 'context window exceeded') == 'context'
    assert classify(1, 'authentication failed') == 'auth'
    assert classify(1, 'permission denied') == 'permission'
    assert classify(1, 'Unknown model: model-x') == 'model'
    assert classify(1, 'The model is not available') == 'model'
    assert classify(0, 'hello') == 'ok'
    assert classify(0, '{"type":"result","is_error":true,"result":"rate limit exceeded"}') == 'quota'
    assert classify(1, '{"type":"error","error":{"code":"token_expired","message":"Please log in again"}}') == 'auth'
    assert classify(1, "You've hit your limit · resets tomorrow") == 'quota'


def test_actual_claude_model_recorded_from_stream(tmp_path):
    p=tmp_path/'session.jsonl';p.write_text('\n'.join([
        json.dumps({'type':'system','subtype':'init','model':'claude-future-version','session_id':'s1'}),
        json.dumps({'type':'result','modelUsage':{'claude-future-version':{'inputTokens':12}}})]))
    m=session_metadata(p)
    assert m['observed_models']==['claude-future-version']
    assert m['session_id']=='s1'


def test_timeout_terminates_process(tmp_path):
    result = supervise([sys.executable, '-c', 'import time; time.sleep(30)'],
        cwd=tmp_path, prompt='', log=tmp_path/'log', timeout=.15, cancelled=lambda: False)
    assert result['kind'] == 'timeout'


def test_cancel_terminates_process(tmp_path):
    result = supervise([sys.executable, '-c', 'import time; time.sleep(30)'],
        cwd=tmp_path, prompt='', log=tmp_path/'log', timeout=10, cancelled=lambda: True)
    assert result['kind'] == 'cancelled'


def test_subscription_session_limits_are_quota():
    line = json.dumps({'type': 'result', 'is_error': True, 'api_error_status': 429,
                       'result': "You've hit your session limit · resets 5:40pm (America/Los_Angeles)"})
    assert classify(1, line) == 'quota'
    assert classify(1, "You've hit your session limit") == 'quota'


def test_reset_time_becomes_cooldown():
    from datetime import datetime
    from harness.workers import reset_delay
    now = datetime(2026, 10, 15, 17, 0)
    assert reset_delay('session limit · resets 5:40pm (America/Los_Angeles)', now) == 40 * 60 + 60
    assert reset_delay('try again at 4:24 PM.', now) == (23 * 60 + 24) * 60 + 60   # tomorrow
    assert reset_delay('usage limit, no time given', now) is None
    weekly = 'purchase more credits or try again at Oct 22nd, 2026 11:24 AM.'
    assert reset_delay(weekly, now) == int((datetime(2026, 10, 22, 11, 24) - now).total_seconds()) + 60


def test_idle_timeout_terminates_a_silent_worker(tmp_path):
    result = supervise([sys.executable, '-c', 'import time; time.sleep(30)'],
        cwd=tmp_path, prompt='', log=tmp_path/'log', timeout=5,
        idle_timeout=.25, cancelled=lambda: False)
    assert result['kind'] == 'idle_timeout'
    assert 'idle_timeout' in result['detail']


def test_active_logs_prevent_false_idle_timeout(tmp_path):
    program = ('import sys,time; '
               '[(sys.stdout.write("ping\\n"),sys.stdout.flush(),time.sleep(.08)) for _ in range(7)]')
    result = supervise([sys.executable, '-c', program],
        cwd=tmp_path, prompt='', log=tmp_path/'log', timeout=5,
        idle_timeout=.25, cancelled=lambda: False)
    assert result['kind'] == 'ok'


def test_codex_login_status_accepts_chatgpt_variants(monkeypatch):
    from types import SimpleNamespace
    from harness.workers import subscription_status

    for phrase in ('Logged in using ChatGPT', 'Logged in via chatgpt', 'CHATGPT authenticated'):
        monkeypatch.setattr('harness.workers.subprocess.run', lambda *a, **k: SimpleNamespace(
            returncode=0, stdout=phrase, stderr=''))
        assert subscription_status('codex') is True
    monkeypatch.setattr('harness.workers.subprocess.run', lambda *a, **k: SimpleNamespace(
        returncode=0, stdout='Logged in using an API key', stderr=''))
    assert subscription_status('codex') is False


def test_cli_default_codex_preserves_chatgpt_auth_without_pinning_model(tmp_path):
    from harness.workers import CODEX_CLI_DEFAULT
    argv = command({'provider': 'codex', 'model': CODEX_CLI_DEFAULT}, tmp_path)
    assert '--ignore-user-config' in argv
    assert 'forced_login_method="chatgpt"' in argv
    assert '--json' in argv
    assert '-m' not in argv
    assert 'model_reasoning_effort' not in str(argv)


def test_model_capacity_is_transient_provider_capacity_not_a_crash():
    event = '{"type":"turn.failed","error":{"message":"Selected model is at capacity. Please try a different model."}}'
    assert classify(1, event) == 'capacity'
    assert classify(1, 'API Error: 529 Overloaded') == 'capacity'
