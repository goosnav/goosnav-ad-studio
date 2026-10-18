import pytest
from harness.models import choose_model, ModelError


def test_future_models_are_selected_without_release_names():
    models = [
        {'model': 'future-a', 'description': 'Older generation workhorse model.'},
        {'model': 'future-b', 'description': 'Frontier intelligence for the most demanding work.'},
        {'model': 'future-c', 'description': 'Fast and affordable model for easier tasks.'},
        {'model': 'future-d', 'description': 'Latest workhorse model.', 'isDefault': True}]
    assert choose_model(models, 'quality')['model'] == 'future-b'
    assert choose_model(models, 'economy')['model'] == 'future-c'
    assert choose_model(models, 'balanced')['model'] == 'future-d'


def test_no_silent_quality_or_cost_downgrade():
    with pytest.raises(ModelError):
        choose_model([{'model': 'mystery', 'description': 'Unknown model'}], 'economy')
    with pytest.raises(ModelError):
        choose_model([{'model': 'old', 'description': 'Older frontier model'}], 'quality')


def test_codex_catalog_failure_uses_cli_default_instead_of_disabling_provider(monkeypatch, tmp_path):
    import harness.models as models
    from harness.config import profiles
    from harness.workers import CODEX_CLI_DEFAULT, command

    def fail_catalog():
        raise ModelError('model/list failed during temporary outage')

    monkeypatch.setattr(models, 'codex_catalog', fail_catalog)
    monkeypatch.setattr(models.shutil, 'which', lambda _: '/usr/bin/agent-cli')
    resolved = models.resolve_workers({'researcher': profiles('balanced')})
    codex = resolved['workers']['researcher'][0]
    assert codex['provider'] == 'codex'
    assert codex['model'] == CODEX_CLI_DEFAULT
    assert 'unavailable' not in codex
    assert 'model/list failed' in codex['resolution']
    argv = command(codex, tmp_path)
    assert argv[0:2] == ['codex', 'exec']
    assert '-m' not in argv  # let the CLI select its own supported model
    assert '--json' in argv
    assert resolved['workers']['researcher'][1]['model'] == 'sonnet'


def test_unknown_codex_catalog_descriptions_fall_back_to_cli_default(monkeypatch):
    import harness.models as models
    from harness.config import profiles
    from harness.workers import CODEX_CLI_DEFAULT
    monkeypatch.setattr(models, 'codex_catalog',
                        lambda: [{'model': 'working-model', 'description': 'Undocumented'}])
    monkeypatch.setattr(models.shutil, 'which', lambda _: '/usr/bin/agent-cli')
    resolved = models.resolve_workers({'researcher': profiles('balanced')})
    codex = resolved['workers']['researcher'][0]
    assert codex['model'] == CODEX_CLI_DEFAULT
    assert 'unavailable' not in codex


def test_malformed_codex_catalog_response_still_keeps_cli_eligible(monkeypatch):
    import harness.models as models
    from harness.config import profiles
    from harness.workers import CODEX_CLI_DEFAULT

    def broken_catalog():
        raise KeyError('result')

    monkeypatch.setattr(models, 'codex_catalog', broken_catalog)
    monkeypatch.setattr(models.shutil, 'which', lambda _: '/usr/bin/agent-cli')
    resolved = models.resolve_workers({'producer': profiles('balanced')})
    assert resolved['workers']['producer'][0]['model'] == CODEX_CLI_DEFAULT
    assert 'unavailable' not in resolved['workers']['producer'][0]
    assert 'KeyError' in resolved['discovery_error']
