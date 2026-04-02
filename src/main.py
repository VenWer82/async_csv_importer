from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from .producer import producer

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)


async def _worker(id: int, queue: asyncio.Queue):
    try:
        while True:
            value = await queue.get()
            print(f"Worker {id}: {value}")
            queue.task_done()
    except asyncio.CancelledError as e:
        print(f"Worker {id} cancelled: {e}")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.post("/upload/")
async def create_upload_file(file: UploadFile = File(...)):
    queu = asyncio.Queue(maxsize=10)
    tasks = []
    if file.size is not None and file.size > 10 * 1024 * 1024:
        # Limit file size to 10MB
        tasks = [asyncio.create_task(_worker(i, queu)) for i in range(4)]
        async for value in producer(file, 1024):
            # This will block if the queue reaches 10 items without a consumer
            await queu.put(value)
        await queu.join()
        for w in tasks:
            w.cancel()  # Wait until all items have been processed
    return {"filename": file.filename, "items_queued": queu.qsize()}
