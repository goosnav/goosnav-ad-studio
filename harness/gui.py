"""A plain local web page over the same store and CLI. It never runs workers itself.

Starting/resuming spawns `python -m harness ...` detached, so the CLI's file lock
still guarantees one controller per run. Pause/cancel write the same control flag the CLI
writes. Files are served only from inside the harness home.
"""
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import parse_qs, quote, urlparse
import urllib.request

from .config import load_config
from .store import Store
from .delivery import _completed_ads

REPO = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = REPO / 'harness.local.json'
STYLE = '''body{font:15px/1.45 Helvetica,Arial,sans-serif;max-width:68rem;margin:2rem auto;padding:0 1rem}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:.3rem;text-align:left;vertical-align:top}
textarea{width:100%;font:13px monospace}video{max-width:22rem;display:block}pre{white-space:pre-wrap;font-size:12px}
.failed,.needs_review,.waiting_provider{color:#b00}.succeeded,.complete{color:#070}.running{color:#06c}.awaiting_upload{color:#875500}'''


def esc(value):
    return html.escape(str(value), quote=True)


def display_status(state):
    """Present delivery completion without changing generation's saved status."""
    from .delivery_queue import _pending
    if state['status'] == 'complete' and _pending(state):
        return 'awaiting_upload'
    return state['status']


def delivery_summary(store, state):
    """Keep retry deadlines in the queue; expose queued and orphaned transfers."""
    from .delivery_queue import _pending, describe, worker_running
    pending = _pending(state)
    info = state.get('delivery')
    info = info if isinstance(info, dict) else {}
    if not info and not pending:
        return ''
    if pending and info.get('status') == 'uploaded':
        # An old receipt can no longer match the packaged bytes or destination.
        state = {**state, 'delivery': {**info, 'status': 'queued', 'verified': {}}}
    text = describe(store, state)
    if pending and info.get('status') != 'retrying':
        action = store.control_value(state['id'])
        if action != 'run':
            text += ' | automatic retries ' + ('paused' if action == 'pause' else 'cancelled')
        else:
            if info.get('status') != 'uploading':
                text += ' | queued for automatic delivery'
            text += ' | ' + ('worker running' if worker_running(store)
                             else 'WARNING: retry worker not running')
    return text


def page(title, body, refresh=False):
    meta = '<meta http-equiv="refresh" content="10">' if refresh else ''
    return (f'<!doctype html><meta charset="utf-8">{meta}<title>{esc(title)}</title><style>{STYLE}</style>'
            f'<p><a href="/">Ad Studio</a> · <a href="/config">Config</a> · <a href="/doctor">Doctor</a></p>'
            f'<h1>{esc(title)}</h1>{body}')


def spawn(home, *args):
    """Detached controller process; its output goes to a per-run log in the home."""
    logs = Path(home) / 'gui-logs'; logs.mkdir(parents=True, exist_ok=True)
    log = logs / f'{time.strftime("%Y%m%d-%H%M%S")}-{args[0]}-{uuid.uuid4().hex}.log'
    with log.open('x') as out:
        subprocess.Popen([sys.executable, '-m', 'harness', '--home', str(home), *args], cwd=REPO,
                         stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)


def videos(state):
    found = []
    for task in state['tasks']:
        if (task['status'] == 'succeeded' and task['stage'] in ('animate', 'edit', 'frame')
                and task['result'].get('delivery_mode') != 'product_only'):
            for f in task['result'].get('files', []):
                if f['path'].endswith('.mp4'):
                    found.append((task['id'], f['path']))
    return found


