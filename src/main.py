import asyncio
import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import asyncpg
from aiofiles import open as aio_open
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .db.db import db
from .services.worker import _worker
from .services.producer import producer, handle_large_file
from .utils.utils import prepare_table
from .utils.deps import _get_db, file

load_dotenv()


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost/postgres"
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bgtasks")


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
            try:
                async with asyncio.TaskGroup() as tg:
                    # Start workers with table context
                    tasks = [
                        tg.create_task(
                            _worker(i, queue, conn, table_name, sanitized_headers)
                        )
                        for i in range(4)
                    ]

                    async for line in gen:
                        await queue.put(line)

                    await queue.join()
                    for w in tasks:
                        w.cancel()

            except* ValueError as eg:
                logger.error(
                    "Runner intercepted a ValueError exception group from workers:"
                )
                for exc in eg.exceptions:
                    logger.exception(f"Aggregated Error Detail: {exc}", exc_info=exc)
            except* Exception as eg:
                logger.error(
                    "Runner intercepted an unhandled Exception Group from workers:"
                )
                for exc in eg.exceptions:
                    logger.exception(
                        f"Aggregated Generic Error Detail: {exc}", exc_info=exc
                    )
        else:
            await handle_large_file(file, conn, table_name)

    except Exception as e:
        logger.error(f"Runner error: {e}")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.post("/upload/")
async def create_upload_file(
    backgroundtasks: BackgroundTasks,
    file: UploadFile = file,
    conn: asyncpg.Connection = _get_db,
):
    queue = asyncio.Queue(maxsize=10)

    backgroundtasks.add_task(runner, file, queue, conn)
    return {"filename": file.filename, "items_queued": queue.qsize()}
