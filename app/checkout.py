from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from urllib.parse import quote, urljoin, urlparse

import aiohttp


@dataclass(frozen=True, slots=True)
class CheckoutLine:
    brand: str
    article: str
    title: str
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True, slots=True)
class CheckoutRequest:
    order_id: int
    group_id: int
    provider: str
    total: Decimal
    lines: tuple[CheckoutLine, ...]
    fallback_url: str | None = None


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    status: str
    mode: str
    external_order_id: str | None = None
    checkout_url: str | None = None
    error: str | None = None


class CheckoutAdapter(Protocol):
    provider_name: str

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        ...

    async def get_status(self, external_order_id: str) -> CheckoutResult:
        ...


class DeeplinkCheckoutAdapter:
    provider_name = "*"

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        if request.fallback_url and request.fallback_url.startswith(("https://", "http://")):
            return CheckoutResult(
                status="manual_required",
                mode="deeplink",
                checkout_url=request.fallback_url,
            )
        return CheckoutResult(
            status="failed",
            mode="unavailable",
            error="Поставщик не предоставил checkout API или deeplink.",
        )

    async def get_status(self, external_order_id: str) -> CheckoutResult:
        return CheckoutResult(
            status="unknown",
            mode="deeplink",
            external_order_id=external_order_id,
        )


@dataclass(frozen=True, slots=True)
class HttpCheckoutConfig:
    provider_name: str
    base_url: str
    create_path: str = "/orders"
    status_path: str = "/orders/{external_order_id}"
    api_key: str | None = None
    api_key_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    allow_http: bool = False
    timeout_seconds: float = 10.0

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("CHECKOUT_API_BASE_URL must be an absolute HTTP(S) URL")
        if parsed.scheme != "https" and not self.allow_http:
            raise ValueError("Checkout API must use HTTPS unless allow_http is enabled")


class GenericHttpCheckoutAdapter:
    def __init__(self, config: HttpCheckoutConfig) -> None:
        config.validate()
        self.config = config
        self.provider_name = config.provider_name

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            value = self.config.api_key
            if self.config.auth_scheme:
                value = f"{self.config.auth_scheme} {value}".strip()
            headers[self.config.api_key_header] = value
        return headers

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        url = urljoin(
            self.config.base_url.rstrip("/") + "/",
            self.config.create_path.lstrip("/"),
        )
        payload = {
            "idempotency_key": f"zap:{request.order_id}:{request.group_id}",
            "order_id": request.order_id,
            "group_id": request.group_id,
            "provider": request.provider,
            "currency": "RUB",
            "total": str(request.total),
            "items": [
                {
                    "brand": line.brand,
                    "article": line.article,
                    "title": line.title,
                    "quantity": line.quantity,
                    "unit_price": str(line.unit_price),
                }
                for line in request.lines
            ],
        }

        try:
            timeout = aiohttp.ClientTimeout(total=max(1.0, self.config.timeout_seconds))
            async with aiohttp.ClientSession(headers=self._headers(), timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()
                    data = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            return CheckoutResult(
                status="failed",
                mode="api",
                error=type(exc).__name__,
            )

        if not isinstance(data, dict):
            return CheckoutResult(
                status="failed",
                mode="api",
                error="invalid_payload",
            )

        external_order_id = data.get("external_order_id") or data.get("order_id")
        checkout_url = data.get("checkout_url")
        raw_status = str(data.get("status") or "placed").casefold()
        status = raw_status if raw_status in {
            "placed",
            "pending",
            "confirmed",
            "completed",
            "cancelled",
            "failed",
        } else "pending"

        return CheckoutResult(
            status=status,
            mode="api",
            external_order_id=str(external_order_id) if external_order_id else None,
            checkout_url=(
                str(checkout_url)
                if isinstance(checkout_url, str)
                and checkout_url.startswith(("https://", "http://"))
                else None
            ),
        )

    async def get_status(self, external_order_id: str) -> CheckoutResult:
        path = self.config.status_path.format(
            external_order_id=quote(external_order_id, safe="")
        )
        url = urljoin(
            self.config.base_url.rstrip("/") + "/",
            path.lstrip("/"),
        )
        try:
            timeout = aiohttp.ClientTimeout(total=max(1.0, self.config.timeout_seconds))
            async with aiohttp.ClientSession(headers=self._headers(), timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            return CheckoutResult(
                status="failed",
                mode="api",
                external_order_id=external_order_id,
                error=type(exc).__name__,
            )

        if not isinstance(data, dict):
            return CheckoutResult(
                status="failed",
                mode="api",
                external_order_id=external_order_id,
                error="invalid_payload",
            )

        raw_status = str(data.get("status") or "pending").casefold()
        status = raw_status if raw_status in {
            "placed",
            "pending",
            "confirmed",
            "completed",
            "cancelled",
            "failed",
        } else "pending"
        return CheckoutResult(
            status=status,
            mode="api",
            external_order_id=external_order_id,
            checkout_url=(
                str(data["checkout_url"])
                if isinstance(data.get("checkout_url"), str)
                and str(data["checkout_url"]).startswith(("https://", "http://"))
                else None
            ),
        )


class CheckoutRegistry:
    def __init__(self, adapters: list[CheckoutAdapter] | None = None) -> None:
        self._adapters = {
            adapter.provider_name.casefold(): adapter
            for adapter in (adapters or [])
        }
        self._fallback = DeeplinkCheckoutAdapter()

    def for_provider(self, provider: str) -> CheckoutAdapter:
        return self._adapters.get(provider.casefold(), self._fallback)
