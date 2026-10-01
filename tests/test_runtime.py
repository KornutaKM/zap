import pytest

from app.runtime import normalize_webhook_path, validate_webhook_url


def test_normalize_webhook_path():
    assert normalize_webhook_path("telegram") == "/telegram"
    assert normalize_webhook_path("/hook") == "/hook"
    assert normalize_webhook_path("") == "/webhook"


def test_webhook_url_requires_https():
    assert validate_webhook_url("https://bot.example.com/webhook").startswith("https://")
    with pytest.raises(ValueError):
        validate_webhook_url("http://bot.example.com/webhook")
    with pytest.raises(ValueError):
        validate_webhook_url(None)
