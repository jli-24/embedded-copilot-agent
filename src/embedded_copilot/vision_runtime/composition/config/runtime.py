from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import urlsplit

_TAILSCALE_IPV4 = ipaddress.ip_network("100.64.0.0/10")
_TAILSCALE_IPV6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
_MODEL_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class VisionSettingsSource(Protocol):
    vision_provider: str
    ollama_vision_base_url: str
    ollama_vision_model: str | None
    ollama_vision_require_tls: bool
    request_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class VisionRuntimeConfig:
    provider: Literal["unavailable", "ollama"]
    base_url: str | None
    model: str | None
    timeout_seconds: float
    require_tls: bool


def load_vision_runtime_config(
    settings: VisionSettingsSource,
) -> VisionRuntimeConfig:
    if settings.vision_provider == "unavailable":
        return VisionRuntimeConfig(
            provider="unavailable",
            base_url=None,
            model=None,
            timeout_seconds=settings.request_timeout_seconds,
            require_tls=False,
        )
    if settings.vision_provider != "ollama":
        raise ValueError("vision runtime configuration is invalid")
    try:
        model = _model_identifier(settings.ollama_vision_model)
        base_url = _validated_base_url(
            settings.ollama_vision_base_url,
            require_tls=settings.ollama_vision_require_tls,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("vision runtime configuration is invalid") from error
    return VisionRuntimeConfig(
        provider="ollama",
        base_url=base_url,
        model=model,
        timeout_seconds=settings.request_timeout_seconds,
        require_tls=settings.ollama_vision_require_tls,
    )


def _model_identifier(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("vision model identifier is invalid")
    model = value.strip()
    if not _MODEL_IDENTIFIER.fullmatch(model):
        raise ValueError("vision model identifier is invalid")
    return model


def _validated_base_url(value: object, *, require_tls: bool) -> str:
    if not isinstance(value, str):
        raise ValueError("vision endpoint is invalid")
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or (require_tls and parsed.scheme != "https")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.hostname is None
    ):
        raise ValueError("vision endpoint is invalid")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError("vision endpoint is invalid") from error
    host = parsed.hostname.casefold()
    if host != "localhost":
        try:
            address = ipaddress.ip_address(host)
        except ValueError as error:
            raise ValueError("vision endpoint is invalid") from error
        if not (
            address.is_loopback
            or address in _TAILSCALE_IPV4
            or address in _TAILSCALE_IPV6
        ):
            raise ValueError("vision endpoint is invalid")
    return candidate.rstrip("/")