class Handler(BaseHTTPRequestHandler):
    store = None

    def send(self, body, code=200, kind='text/html; charset=utf-8'):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    def redirect(self, where):
        self.send_response(303); self.send_header('Location', where); self.end_headers()

    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path); q = parse_qs(url.query)
        try:
            if url.path == '/':
                self.send(self.index())
            elif url.path.startswith('/run/'):
                self.send(self.run_page(url.path.split('/')[2]))
            elif url.path == '/health':
                self.send(json.dumps({'app': 'goosnav-ad-studio', 'home': str(self.store.root)}),
                          kind='application/json')
            elif url.path == '/file':
                self.file(q.get('path', [''])[0])
            elif url.path == '/config':
                text = LOCAL_CONFIG.read_text() if LOCAL_CONFIG.exists() else (REPO / 'harness.example.json').read_text()
                self.send(page('Config', f'<p>Edits <code>{esc(LOCAL_CONFIG)}</code> (git-ignored). '
                    'Validated before saving. Brand documents, script banks, inspiration and asset folders are path lists.</p>'
                    f'<form method="post" action="/config"><textarea name="config" rows="40">{esc(text)}</textarea>'
                    '<p><button>Validate and save</button></p></form>'))
            elif url.path == '/doctor':
                from .cli import doctor
                self.send(page('Doctor', f'<pre>{esc(json.dumps(doctor(load_config(self.config_path())), indent=2))}</pre>'))
            else:
                self.send(page('Not found', ''), 404)
        except Exception as e:
            self.send(page('Error', f'<pre>{esc(type(e).__name__)}: {esc(e)}</pre>'), 400)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        if length > 1024 * 1024:
            return self.send(page('Error', 'Request too large'), 413)
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
        path = urlparse(self.path).path
        try:
            if path == '/make':
                overrides = {k: form[k].strip() for k in ('concept', 'website', 'count', 'seconds') if form.get(k, '').strip()}
                for key in ('count', 'seconds'):
                    if key in overrides:
                        overrides[key] = int(overrides[key])
                args = ['make'] + (['--config', self.config_path()] if self.config_path() else [])
                for key, value in overrides.items():
                    args += [f'--{key}', str(value)]
                if 'seconds' in overrides:
                    overrides['output'] = {'target_seconds': overrides.pop('seconds')}
                # Validate here so input errors appear in the browser rather than a log.
                load_config(self.config_path(), overrides)
                spawn(self.store.root, *args)
                time.sleep(1.5)
                return self.redirect('/')
            if path == '/config':
                candidate = json.loads(form.get('config', ''))
                tmp = LOCAL_CONFIG.with_suffix('.check.json'); tmp.write_text(json.dumps(candidate, indent=2))
                try:
                    load_config(tmp)
                finally:
                    tmp.unlink()
                LOCAL_CONFIG.write_text(json.dumps(candidate, indent=2) + '\n')
                return self.redirect('/config')
            parts = path.strip('/').split('/')
            if len(parts) == 3 and parts[0] == 'run':
                run_id, action = parts[1], parts[2]
                self.store.get(run_id)
                if action in ('pause', 'cancel'):
                    self.store.control(run_id, action)
                elif action == 'resume':
                    spawn(self.store.root, 'resume', run_id)
                elif action == 'retry':
                    spawn(self.store.root, 'retry', run_id, '--task', form['task'])
                else:
                    raise ValueError('Unknown action')
                time.sleep(1)
                return self.redirect(f'/run/{quote(run_id)}')
            self.send(page('Not found', ''), 404)
        except Exception as e:
            self.send(page('Error', f'<pre>{esc(type(e).__name__)}: {esc(e)}</pre>'), 400)

    def config_path(self):
        return str(LOCAL_CONFIG) if LOCAL_CONFIG.exists() else None

    def index(self):
        rows = ''.join(
            f'<tr><td><a href="/run/{quote(r["id"])}">{esc(r["id"])}</a></td><td class="{esc(status)}">{esc(status)}</td>'
            f'<td>{esc(r["config"]["concept"] or "(open brief)")}</td><td>{r["config"]["count"]}</td>'
            f'<td>{len(_completed_ads(r))}</td>'
            f'<td>{esc(delivery_summary(self.store, r)) or "—"}</td></tr>'
            for r in self.store.list() for status in (display_status(r),))
        target = load_config(self.config_path())['output']['target_seconds']
        return page('Ad Studio', '''<form method="post" action="/make">
<p><label>Concept (optional)<br><input name="concept" size="70" placeholder="Leave empty for an open brief"></label></p>
<p><label>Ads <input name="count" type="number" min="1" max="50" value="1"></label>
<label>Target seconds <input name="seconds" type="number" min="1" max="300" value="''' + str(target) + '''"></label>
<label>Website override <input name="website" placeholder="from config"></label></p>
<p><button>Make ads</button> Research, writing contest and production run unattended.</p></form>
<h2>Runs</h2><table><tr><th>Run</th><th>Status</th><th>Concept</th><th>Ads</th><th>Packaged</th><th>Drive delivery</th></tr>''' + rows + '</table>',
                    refresh=True)

    def run_page(self, run_id):
        s = self.store.get(run_id)
        rows = ''
        for t in s['tasks']:
            last = t['attempts'][-1] if t['attempts'] else {}
            who = f'{last.get("provider", "")} {last.get("model", "")}'.strip() or ('controller' if t['stage'] in ('frame', 'qa', 'package') else '')
            note = (t['result'] or {}).get('summary', '') if t['status'] == 'succeeded' else t['feedback']
            if t['status'] == 'running' and last:
                elapsed = max(0, int(time.time() - last.get('started', time.time())))
                log = Path(last.get('log', ''))
                activity = (f'last log update {int(time.time() - log.stat().st_mtime)}s ago'
                            if log.is_file() else 'no worker output yet')
                note = f'Running {elapsed//60}m {elapsed%60}s; {activity}. ' + note
            retry = (f'<form method="post" action="/run/{quote(run_id)}/retry"><input type="hidden" name="task" value="{esc(t["id"])}">'
                     '<button>Retry</button></form>') if t['status'] in ('failed', 'needs_review', 'waiting_provider') else ''
            rows += (f'<tr><td>{esc(t["id"])}</td><td class="{esc(t["status"])}">{esc(t["status"])}</td><td>{len(t["attempts"])}</td>'
                     f'<td>{esc(who)}</td><td><pre>{esc(str(note)[:600])}</pre>{retry}</td></tr>')
        media = ''.join(f'<p>{esc(task)}<video controls preload="metadata" src="/file?path={quote(p)}"></video></p>'
                        for task, p in videos(s))
        controls = ''.join(f'<form method="post" action="/run/{quote(run_id)}/{a}" style="display:inline"><button>{a.title()}</button></form> '
                           for a in ('pause', 'resume', 'cancel'))
        selected = next((t['result'] for t in s['tasks'] if t['stage'] == 'select' and t['status'] == 'succeeded'), None)
        choice = f'<h2>Selected scripts</h2><pre>{esc(json.dumps(selected, indent=2))}</pre>' if selected else ''
        events = ''.join(f'<li>{time.strftime("%H:%M:%S", time.localtime(e["at"]))} {esc(e["kind"])} {esc(json.dumps(e["data"])[:200])}</li>'
                         for e in self.store.events(run_id)[-25:])
        description = delivery_summary(self.store, s)
        delivery = f'<h2>Drive delivery</h2><pre>{esc(description)}</pre>' if description else ''
        fallback = ''.join(f'<p>Ad {int(ad)+1:02}: ' +
                           ('previous end-card-only output replaced with the full story.'
                            if int(ad) in _completed_ads(s) else
                            'previous end-card-only output rejected; original story required before delivery.') + '</p>'
                           for ad in s.get('fallbacks', {}))
        status = display_status(s)
        return page(f'Run {run_id}', f'<p>Status: <b class="{esc(status)}">{esc(status)}</b> {esc(s.get("error", ""))}</p>'
                    f'<p>{controls}</p>{delivery}{fallback}<p>Files: <code>{esc(self.store.root / "runs" / run_id)}</code></p>{media}{choice}'
                    f'<h2>Tasks</h2><table><tr><th>Task</th><th>Status</th><th>Attempts</th><th>Worker</th><th>Result / feedback</th></tr>{rows}</table>'
                    f'<h2>Recent events</h2><ul>{events}</ul>', refresh=True)

    def file(self, value):
        p = Path(value).resolve()
        if not p.is_relative_to(self.store.root) or not p.is_file():
            return self.send(page('Not found', ''), 404)
        self.send(p.read_bytes(), kind=mimetypes.guess_type(p.name)[0] or 'application/octet-stream')


