from dotenv import load_dotenv
import asyncpg
import os
from typing import AsyncGenerator

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost/postgres"
)


class Database:
    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.database_url)

    async def disconnect(self):
        if self.pool:
            await self.pool.close()


db = Database()


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:

    try:
        if db.pool is not None:
            async with db.pool.acquire() as conn:
                yield conn  # type: ignore
    except ConnectionError as e:
        print(f"Database connection error: {e}")
        raise
