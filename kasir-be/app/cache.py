import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None
MENU_TTL = 300


async def init(url: str) -> None:
    global _redis
    _redis = aioredis.from_url(url, encoding="utf-8", decode_responses=True)


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def get(key: str) -> Any | None:
    if _redis is None:
        return None
    try:
        raw = await _redis.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception:
        logger.warning("Redis get failed for %s", key, exc_info=True)
        return None


async def set(key: str, value: Any, ttl: int = MENU_TTL) -> None:
    if _redis is None:
        return
    try:
        await _redis.set(key, json.dumps(value), ex=ttl)
    except Exception:
        logger.warning("Redis set failed for %s", key, exc_info=True)


async def delete(*keys: str) -> None:
    if _redis is None or not keys:
        return
    try:
        await _redis.delete(*keys)
    except Exception:
        logger.warning("Redis delete failed for %s", keys, exc_info=True)


def menu_key(store_id: str) -> str:
    return f"menu:{store_id}"


def cats_key(store_id: str) -> str:
    return f"cats:{store_id}"
