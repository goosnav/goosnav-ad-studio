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


@pytest.mark.parametrize('tier,family', [('quality', 'astra'), ('balanced', 'sol'), ('economy', 'luna')])
def test_new_family_release_wins_even_if_catalog_order_and_default_lag(tier, family):
    models = [
        {'model': f'gpt-6-{family}', 'description': 'Current model', 'isDefault': True},
        {'model': f'gpt-6.2-{family}', 'description': 'Current model'},
        {'model': f'gpt-5.6-{family}', 'description': 'Current model'},
        {'model': f'gpt-7-{family}', 'description': 'Hidden preview', 'hidden': True},
    ]
    assert choose_model(models, tier)['model'] == f'gpt-6.2-{family}'


def test_preset_effort_adapts_to_catalog_supported_efforts(monkeypatch):
    import harness.models as models
    monkeypatch.setattr(models, 'codex_catalog', lambda: [
        {'model': 'gpt-9-astra', 'description': 'Frontier intelligence',
         'supportedReasoningEfforts': [{'reasoningEffort': 'medium'}, {'reasoningEffort': 'xhigh'}]}])
    monkeypatch.setattr(models.shutil, 'which', lambda _: '/usr/bin/cli')
    result = models.resolve_workers({'writer': [{'provider': 'codex', 'model': 'auto:quality', 'effort': 'high'}]})
    profile = result['workers']['writer'][0]
    assert profile['model'] == 'gpt-9-astra'
    assert profile['effort'] in ('medium', 'xhigh')
    assert 'effort' in profile['resolution'].lower()


def test_no_silent_quality_or_cost_downgrade():
    with pytest.raises(ModelError):
        choose_model([{'model': 'mystery', 'description': 'Unknown model'}], 'economy')
    with pytest.raises(ModelError):
        choose_model([{'model': 'old', 'description': 'Older frontier model'}], 'quality')


def route(resolved, provider):
    return next(p for p in resolved['workers']['researcher'] if p['provider'] == provider)


def test_codex_catalog_failure_uses_cli_default_instead_of_disabling_provider(monkeypatch, tmp_path):
    import harness.models as models
    from harness.config import profiles
    from harness.workers import CODEX_CLI_DEFAULT, command

    def fail_catalog():
        raise ModelError('model/list failed during temporary outage')

    monkeypatch.setattr(models, 'codex_catalog', fail_catalog)
    monkeypatch.setattr(models.shutil, 'which', lambda _: '/usr/bin/agent-cli')
    resolved = models.resolve_workers({'researcher': profiles('balanced')})
    codex = route(resolved, 'codex')
    assert codex['provider'] == 'codex'
    assert codex['model'] == CODEX_CLI_DEFAULT
    assert 'unavailable' not in codex
    assert 'model/list failed' in codex['resolution']
    argv = command(codex, tmp_path)
    assert argv[0:2] == ['codex', 'exec']
    assert '-m' not in argv  # let the CLI select its own supported model
    assert '--json' in argv
    assert route(resolved, 'claude')['model'] == 'sonnet'


def test_unknown_codex_catalog_descriptions_fall_back_to_cli_default(monkeypatch):
    import harness.models as models
    from harness.config import profiles
    from harness.workers import CODEX_CLI_DEFAULT
    monkeypatch.setattr(models, 'codex_catalog',
                        lambda: [{'model': 'working-model', 'description': 'Undocumented'}])
    monkeypatch.setattr(models.shutil, 'which', lambda _: '/usr/bin/agent-cli')
    resolved = models.resolve_workers({'researcher': profiles('balanced')})
    codex = route(resolved, 'codex')
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
    assert next(r for r in resolved['workers']['producer'] if r['provider'] == 'codex')['model'] == CODEX_CLI_DEFAULT
    assert 'unavailable' not in next(r for r in resolved['workers']['producer'] if r['provider'] == 'codex')
    assert 'KeyError' in resolved['discovery_error']
