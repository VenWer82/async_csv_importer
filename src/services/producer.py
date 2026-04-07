import asyncio
import asyncpg
from typing import AsyncGenerator
from fastapi import UploadFile


async def producer(file: UploadFile, n: int) -> AsyncGenerator[str, None]:
    remainder = ""
    while True:
        chunk_bytes = await file.read(n)
        if not chunk_bytes:
            if remainder:
                yield remainder.strip()
            break

        # Decode bytes and combine with the last partial string
        data = remainder + chunk_bytes.decode("utf-8")
        parts = data.split("\n")

        # Yield all complete parts (everything except the last index)
        for part in parts[:-1]:
            if part.strip():
                yield part.strip()

        # Keep the last part as the remainder for the next iteration
        remainder = parts[-1]


async def handle_large_file(
    file: UploadFile,
    conn: asyncpg.Connection,
    table_name: str,
):
    pass
