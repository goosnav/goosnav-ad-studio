"""Install the delivery queue as a restarting Linux user service.

The queue retains its existing singleton/transfer leases and durable receipts.
No credentials are copied into the unit. Hosts without a user service manager
can keep using the detached worker started by the CLI.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .store import Store


def _quoted(value):
    value = str(value)
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Service paths cannot contain control characters')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def _unit_location(store, config_home):
    name = 'goosnav-ad-delivery-' + sha256(str(store.root).encode()).hexdigest()[:12] + '.service'
    base = Path(config_home or os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return name, base / 'systemd' / 'user' / name


def recover_installed(store, *, config_home=None, run=subprocess.run, which=shutil.which):
    """Keep CLI recovery with the installed supervisor, including restart delays."""
    name, unit = _unit_location(store, config_home)
    binary = which('systemctl')
    if not unit.is_file() or not binary:
        return False
    try:
        result = run([binary, '--user', '--no-block', 'start', name],
                     capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True
        print('Drive delivery supervisor unavailable; using detached recovery: '
              + (result.stderr or result.stdout).strip()[-300:], file=sys.stderr)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'Drive delivery supervisor unavailable; using detached recovery: {exc}', file=sys.stderr)
    return False


def install(store, *, config_home=None, run=subprocess.run, which=shutil.which):
    """Idempotent explicit setup; normal CLI delivery needs no service prompts."""
    binary = which('systemctl')
    if not binary:
        return {'active': False, 'error': 'No user service manager; detached delivery remains available'}
    def control(*args):
        return run([binary, '--user', *args], capture_output=True, text=True, timeout=15)
    try:
        if control('show-environment').returncode:
            return {'active': False, 'error': 'Cannot reach user service manager; detached delivery remains available'}
        name, unit = _unit_location(store, config_home)
        repo = Path(__file__).resolve().parents[1]
        _quoted(repo)  # Validate control characters; this directive takes a raw path.
        rclone = which('rclone')
        executable_path = os.pathsep.join(dict.fromkeys(
            ([str(Path(rclone).parent)] if rclone else []) + os.defpath.split(os.pathsep)))
        settings = ['Environment=' + _quoted('PATH=' + executable_path), 'Environment=PYTHONUNBUFFERED=1']
        for key in ('XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'RCLONE_CONFIG'):
            if os.environ.get(key):
                settings.append('Environment=' + _quoted(key + '=' + os.environ[key]))
        content = ('[Unit]\nDescription=Goosnav ad video delivery\nStartLimitIntervalSec=0\n\n'
                   '[Service]\nType=simple\nWorkingDirectory=' + str(repo).replace('%', '%%') + '\n'
                   'ExecStart=:' + _quoted(sys.executable) + ' -B -X '
                   + _quoted('pycache_prefix=' + str(store.root / '.delivery-bytecode' / 'service'))
                   + ' -m harness.delivery_queue ' + _quoted(store.root) + '\n'
                   'Restart=always\nRestartSec=5\nKillMode=mixed\nTimeoutStopSec=125\n'
                   + '\n'.join(settings) + '\n'
                   'StandardOutput=append:' + str(store.root / 'delivery-worker.log').replace('%', '%%') + '\n'
                   'StandardError=inherit\n\n[Install]\nWantedBy=default.target\n')
        unit.parent.mkdir(parents=True, exist_ok=True)
        if not unit.exists() or unit.read_text() != content:
            with tempfile.NamedTemporaryFile(mode='w', dir=unit.parent, delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(content)
                    stream.flush()
                    temporary.replace(unit)
                finally:
                    temporary.unlink(missing_ok=True)
        for args in (('daemon-reload',), ('enable', '--now', name)):
            result = control(*args)
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout or 'Service setup failed').strip()[-500:])
        active = control('is-active', name).returncode == 0
        return {'active': active, 'unit': name, 'unit_file': str(unit)}
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
        return {'active': False, 'error': str(exc)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', default=os.environ.get('STUDIO_HARNESS_HOME',
                        str(Path.home() / '.local/share/goosnav-ad-studio')))
    args = parser.parse_args()
    result = install(Store(args.home))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['active'] else 1)
