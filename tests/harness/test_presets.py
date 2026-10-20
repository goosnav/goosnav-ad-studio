import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from harness.config import ConfigError, load_config


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('effort,provider,creative,qa', [
    ('high', 'codex', 'auto:quality', 'auto:balanced'),
    ('medium', 'claude', 'auto:quality', 'auto:balanced'),
    ('low', 'codex', 'auto:economy', 'auto:economy'),
])
def test_intensity_selects_requested_default_provider_and_role_tiers(effort, provider, creative, qa):
    config = load_config(None, {'generation': {'effort': effort}})
    for role in ('writer', 'animator', 'director'):
        assert config['workers'][role][0]['provider'] == provider
        assert config['workers'][role][0]['model'] == creative
        assert len(config['workers'][role]) == 2
    for role in ('critic', 'selector', 'reviewer'):
        assert config['workers'][role][0]['model'] == qa


@pytest.mark.parametrize('effort,provider,backend,creative,qa,thinking', [
    ('high', 'openai', 'codex', 'auto:quality', 'auto:balanced', 'high'),
    ('medium', 'openai', 'codex', 'auto:balanced', 'auto:economy', 'medium'),
    ('low', 'openai', 'codex', 'auto:economy', 'auto:economy', 'low'),
    ('high', 'anthropic', 'claude', 'auto:quality', 'auto:balanced', 'max'),
    ('medium', 'anthropic', 'claude', 'auto:quality', 'auto:balanced', 'medium'),
    ('low', 'anthropic', 'claude', 'auto:balanced', 'auto:economy', 'low'),
])
def test_explicit_provider_is_preferred_and_keeps_dynamic_failover(effort, provider, backend, creative, qa, thinking):
    config = load_config(None, {'generation': {'effort': effort, 'provider': provider}})
    for routes in config['workers'].values():
        assert len(routes) == 2
        assert routes[0]['provider'] == backend
        assert routes[1]['provider'] != backend
    for role in ('writer', 'animator', 'director'):
        assert config['workers'][role][0]['model'] == creative
        assert config['workers'][role][0]['effort'] == thinking
    assert config['workers']['reviewer'][0]['model'] == qa


def test_default_is_medium_and_keeps_explicit_json_worker_overrides(tmp_path):
    path = tmp_path / 'custom.json'
    custom = [{'provider': 'claude', 'model': 'custom-pinned-model'}]
    path.write_text(json.dumps({'workers': {'writer': custom}}))
    assert load_config(path)['workers']['writer'] == custom
    assert load_config()['generation'] == {'effort': 'medium', 'provider': 'auto'}
    # A CLI selection deliberately replaces old routes for this run only.
    high = load_config(path, {'generation': {'effort': 'high', 'provider': 'openai'}})
    assert high['workers']['writer'][0]['model'] == 'auto:quality'
    assert high['workers']['writer'][0]['provider'] == 'codex'
    assert json.loads(path.read_text())['workers']['writer'] == custom


@pytest.mark.parametrize('setting,value', [('effort', 'maximum'), ('provider', 'unknown')])
def test_invalid_preset_in_json_has_actionable_choices(setting, value):
    with pytest.raises(ConfigError, match='low, medium, high|auto, openai, anthropic'):
        load_config(None, {'generation': {setting: value}})


@pytest.mark.parametrize('effort_flag,provider_flag', [('-e', '-p'), ('--effort', '--provider'),
                                                    ('-effort', '-provider')])
def test_shortcut_forwards_model_flags_without_starting_workers(tmp_path, effort_flag, provider_flag):
    config = tmp_path / 'blank.json'; config.write_text('{}')
    env = {**os.environ, 'STUDIO_HARNESS_HOME': str(tmp_path / 'jobs')}
    result = subprocess.run([sys.executable, str(ROOT / 'ad'), 'An astronaut reads', '-s', '9',
        effort_flag, 'high', provider_flag, 'openai', '--config', str(config), '--plan'],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    state = json.loads(result.stdout)
    assert state['config']['generation'] == {'effort': 'high', 'provider': 'openai'}
    assert state['config']['output']['target_seconds'] == 9
    assert state['models'] == {} and state['status'] == 'ready'
    assert state['config']['workers']['animator'][0] == {
        'provider': 'codex', 'model': 'auto:quality', 'effort': 'high'}


@pytest.mark.parametrize('args,choices', [(['-e', 'huge'], ('low', 'medium', 'high')),
                                       (['-p', 'wrong'], ('openai', 'anthropic')),
                                       (['--efort', 'high'], ('--effort',))])
def test_invalid_shortcut_arguments_list_choices_and_do_not_create_a_job(tmp_path, args, choices):
    jobs = tmp_path / 'jobs'
    result = subprocess.run([sys.executable, str(ROOT / 'ad'), *args], cwd=ROOT,
        env={**os.environ, 'STUDIO_HARNESS_HOME': str(jobs)}, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert all(choice in result.stderr for choice in choices)
    assert not (jobs / 'state.sqlite3').exists()


def test_low_level_cli_uses_same_presets(tmp_path):
    config = tmp_path / 'blank.json'; config.write_text('{}')
    result = subprocess.run([sys.executable, '-m', 'harness', '--home', str(tmp_path / 'jobs'),
        'make', '--config', str(config), '-e', 'low', '-p', 'anthropic', '--seconds', '9', '--plan'],
        cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    state = json.loads(result.stdout)
    assert state['config']['workers']['animator'][0] == {
        'provider': 'claude', 'model': 'auto:balanced', 'effort': 'low'}
    assert state['config']['workers']['reviewer'][0]['model'] == 'auto:economy'


@pytest.mark.parametrize('command', ['status', 'list', 'cancel', 'cooldown', 'resume'])
def test_control_commands_show_help_and_reject_bad_options_without_side_effects(tmp_path, command):
    env = {**os.environ, 'STUDIO_HARNESS_HOME': str(tmp_path / 'jobs')}
    for args, code in ((['--help'], 0), (['--invalid-option'], 2)):
        result = subprocess.run([sys.executable, str(ROOT / 'ad'), command, *args], cwd=ROOT,
            env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode == code, result.stdout + result.stderr
        assert 'usage:' in result.stdout + result.stderr
        assert 'Traceback' not in result.stderr
    assert not (tmp_path / 'jobs' / 'state.sqlite3').exists()
