from contextlib import asynccontextmanager

import asyncpg

from app.config import settings


class Database:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    @asynccontextmanager
    async def acquire(self):
        if self.pool is None:
            raise RuntimeError("Database pool is not initialized")
        async with self.pool.acquire() as connection:
            yield connection


database = Database()

