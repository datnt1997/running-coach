from collections.abc import AsyncIterator

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.config import DATABASE_URL

# Module-level pool, initialized via init_pool() during app lifespan.
_pool: AsyncConnectionPool | None = None


async def init_pool() -> AsyncConnectionPool:
    """Create and open the global async connection pool."""
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        _pool = AsyncConnectionPool(conninfo=DATABASE_URL, open=False)
        await _pool.open(wait=True)
    return _pool


async def close_pool() -> None:
    """Close the global async connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Connection pool is not initialized. Call init_pool() first.")
    return _pool


async def get_db() -> AsyncIterator[AsyncConnection]:
    """FastAPI dependency yielding a pooled async connection.

    The connection is returned to the pool when the request finishes. The
    surrounding transaction is committed on success and rolled back on error.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        yield conn
