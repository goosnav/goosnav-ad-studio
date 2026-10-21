"""Native CLI workers. No API SDK, shell interpolation, or hidden model fallback."""
from datetime import datetime, timedelta
import errno
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time
import uuid


# Ask the Codex CLI to choose its own working model when catalog discovery fails.
CODEX_CLI_DEFAULT = 'cli-default'
_ATTEMPT_ENV = 'GOOSNAV_WORKER_ATTEMPT'


class WorkerCleanupError(RuntimeError):
    """The workspace may still have a writer; retain token and block retries."""

    def __init__(self, ownership_token, detail):
        self.ownership_token = ownership_token
        super().__init__(detail)


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
        cmd = ['codex', 'exec', '--ignore-user-config', '--skip-git-repo-check',
               # Full access by owner decision: a sandbox or approval prompt stalls an unattended worker.
               '-C', str(workspace), '--dangerously-bypass-approvals-and-sandbox',
               '-c', 'forced_login_method="chatgpt"']
        if model != CODEX_CLI_DEFAULT:
            cmd += ['-m', model, '-c', f'model_reasoning_effort="{profile.get("effort", "medium")}"']
        # An omitted -m uses the Codex CLI's own default; never invent a model ID.
        return cmd + ['--json', '-']
    cmd = ['claude', '-p', '--model', model, '--output-format', 'stream-json', '--verbose',
            '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
            '--dangerously-skip-permissions',
            # The tool set scopes the job (no sub-agents); it is not a permission gate.
            '--tools', 'Read,Write,Edit,Bash,Glob,Grep,WebSearch,WebFetch,TodoWrite']
    if profile.get('effort'):
        cmd += ['--effort', profile['effort']]
    return cmd


def subscription_status(provider):
    cmd = ['codex', 'login', 'status'] if provider == 'codex' else ['claude', 'auth', 'status']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=worker_env())
        if provider == 'codex':
            return r.returncode == 0 and 'chatgpt' in (r.stdout + r.stderr).lower()
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
        'capacity': ['at capacity', 'overloaded', 'server is busy', 'try a different model'],
        'context': ['context window', 'context_length', 'context limit', 'max_tokens', 'max_turns'],
        'auth': ['authentication', 'unauthorized', 'not logged in', 'login required',
                 'token_expired', 'log in again', 'invalid_api_key', 'invalid login', 'login expired'],
        'model': ['model not found', 'model_not_found', 'unknown model', 'invalid model',
                  'unsupported model', 'not supported', 'model is unavailable',
                  'model is not available'],
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


def _owned_processes(marker, deadline):
    """Open stable Linux handles only for this attempt's inherited environment.

    Never infer ownership from a command, cwd, username or a recycled PID.
    Open the pidfd BEFORE reading environ: if the PID is recycled during the
    read, signalling the handle still cannot reach the replacement process.
    """
    owned = []
    inspected = 0
    try:
        with os.scandir('/proc') as entries:
            for entry in entries:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Worker ownership scan exceeded cleanup deadline')
                if not entry.name.isdecimal():
                    continue
                fd = None
                try:
                    if entry.stat().st_uid != os.getuid():
                        continue
                    fd = os.pidfd_open(int(entry.name))
                    with open(entry.path + '/environ', 'rb') as env:
                        # Bound memory even for an unexpectedly large environment.
                        data = env.read(2 * 1024 * 1024)
                    inspected += 1
                    if marker in data.split(b'\0'):
                        owned.append(fd)
                        fd = None
                except (ProcessLookupError, FileNotFoundError, PermissionError):
                    # Exited or unidentified: never infer ownership from UID.
                    # Unreadable/scrubbed markers are an explicit limitation.
                    pass
                finally:
                    if fd is not None:
                        os.close(fd)
        if time.monotonic() >= deadline:
            raise TimeoutError('Worker ownership scan exceeded cleanup deadline')
        if not inspected:
            raise OSError('Cannot confirm worker cleanup: no same-user process environments could be inspected')
        return owned
    except BaseException:
        for fd in owned:
            os.close(fd)
        raise


def _linux_ownership():
    return (sys.platform.startswith('linux') and hasattr(os, 'pidfd_open')
            and hasattr(signal, 'pidfd_send_signal') and hasattr(os, 'WNOWAIT'))


