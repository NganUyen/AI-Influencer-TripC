"""
Shared asyncpg access helpers for customer-facing services.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover - depends on env
    asyncpg = None

from config.settings import settings


class DatabaseService:
    _pool: Optional[Any] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_pool(cls) -> Any:
        if asyncpg is None:
            raise RuntimeError("asyncpg is not installed")

        if cls._pool is None:
            async with cls._lock:
                if cls._pool is None:
                    cls._pool = await asyncpg.create_pool(
                        dsn=settings.DATABASE_URL,
                        min_size=max(1, int(settings.DATABASE_POOL_MIN_SIZE)),
                        max_size=max(
                            int(settings.DATABASE_POOL_MIN_SIZE),
                            int(settings.DATABASE_POOL_MAX_SIZE),
                        ),
                        command_timeout=max(
                            1,
                            int(settings.DATABASE_POOL_COMMAND_TIMEOUT_SECONDS),
                        ),
                    )
        return cls._pool

    @classmethod
    async def close_pool(cls) -> None:
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None
