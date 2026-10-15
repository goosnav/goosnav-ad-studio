import pytest
from harness.audio import validate_request


def test_audio_request_rejects_missing_text_or_unknown_provider():
    with pytest.raises(ValueError):validate_request({'provider':'kokoro','text':''})
    with pytest.raises(ValueError):validate_request({'provider':'whatever','text':'hi'})
    assert validate_request({'provider':'kokoro','text':'hello','voice':'af_heart'})['provider']=='kokoro'


def test_no_automatic_piper_downgrade():
    with pytest.raises(ValueError):validate_request({'provider':'piper','text':'hi'})
