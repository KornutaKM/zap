import pathlib


def test_production_compose_contains_shared_services():
    text = pathlib.Path("docker-compose.prod.yml").read_text()
    assert "postgres:" in text
    assert "redis:" in text
    assert "db-init:" in text
    assert "worker:" in text
    assert "order-worker:" in text
    assert 'command: ["python", "-m", "app.db_init"]' in text
    assert 'command: ["python", "-m", "app.worker"]' in text
    assert 'command: ["python", "-m", "app.order_worker"]' in text
    assert "SEARCH_CACHE_BACKEND: redis" in text
    assert "RATE_LIMIT_BACKEND: redis" in text
    assert "PRICE_ALERT_WORKER_MODE: external" in text
    assert "condition: service_completed_successfully" in text
