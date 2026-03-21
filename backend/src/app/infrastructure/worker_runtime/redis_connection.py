from __future__ import annotations

from collections.abc import Callable
from typing import Any

import redis

_FAKE_REDIS_SERVERS: dict[str, Any] = {}


def build_queue_connection(redis_url: str) -> Any:
    if redis_url.startswith("fakeredis://"):
        return _build_fakeredis_connection(redis_url)
    return redis.Redis.from_url(redis_url)


def build_queue_connection_factory(redis_url: str) -> Callable[[], Any]:
    def factory() -> Any:
        return build_queue_connection(redis_url)

    return factory


def _build_fakeredis_connection(redis_url: str) -> Any:
    try:
        import fakeredis
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "fakeredis support requires the fakeredis package to be installed."
        ) from exc
    server = _FAKE_REDIS_SERVERS.get(redis_url)
    if server is None:
        server = fakeredis.FakeServer()
        _FAKE_REDIS_SERVERS[redis_url] = server
    return fakeredis.FakeRedis(server=server)
