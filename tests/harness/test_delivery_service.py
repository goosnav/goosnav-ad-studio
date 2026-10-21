"""The installed user service owns restart policy without exposing credentials."""
from pathlib import Path
from types import SimpleNamespace
import shutil
import subprocess

import pytest

from harness.store import Store


def test_service_installs_a_unique_persistent_worker_and_starts_it(tmp_path):
    from harness.delivery_service import install
    store = Store(tmp_path / 'state with spaces')
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout='active\n', stderr='')
    result = install(store, config_home=tmp_path / 'config', run=run,
                     which=lambda binary: '/usr/bin/' + binary)
    unit = Path(result['unit_file'])
    assert unit.is_file()
    text = unit.read_text()
    assert 'Restart=always' in text and 'RestartSec=5' in text
    assert str(store.root) in text and '-m harness.delivery_queue' in text
    assert 'WantedBy=default.target' in text
    assert commands[-1][-1] == result['unit']
    assert any(c[2:4] == ['enable', '--now'] for c in commands)
    assert result['active'] is True
    # Reinstall leaves the same unit and destination, rather than duplicating workers.
    other = install(store, config_home=tmp_path / 'config', run=run,
                    which=lambda binary: '/usr/bin/' + binary)
    assert other['unit'] == result['unit']
    assert len(list(unit.parent.glob('*.service'))) == 1


def test_missing_user_service_manager_preserves_existing_delivery_fallback(tmp_path):
    from harness.delivery_service import install
    def run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout='', stderr='Cannot connect to user bus')
    result = install(Store(tmp_path / 'state'), config_home=tmp_path / 'config',
                     run=run, which=lambda binary: '/usr/bin/' + binary)
    assert result['active'] is False
    assert 'user service manager' in result['error']
    assert not list((tmp_path / 'config').rglob('*.service'))


@pytest.mark.skipif(not shutil.which('systemd-analyze'), reason='systemd validator unavailable')
def test_generated_service_is_accepted_by_the_real_service_manager_parser(tmp_path):
    from harness.delivery_service import install
    result = install(Store(tmp_path / 'delivery state'), config_home=tmp_path / 'config',
                     run=lambda *a, **k: SimpleNamespace(returncode=0, stdout='', stderr=''),
                     which=shutil.which)
    checked = subprocess.run(['systemd-analyze', '--user', 'verify', result['unit_file']],
                             capture_output=True, text=True, timeout=15)
    assert checked.returncode == 0, checked.stderr


def test_recovery_requests_installed_supervisor_instead_of_an_unmanaged_worker(tmp_path):
    from harness.delivery_service import install, recover_installed
    store = Store(tmp_path / 'state')
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    config = tmp_path / 'config'
    assert recover_installed(store, config_home=config, run=run, which=shutil.which) is False
    install(store, config_home=config, run=run, which=shutil.which)
    calls.clear()
    assert recover_installed(store, config_home=config, run=run, which=shutil.which) is True
    assert len(calls) == 1
    assert '--no-block' in calls[0] and 'start' in calls[0]
