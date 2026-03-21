"""Worker-lane RQ configuration helpers."""

from __future__ import annotations

import os
from typing import Any, Final, Literal, cast

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from worker._rq_shared_state import FAKE_SERVER_BY_URL

try:
    import fakeredis
except ImportError:  # pragma: no cover - optional in non-test runtime
    fakeredis = None

LaneName = Literal["simulation", "characterization"]

_QUEUE_NAME_ENV_VARS: Final[dict[LaneName, str]] = {
    "simulation": "SC_SIMULATION_QUEUE_NAME",
    "characterization": "SC_CHARACTERIZATION_QUEUE_NAME",
}
_QUEUE_NAME_DEFAULTS: Final[dict[LaneName, str]] = {
    "simulation": "simulation",
    "characterization": "characterization",
}

_FAKE_SERVER_BY_URL: dict[str, Any] = FAKE_SERVER_BY_URL


def default_stale_timeout_seconds() -> int:
    """Return the reconcile timeout used by worker probe and startup helpers."""
    raw_value = os.getenv("SC_WORKER_STALE_TIMEOUT_SECONDS", "300")
    return max(1, int(raw_value))


def resolve_queue_name(lane: LaneName) -> str:
    """Resolve one lane-specific RQ queue name."""
    override = os.getenv(_QUEUE_NAME_ENV_VARS[lane])
    if override is not None and override.strip():
        return override.strip()
    return _QUEUE_NAME_DEFAULTS[lane]


def resolve_redis_url(lane: LaneName) -> str:
    """Resolve the Redis URL backing the worker queues."""
    for env_name in ("SC_RQ_REDIS_URL", "SC_REDIS_URL"):
        raw_value = os.getenv(env_name)
        if raw_value is not None and raw_value.strip():
            return raw_value.strip()

    return "redis://127.0.0.1:6379/0"


def _create_fake_connection(url: str) -> Redis:
    if fakeredis is None:  # pragma: no cover - exercised only when test dep missing
        raise RuntimeError(
            "fakeredis is required for fakeredis:// worker queue URLs. "
            "Install the dev dependency group or configure SC_RQ_REDIS_URL."
        )

    server = _FAKE_SERVER_BY_URL.get(url)
    if server is None:
        server = fakeredis.FakeServer()
        _FAKE_SERVER_BY_URL[url] = server
    return fakeredis.FakeStrictRedis(server=cast(Any, server))


def reset_fake_backend_cache() -> None:
    """Clear the shared fake Redis registry used by test-only fakeredis URLs."""
    _FAKE_SERVER_BY_URL.clear()


def create_connection(lane: LaneName) -> Redis:
    """Create one lane-specific Redis connection."""
    redis_url = resolve_redis_url(lane)
    if redis_url.startswith("fakeredis://"):
        return _create_fake_connection(redis_url)
    return Redis.from_url(redis_url)


def ensure_connection_available(lane: LaneName) -> Redis:
    """Create one lane-specific Redis connection and verify reachability."""
    connection = create_connection(lane)
    try:
        connection.ping()
    except RedisError as exc:
        redis_url = resolve_redis_url(lane)
        raise RuntimeError(
            f"RQ backend for the {lane} lane is unavailable at {redis_url}. "
            "Set SC_RQ_REDIS_URL (or SC_REDIS_URL) to a reachable Redis instance."
        ) from exc
    return connection


def create_queue(lane: LaneName) -> Queue:
    """Create one lane-specific RQ queue."""
    return Queue(
        name=resolve_queue_name(lane),
        connection=create_connection(lane),
        default_timeout=-1,
    )
