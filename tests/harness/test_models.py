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
