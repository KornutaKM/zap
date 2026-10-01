from dataclasses import dataclass

from app.cache_backend import SearchCache, build_search_cache
from app.checkout import CheckoutRegistry, GenericHttpCheckoutAdapter, HttpCheckoutConfig
from app.external_fitment import GenericHttpFitmentCatalog, HttpFitmentConfig
from app.external_provider import GenericHttpProvider, HttpProviderConfig
from app.external_vehicle import GenericHttpVehicleResolver, HttpVehicleResolverConfig
from app.fitment import DemoFitmentCatalog, FitmentCatalog
from app.providers import AutodocProvider, ExistProvider, MockProvider, PartsProvider
from app.search_service import PartsSearchService
from app.vehicle_resolution import NullVehicleResolver, VehicleResolver


@dataclass(slots=True)
class AppServices:
    providers: list[PartsProvider]
    fitment_catalog: FitmentCatalog | None
    search_cache: SearchCache
    search_service: PartsSearchService
    vehicle_resolver: VehicleResolver
    checkout_registry: CheckoutRegistry


def build_providers(settings) -> list[PartsProvider]:
    providers: list[PartsProvider] = [ExistProvider(), AutodocProvider()]

    if settings.demo_provider_enabled:
        providers.insert(0, MockProvider())

    if settings.external_provider_enabled and settings.external_provider_base_url:
        providers.append(
            GenericHttpProvider(
                HttpProviderConfig(
                    name=settings.external_provider_name,
                    base_url=settings.external_provider_base_url,
                    search_path=settings.external_provider_search_path,
                    api_key=settings.external_provider_api_key,
                    api_key_header=settings.external_provider_api_key_header,
                    auth_scheme=settings.external_provider_auth_scheme,
                    allow_http=settings.external_provider_allow_http,
                )
            )
        )
    return providers


def build_fitment_catalog(settings) -> FitmentCatalog | None:
    if settings.fitment_api_enabled and settings.fitment_api_base_url:
        return GenericHttpFitmentCatalog(
            HttpFitmentConfig(
                base_url=settings.fitment_api_base_url,
                resolve_path=settings.fitment_api_resolve_path,
                api_key=settings.fitment_api_key,
                api_key_header=settings.fitment_api_key_header,
                auth_scheme=settings.fitment_api_auth_scheme,
                allow_http=settings.fitment_api_allow_http,
            )
        )
    if settings.demo_fitment_enabled:
        return DemoFitmentCatalog()
    return None


def build_vehicle_resolver(settings) -> VehicleResolver:
    if settings.vehicle_api_enabled and settings.vehicle_api_base_url:
        return GenericHttpVehicleResolver(
            HttpVehicleResolverConfig(
                base_url=settings.vehicle_api_base_url,
                vin_path=settings.vehicle_api_vin_path,
                api_key=settings.vehicle_api_key,
                api_key_header=settings.vehicle_api_key_header,
                auth_scheme=settings.vehicle_api_auth_scheme,
                allow_http=settings.vehicle_api_allow_http,
            )
        )
    return NullVehicleResolver()


def build_checkout_registry(settings) -> CheckoutRegistry:
    adapters = []
    if settings.checkout_api_enabled and settings.checkout_api_base_url:
        adapters.append(
            GenericHttpCheckoutAdapter(
                HttpCheckoutConfig(
                    provider_name=settings.checkout_api_provider_name,
                    base_url=settings.checkout_api_base_url,
                    create_path=settings.checkout_api_create_path,
                    status_path=settings.checkout_api_status_path,
                    api_key=settings.checkout_api_key,
                    api_key_header=settings.checkout_api_key_header,
                    auth_scheme=settings.checkout_api_auth_scheme,
                    allow_http=settings.checkout_api_allow_http,
                )
            )
        )
    return CheckoutRegistry(adapters)


def build_app_services(settings) -> AppServices:
    providers = build_providers(settings)
    fitment_catalog = build_fitment_catalog(settings)
    search_cache = build_search_cache(
        settings.search_cache_backend,
        settings.redis_url,
    )
    search_service = PartsSearchService(
        providers,
        cache_ttl_seconds=settings.search_cache_ttl_seconds,
        provider_timeout_seconds=settings.provider_timeout_seconds,
        fitment_catalog=fitment_catalog,
        circuit_failure_threshold=settings.provider_circuit_failure_threshold,
        circuit_cooldown_seconds=settings.provider_circuit_cooldown_seconds,
        cache=search_cache,
    )
    return AppServices(
        providers=providers,
        fitment_catalog=fitment_catalog,
        search_cache=search_cache,
        search_service=search_service,
        vehicle_resolver=build_vehicle_resolver(settings),
        checkout_registry=build_checkout_registry(settings),
    )