def _validate_ownership_token(token):
    if not isinstance(token, str) or re.fullmatch(r'[0-9a-f]{32}', token) is None:
        raise ValueError('ownership_token must be a 32-character lowercase UUID hex string')
    return token


def cleanup_owned_attempt(token):
    """Stop an attempt recovered from persisted state, even without its leader.

    Pass the unique uuid.uuid4().hex saved BEFORE supervise is launched. Returns
    None after a complete scan finds no readable marked processes. Invalid tokens
    raise ValueError; unsupported platforms and unconfirmed cleanup raise OSError
    (including TimeoutError). Callers must retain the interrupted state on error.

    Linux /proc, readable candidate environments and pidfds are required. Scans,
    kills and exit confirmation share a three-second deadline. Detached children
    must inherit the marker: this is cooperative ownership, not containment.
    Legacy/non-Linux supervision retains its live process-group fallback, but
    token-only crash recovery cannot safely infer a group and fails closed.
    Unidentified permission-denied entries are skipped, never killed. Unreadable,
    scrubbed or markers beyond the 2 MiB environment read limit can escape.
    A scan with zero successful environment inspections raises OSError.
    Signal failures or deadlines for proven-owned pidfds propagate to the caller.
    """
    token = _validate_ownership_token(token)
    if not _linux_ownership():
        raise OSError(errno.ENOTSUP, 'Attempt cleanup requires Linux /proc and pidfds')
    _kill_detached(f'{_ATTEMPT_ENV}={token}'.encode(), time.monotonic() + 3)


def _worker_running(proc):
    if _linux_ownership():
        # Keep the leader unreaped until group cleanup. Its reserved PID prevents
        # an unrelated process group from reusing this group ID after CLI exit.
        return os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None
    return proc.poll() is None


def _terminate_attempt(proc, token):
    """Bound cleanup to three seconds, including detached/reparented children.

    Linux requires /proc and pidfds. Elsewhere retain the process-group fallback.
    This is cooperative ownership, not a sandbox: descendants must inherit the
    marker and remain inspectable. An exec with a scrubbed environment can escape.
    """
    if not _linux_ownership():
        terminate_group(proc)
        return
    deadline = time.monotonic() + 3
    marker = f'{_ATTEMPT_ENV}={token}'.encode()
    # The leader is still our unreaped child, so its group cannot be reused.
    # This also catches ordinary children that deliberately sanitize their env.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    grace = time.monotonic() + .2
    while _worker_running(proc) and time.monotonic() < grace:
        time.sleep(.02)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        _kill_detached(marker, deadline)
    finally:
        proc.wait(timeout=max(.001, deadline - time.monotonic()))


def _kill_detached(marker, deadline):
    while True:
        handles = _owned_processes(marker, deadline)
        if not handles:
            return
        try:
            poller = select.poll()
            for fd in handles:
                try:
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                poller.register(fd, select.POLLIN)
            pending = set(handles)
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Worker descendants did not exit before cleanup deadline')
                for fd, _ in poller.poll(max(1, int(remaining * 1000))):
                    pending.discard(fd)
                    poller.unregister(fd)
        finally:
            for fd in handles:
                os.close(fd)
        # Scan again for children forked during the preceding scan/signals.


def _progress_stamp(path):
    try:
        stat = path.stat()
        return stat.st_ino, stat.st_size, stat.st_mtime_ns
    except OSError:
        return None


class _WorkspaceProgress:
    """Metadata only: cache-key discovery never enumerates individual frames."""

    def __init__(self, cwd, log):
        root = Path(cwd)
        self.paths = [log] + [root / name for name in (
            'handoff.md', 'result.json', '.resource-wait.json', 'build.py', 'scene.blend', 'rigs.json',
            'preview.mp4', 'audio/production.json', 'audio/checkpoint.json',
            'audio/direction-result.json', 'audio/audio-result.json',
            'audio/measured-plan.json',
        )]
        self.caches = {root / name: (None, []) for name in ('.render-cache', 'render-cache')}

    def snapshot(self):
        watched = list(self.paths)
        for root, (previous, journals) in self.caches.items():
            stamp = _progress_stamp(root)
            if stamp != previous:
                journals = []
                try:
                    with os.scandir(root) as entries:
                        for index, entry in enumerate(entries):
                            # Bounded fanout; real workspaces have only a few keys.
                            if index >= 256:
                                break
                            if entry.is_dir(follow_symlinks=False):
                                journals.append(Path(entry.path) / 'frames.json')
                except OSError:
                    pass
                self.caches[root] = (stamp, journals)
            watched.extend(journals)
        return {str(path): _progress_stamp(path) for path in watched}


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


