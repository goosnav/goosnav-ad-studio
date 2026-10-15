from http.server import ThreadingHTTPServer
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from harness import gui
from harness.config import load_config
from harness.store import Store
from harness.workflow import build_tasks


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(gui, 'LOCAL_CONFIG', tmp_path / 'harness.local.json')
    store = Store(tmp_path / 'home'); gui.Handler.store = store
    run = store.create(load_config(None, {'concept': 'A <b>loud</b> stapler'}))
    run['tasks'] = build_tasks(1); store.save(run, 'planned')
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), gui.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{httpd.server_port}', run, tmp_path
    httpd.shutdown()


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_pages_escape_input_and_files_stay_inside_home(server):
    base, run, tmp = server
    code, body = get(base + '/')
    assert code == 200 and '&lt;b&gt;loud' in body and '<b>loud' not in body
    code, body = get(base + f'/run/{run["id"]}')
    assert code == 200 and 'ad-01-package' in body
    (tmp / 'secret.txt').write_text('x')
    assert get(base + '/file?path=' + urllib.parse.quote(str(tmp / 'secret.txt')))[0] == 404


def test_config_is_validated_before_saving(server):
    base, _, tmp = server
    def post(text):
        data = urllib.parse.urlencode({'config': text}).encode()
        try:
            return urllib.request.urlopen(base + '/config', data).status
        except urllib.error.HTTPError as e:
            return e.code
    assert post('{"bogus": 1}') == 400 and not (tmp / 'harness.local.json').exists()
    assert post('{"website": "www.example.com"}') == 200
    assert 'example.com' in (tmp / 'harness.local.json').read_text()
