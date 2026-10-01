import json
import logging

from app.observability import JsonFormatter, _redact


def test_redact_hides_sensitive_fields():
    value = _redact(
        {
            "api_key": "abc",
            "nested": {"authorization": "Bearer x"},
            "provider": "shop",
        }
    )
    assert value["api_key"] == "***"
    assert value["nested"]["authorization"] == "***"
    assert value["provider"] == "shop"


def test_json_formatter_outputs_structured_event():
    record = logging.LogRecord(
        name="zap.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="provider state changed",
        args=(),
        exc_info=None,
    )
    record.event = "provider_state"
    record.data = {"provider": "Partner", "secret_token": "hidden"}

    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "provider_state"
    assert payload["data"]["provider"] == "Partner"
    assert payload["data"]["secret_token"] == "***"
