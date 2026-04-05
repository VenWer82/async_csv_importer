import asyncio
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


from .producer import producer

app = FastAPI()
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost/postgres"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the pool once for the entire application
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)
    yield
    # Clean up the pool on shutdown
    await app.state.pool.close()


app = FastAPI(lifespan=lifespan)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)


async def _worker(worker_id: int, queue: asyncio.Queue, pool: asyncpg.Pool):
    try:
        while True:
            # Get item from queue; this can be cancelled by the runner
            value = await queue.get()
            try:
                # Actual processing logic
                print(f"Worker {worker_id}: {value}")
                # value is a stripped CSV line from producer.py
                # In a real scenario, you'd parse 'value' here (e.g., value.split(','))
                async with pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO csv_data (raw_content) VALUES ($1)", value
                    )
            except Exception as e:
                # Catch processing errors so the worker stays alive for the next item
                print(f"Worker {worker_id} error processing item: {e}")
            finally:
                # Always signal completion to prevent queue.join() from hanging
                queue.task_done()
    except asyncio.CancelledError:
        # Expected when the runner cancels the tasks after processing is complete
        pass


async def runner(file: UploadFile, queue: asyncio.Queue, pool: asyncpg.Pool):
    tasks = []
    try:
        if file.size is not None and file.size <= 10 * 1024 * 1024:
            # Process files up to 10MB

            tasks = [asyncio.create_task(_worker(i, queue, pool)) for i in range(4)]
            async for value in producer(file, 1024):
                await queue.put(value)

            await queue.join()
            for w in tasks:
                w.cancel()

    except asyncio.CancelledError:
        print("Runner cancelled")
    except Exception as e:
        print(f"Runner error: {e}")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.post("/upload/")
async def create_upload_file(
    backgroundtasks: BackgroundTasks, file: UploadFile = File(...), app: FastAPI = app
):
    queue = asyncio.Queue(maxsize=10)

    backgroundtasks.add_task(runner, file, queue, app.state.pool)
    return {"filename": file.filename, "items_queued": queue.qsize()}
