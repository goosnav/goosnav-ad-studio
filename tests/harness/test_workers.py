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
