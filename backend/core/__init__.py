"""Core package exports without import-time network or client construction."""

from __future__ import annotations

from .resources import close_core_clients, get_core_clients, warm_core_clients
from .sas import get_container_sas_token

_CLIENT_EXPORTS = {
    "credential",
    "async_credential",
    "sora_client",
    "image_client",
    "llm_client",
    "async_llm_client",
}


class _LazyClientProxy:
    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attribute: str):
        client = getattr(get_core_clients(), self._name)
        return getattr(client, attribute)

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"<lazy core client {self._name}>"


_CLIENT_PROXIES = {name: _LazyClientProxy(name) for name in _CLIENT_EXPORTS}


def __getattr__(name: str):
    if name in _CLIENT_EXPORTS:
        return _CLIENT_PROXIES[name]
    raise AttributeError(name)


__all__ = [
    "close_core_clients",
    "get_container_sas_token",
    "get_core_clients",
    "warm_core_clients",
    *_CLIENT_EXPORTS,
]