def last_actions(path, limit=5):
    """The final messages and commands of a worker session, oldest first (Claude or Codex logs)."""
    actions = []
    try:
        f = Path(path).open(errors='replace')
    except OSError:
        return actions
    with f:
        for line in iter(lambda: f.readline(1024 * 1024), ''):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            item = d.get('item') if d.get('type') == 'item.completed' else None
            if isinstance(item, dict) and item.get('type') == 'agent_message':
                actions.append(item.get('text'))
            elif isinstance(item, dict) and item.get('type') == 'command_execution':
                actions.append(f"$ {item.get('command')}")
            message = d.get('message')
            content = message.get('content') if d.get('type') == 'assistant' and isinstance(message, dict) else None
            for part in content if isinstance(content, list) else []:
                if not isinstance(part, dict):
                    continue
                if part.get('type') == 'text':
                    actions.append(part.get('text'))
                elif part.get('type') == 'tool_use':
                    i = part.get('input') if isinstance(part.get('input'), dict) else {}
                    actions.append(f"{part.get('name')}: {i.get('command') or i.get('file_path') or i.get('description') or ''}")
            actions = [a for a in actions if isinstance(a, str) and a.strip()][-limit:]
    return [' '.join(a.split())[:200] for a in actions]


def supervise(argv, *, cwd, prompt, log, timeout, cancelled, max_log_mb=32, started=None,
              idle_timeout=None, ownership_token=None):
    token = uuid.uuid4().hex if ownership_token is None else _validate_ownership_token(ownership_token)
    start = time.monotonic()
    log = Path(log); log.parent.mkdir(parents=True, exist_ok=True)
    kind = None
    # A file for stdin avoids blocking the supervisor on a large pipe write.
    prompt_path = Path(cwd) / '.worker-input.txt'
    prompt_path.write_text(prompt)
    temporary = Path(cwd).resolve() / '.tmp'
    temporary.mkdir(exist_ok=True)
    env = {**worker_env(), _ATTEMPT_ENV: token,
           'TMPDIR': str(temporary), 'TMP': str(temporary), 'TEMP': str(temporary)}
    try:
        with prompt_path.open() as inp, log.open('w') as out:
            proc = subprocess.Popen(argv, cwd=cwd, stdin=inp, stdout=out,
                                    stderr=subprocess.STDOUT, env=env, start_new_session=True)
            try:
                if started:
                    started(proc.pid)
                last_progress = time.monotonic()
                progress = _WorkspaceProgress(cwd, log)
                stamps = {}
                while _worker_running(proc):
                    if cancelled():
                        kind = 'cancelled'; break
                    now = time.monotonic()
                    if now - start > timeout:
                        kind = 'timeout'; break
                    if log.stat().st_size > max_log_mb * 1024 * 1024:
                        kind = 'log_limit'; break
                    if idle_timeout:
                        current = progress.snapshot()
                        if current != stamps:
                            last_progress = now; stamps = current
                        elif now - last_progress > idle_timeout:
                            kind = 'idle_timeout'; break
                    time.sleep(.1)
            finally:
                try:
                    _terminate_attempt(proc, token)
                except Exception as exc:
                    # Never let the dependency handler disguise uncertain cleanup
                    # as a provider failure that is safe to retry in this workspace.
                    raise WorkerCleanupError(token, str(exc)) from exc
        output = tail(log)
        metadata=session_metadata(log)
        error_text='\n'.join(metadata['terminal_errors']) or output
        if kind in ('timeout', 'idle_timeout'):
            error_text = f'{kind}: worker exceeded {timeout}s total or {idle_timeout}s without observable progress. ' + error_text
        return {'kind': kind or classify(proc.returncode, error_text), 'code': proc.returncode,
                'elapsed': round(time.monotonic() - start, 2), 'detail': error_text[-4000:], **metadata}
    except OSError as e:
        return {'kind': 'dependency', 'code': None, 'elapsed': 0, 'detail': str(e)}