def running_studio(host, port):
    """The harness home of an Ad Studio already answering on this port, else None."""
    try:
        with urllib.request.urlopen(f'http://{host}:{port}/health', timeout=1.5) as r:
            body = json.loads(r.read())
        return body.get('home') if body.get('app') == 'goosnav-ad-studio' else None
    except (OSError, ValueError):
        return None


def start(home, host='0.0.0.0', port=8788, tries=20):
    """Serve in a background thread and return (server, url). server is None when this
    studio is already being served on one of the ports; url then points at it."""
    probe = '127.0.0.1' if host in ('0.0.0.0', '') else host
    handler = type('StudioHandler', (Handler,), {'store': Store(home)})
    for candidate in [port] if port == 0 else range(port, port + tries):
        if candidate and running_studio(probe, candidate) == str(handler.store.root):
            return None, f'http://{probe}:{candidate}/'
        try:
            server = ThreadingHTTPServer((host, candidate), handler)
        except OSError:
            continue  # taken by something else; try the next port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        if candidate != port:
            print(f'Port {port} is busy; using {server.server_port}.', file=sys.stderr, flush=True)
        return server, f'http://{probe}:{server.server_port}/'
    raise OSError(f'No free port in {port}-{port + tries - 1}; pass --port')


def lan_addresses():
    """IPv4 addresses other computers can use (LAN first, then VPN such as Tailscale)."""
    try:
        found = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5).stdout.split()
    except (OSError, subprocess.TimeoutExpired):
        found = []
    ipv4 = [a for a in found if a.count('.') == 3 and not a.startswith(('127.', '172.17.', '172.18.'))]
    return sorted(ipv4, key=lambda a: (not a.startswith(('192.168.', '10.')), a))


def serve(home, host='0.0.0.0', port=8788, browser=True):
    from .delivery_queue import recover_worker
    recover_worker(Store(home))
    server, url = start(home, host, port)
    print(f'Ad Studio GUI: {url}' + ('  (already running)' if not server else
          '  (Ctrl+C to stop; runs continue in the background)'), file=sys.stderr, flush=True)
    if host in ('0.0.0.0', ''):
        used = url.rsplit(':', 1)[1].strip('/')
        for address in lan_addresses():
            print(f'  from another computer: http://{address}:{used}/', file=sys.stderr, flush=True)
        print('  (no login: share this network only with people you trust)', file=sys.stderr, flush=True)
    if browser:
        import webbrowser
        webbrowser.open(url)
    if not server:
        return
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()
