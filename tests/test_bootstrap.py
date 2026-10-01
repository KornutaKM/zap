from types import SimpleNamespace

from app.bootstrap import build_app_services
from app.cache_backend import MemorySearchCache
from app.vehicle_resolution import NullVehicleResolver


def settings_stub(**overrides):
    values = dict(
        demo_provider_enabled=True,
        external_provider_enabled=False,
        external_provider_base_url=None,
        external_provider_name="Partner",
        external_provider_search_path="/search",
        external_provider_api_key=None,
        external_provider_api_key_header="Authorization",
        external_provider_auth_scheme="Bearer",
        external_provider_allow_http=False,
        checkout_api_enabled=False,
        checkout_api_provider_name="Partner",
        checkout_api_base_url=None,
        checkout_api_create_path="/orders",
        checkout_api_status_path="/orders/{external_order_id}",
        checkout_api_key=None,
        checkout_api_key_header="Authorization",
        checkout_api_auth_scheme="Bearer",
        checkout_api_allow_http=False,
        checkout_api_timeout_seconds=10,
        demo_fitment_enabled=True,
        fitment_api_enabled=False,
        fitment_api_base_url=None,
        fitment_api_resolve_path="/fitment/resolve",
        fitment_api_key=None,
        fitment_api_key_header="Authorization",
        fitment_api_auth_scheme="Bearer",
        fitment_api_allow_http=False,
        vehicle_api_enabled=False,
        vehicle_api_base_url=None,
        vehicle_api_vin_path="/vehicle/vin",
        vehicle_api_key=None,
        vehicle_api_key_header="Authorization",
        vehicle_api_auth_scheme="Bearer",
        vehicle_api_allow_http=False,
        search_cache_backend="memory",
        redis_url=None,
        search_cache_ttl_seconds=60,
        provider_timeout_seconds=5,
        provider_circuit_failure_threshold=3,
        provider_circuit_cooldown_seconds=60,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_bootstrap_builds_local_services():
    services = build_app_services(settings_stub())
    assert isinstance(services.search_cache, MemorySearchCache)
    assert isinstance(services.vehicle_resolver, NullVehicleResolver)
    assert services.fitment_catalog is not None
    assert len(services.providers) >= 3
