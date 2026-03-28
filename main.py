from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from producer import producer

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)


async def _worker(queue: asyncio.Queue):
    try:
        while True:
            value = await queue.get()
            print(value)
            queue.task_done()
    except asyncio.CancelledError as e:
        return


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.post("/upload/")
async def create_upload_file(file: UploadFile = File(...)):
    queu = asyncio.Queue(maxsize=10)
    async for value in producer(file, 1024):
        # This will block if the queue reaches 10 items without a consumer
        await queu.put(value)
    return {"filename": file.filename, "items_queued": queu.qsize()}
