"""Native CLI workers. No API SDK, shell interpolation, or hidden model fallback."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def worker_env(source=None):
    env = dict(os.environ if source is None else source)
    for key in list(env):
        if key.startswith(('ANTHROPIC_', 'OPENAI_', 'CLAUDE_CODE_USE_', 'AWS_', 'AZURE_')) or key in (
                'CLAUDECODE', 'CLAUDE_CODE_OAUTH_TOKEN', 'CODEX_API_KEY'):
            env.pop(key, None)
    return env


def command(profile, workspace):
    model = profile['model']
    if model.startswith('auto:'):
        raise ValueError('Resolve model selectors before launching a worker')
    if profile['provider'] == 'codex':
        return ['codex', 'exec', '--ignore-user-config', '--skip-git-repo-check',
                # Full access by owner decision: a sandbox or approval prompt stalls an unattended worker.
                '-C', str(workspace), '--dangerously-bypass-approvals-and-sandbox',
                '-c', 'forced_login_method="chatgpt"',
                '-m', model, '-c', f'model_reasoning_effort="{profile.get("effort", "medium")}"',
                '--json', '-']
    return ['claude', '-p', '--model', model, '--output-format', 'stream-json', '--verbose',
            '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
            '--dangerously-skip-permissions',
            # The tool set scopes the job (no sub-agents); it is not a permission gate.
            '--tools', 'Read,Write,Edit,Bash,Glob,Grep,WebSearch,WebFetch,TodoWrite']


def subscription_status(provider):
    cmd = ['codex', 'login', 'status'] if provider == 'codex' else ['claude', 'auth', 'status']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=worker_env())
        if provider == 'codex':
            return r.returncode == 0 and 'using ChatGPT' in r.stdout + r.stderr
        d = json.loads(r.stdout)
        return d.get('loggedIn') is True and d.get('authMethod') == 'claude.ai'
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False


def classify(code, output):
    s = output.lower()
    # Prefer structured terminal events; callers pass only a bounded log tail.
    terminal = []
    for line in output.splitlines():
        try:
            e = json.loads(line)
            if e.get('api_error_status') == 429:
                return 'quota'
            if e.get('type') in ('error', 'turn.failed') or e.get('is_error'):
                terminal.append(json.dumps(e))
        except (ValueError, AttributeError):
            pass
    if code == 0 and not terminal:
        return 'ok'
    if terminal:
        s = '\n'.join(terminal).lower()
    for kind, words in {
        'quota': ['rate limit', 'rate_limit', 'usage limit', 'usage_limit', 'quota', 'out of credits',
                  'hit your limit', 'session limit', 'too many requests', 'limit reached'],
        'context': ['context window', 'context_length', 'context limit', 'max_tokens', 'max_turns'],
        'auth': ['authentication', 'unauthorized', 'not logged in', 'login required',
                 'token_expired', 'log in again', 'invalid_api_key', 'invalid login', 'login expired'],
        'model': ['model not found', 'model_not_found', 'not supported', 'model is unavailable'],
        'permission': ['permission denied', 'permission_denied', 'tool denied'],
    }.items():
        if any(w in s for w in words):
            return kind
    return 'crash'


def reset_delay(text, now=None):
    """Seconds until a reset the CLI announced ("resets 5:40pm", "try again at 4:24 PM"), plus a minute."""
    now = now or datetime.now()
    dated = re.search(r'(?:resets|try again at)\s+([A-Z][a-z]{2})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})'
                      r'\s+(\d{1,2}):(\d{2})\s*([AP])\.?M', text, re.I)
    if dated:   # weekly limits name the day: "try again at Oct 22nd, 2026 11:24 AM"
        month = datetime.strptime(dated[1].title(), '%b').month
        hour = int(dated[4]) % 12 + (12 if dated[6].upper() == 'P' else 0)
        target = datetime(int(dated[3]), month, int(dated[2]), hour, int(dated[5]))
        return max(60, int((target - now).total_seconds()) + 60)
    m = re.search(r'(?:resets|try again at)\s+(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m', text, re.I)
    if not m:
        return None
    hour = int(m[1]) % 12 + (12 if m[3].lower() == 'p' else 0)
    target = now.replace(hour=hour, minute=int(m[2] or 0), second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int((target - now).total_seconds()) + 60


def terminate_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # Also reap descendants when the session leader has already exited.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def tail(path, size=65536):
    with Path(path).open('rb') as f:
        f.seek(0, 2); f.seek(max(0, f.tell() - size))
        return f.read().decode('utf-8', 'replace')


def session_metadata(path):
    models=set();session_id=None;usage={};errors=[]
    with Path(path).open(errors='replace') as f:
        for line in iter(lambda:f.readline(1024*1024), ''):
            try:
                d=json.loads(line)
                if not isinstance(d,dict):continue
                if d.get('type')=='system' and d.get('subtype')=='init':
                    session_id=d.get('session_id')
                    if isinstance(d.get('model'),str):models.add(d['model'])
                if d.get('type')=='thread.started':session_id=d.get('thread_id')
                message=d.get('message',{})
                if isinstance(message,dict) and isinstance(message.get('model'),str):models.add(message['model'])
                if isinstance(d.get('modelUsage'),dict):
                    models.update(d['modelUsage']);usage=d['modelUsage']
                if d.get('type')=='turn.completed':usage=d.get('usage',{})
                if d.get('type') in ('error','turn.failed') or d.get('is_error'):
                    errors.append(line[:4000]);errors=errors[-5:]
            except (ValueError,TypeError):pass
    return {'observed_models':sorted(models),'session_id':session_id,'usage':usage,'terminal_errors':errors}


def supervise(argv, *, cwd, prompt, log, timeout, cancelled, max_log_mb=32, started=None,
              idle_timeout=None):
    start = time.monotonic()
    log = Path(log); log.parent.mkdir(parents=True, exist_ok=True)
    kind = None
    # A file for stdin avoids blocking the supervisor on a large pipe write.
    prompt_path = Path(cwd) / '.worker-input.txt'
    prompt_path.write_text(prompt)
    try:
        with prompt_path.open() as inp, log.open('w') as out:
            proc = subprocess.Popen(argv, cwd=cwd, stdin=inp, stdout=out,
                                    stderr=subprocess.STDOUT, env=worker_env(), start_new_session=True)
            if started:
                started(proc.pid)
            try:
                last_progress = time.monotonic()
                # Streaming output is activity. An agent can also make progress by
                # updating its handoff or final result while the CLI is quiet.
                watched = [log, Path(cwd) / 'handoff.md', Path(cwd) / 'result.json']
                stamps = {}
                while proc.poll() is None:
                    if cancelled():
                        kind = 'cancelled'; break
                    now = time.monotonic()
                    if now - start > timeout:
                        kind = 'timeout'; break
                    if log.stat().st_size > max_log_mb * 1024 * 1024:
                        kind = 'log_limit'; break
                    if idle_timeout:
                        current = {}
                        for p in watched:
                            try:
                                stat = p.stat()
                                current[str(p)] = (stat.st_size, stat.st_mtime_ns)
                            except FileNotFoundError:
                                current[str(p)] = None
                        if current != stamps:
                            last_progress = now; stamps = current
                        elif now - last_progress > idle_timeout:
                            kind = 'idle_timeout'; break
                    time.sleep(.1)
            finally:
                terminate_group(proc)
        output = tail(log)
        metadata=session_metadata(log)
        error_text='\n'.join(metadata['terminal_errors']) or output
        if kind in ('timeout', 'idle_timeout'):
            error_text = f'{kind}: worker exceeded {timeout}s total or {idle_timeout}s without observable progress. ' + error_text
        return {'kind': kind or classify(proc.returncode, error_text), 'code': proc.returncode,
                'elapsed': round(time.monotonic() - start, 2), 'detail': error_text[-4000:], **metadata}
    except OSError as e:
        return {'kind': 'dependency', 'code': None, 'elapsed': 0, 'detail': str(e)}
