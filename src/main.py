import asyncio
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import asyncpg
from aiofiles import open as aio_open
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from .db.db import db, get_db
from .services.worker import _worker
from .services.producer import producer, handle_large_file
from .utils.utils import prepare_table

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





async def runner(file: UploadFile, queue: asyncio.Queue, conn: asyncpg.Connection):
    tasks = []
    table_name = (
        file.filename.rsplit(".", 1)[0]
        if file.filename
        else f"import_{os.urandom(4).hex()}"
    )
    try:

        # Instantiate the generator once so we can pull the header separately
        gen = producer(file, 1024)

        try:
            header_line = await anext(gen)
        except StopAsyncIteration:
            return  # File was empty

        table_name, sanitized_headers = await prepare_table(
            header_line, conn, table_name
        )
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
