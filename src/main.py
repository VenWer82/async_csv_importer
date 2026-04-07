import asyncio
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import asyncpg
from aiofiles import open as aio_open
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from .db.db import db, get_db

from .services.producer import producer, handle_large_file

load_dotenv()


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost/postgres"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the pool once for the entire application
    await db.connect()
    yield
    # Clean up the pool on shutdown
    await db.disconnect()


app = FastAPI(lifespan=lifespan)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)


async def _worker(
    worker_id: int,
    queue: asyncio.Queue,
    conn: asyncpg.Connection,
    table_name: str,
    headers: list[str],
):
    try:
        # Pre-build the insert query with the specific table and columns
        placeholders = ", ".join([f"${i+1}" for i in range(len(headers))])
        columns_str = ", ".join(headers)
        insert_query = (
            f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        )

        while True:
            value = await queue.get()
            try:
                # Parse the CSV line (naive split by comma)
                row_data = [v.strip() for v in value.split(",")]

                if len(row_data) != len(headers):
                    print(
                        f"Worker {worker_id}: Row length mismatch. Expected {len(headers)}, got {len(row_data)}"
                    )
                    continue

                await conn.execute(insert_query, *row_data)
            except Exception as e:
                print(f"Worker {worker_id} error processing item: {e}")
            finally:
                queue.task_done()
    except asyncio.CancelledError:
        pass


async def runner(file: UploadFile, queue: asyncio.Queue, conn: asyncpg.Connection):
    tasks = []
    try:

        # Instantiate the generator once so we can pull the header separately
        gen = producer(file, 1024)

        try:
            header_line = await anext(gen)
        except StopAsyncIteration:
            return  # File was empty

        # Sanitize headers for SQL compatibility (lowercase, underscores instead of spaces/hyphens)
        raw_headers = [h.strip() for h in header_line.split(",")]
        sanitized_headers = [
            h.lower().replace(" ", "_").replace("-", "_") for h in raw_headers
        ]

        # Create a unique table for this import session
        table_name = f"import_{os.urandom(4).hex()}"
        col_defs = ", ".join([f"{h} TEXT" for h in sanitized_headers])

        await conn.execute(f"CREATE TABLE {table_name} ({col_defs})")

        print(f"Created table {table_name} with columns: {sanitized_headers}")
        if file.size is not None and file.size <= 10 * 1024 * 1024:

            # Start workers with table context
            tasks = [
                asyncio.create_task(
                    _worker(i, queue, conn, table_name, sanitized_headers)
                )
                for i in range(4)
            ]

            async for line in gen:
                await queue.put(line)

            await queue.join()
            for w in tasks:
                w.cancel()
        else:
            await handle_large_file(file, conn, table_name)
    except asyncio.CancelledError:
        print("Runner cancelled")
    except Exception as e:
        print(f"Runner error: {e}")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.post("/upload/")
async def create_upload_file(
    backgroundtasks: BackgroundTasks,
    file: UploadFile = File(...),
    conn: asyncpg.Connection = Depends(get_db),
):
    queue = asyncio.Queue(maxsize=10)

    backgroundtasks.add_task(runner, file, queue, conn)
    return {"filename": file.filename, "items_queued": queue.qsize()}
