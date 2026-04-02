# async-csv-importer

A FastAPI-based service for asynchronously processing and importing CSV data with streaming to handle large files efficiently.

## Quick Start

### Prerequisites

- Python 3.12+
- `uv` (recommended) or pip

### Setup

```bash
# Using uv
uv sync

# Or using pip + venv
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run

```bash
uvicorn main:app --reload
```

The server starts at `http://localhost:8000`

### Test

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest test.py -v

# Or manually test the upload endpoint
curl -F "file=@example.csv" http://localhost:8000/upload/
```

## API

### `GET /`

Health check endpoint. Returns:

```json
{ "message": "Hello World" }
```

### `POST /upload/`

Upload a CSV file for processing.

**Request**: Multipart form with `file` field

**Response**:

```json
{
  "filename": "your-file.csv",
  "items_queued": 0
}
```

**How it works**:

1. File is streamed in chunks (1024 bytes by default)
2. CSV lines are buffered and yielded one at a time
3. Lines are queued (max 10 items) for consumption
4. Returns the number of items queued (typically 0 after all processing is done)

## Architecture

This project uses a **producer-consumer pattern**:

- **Producer** ([producer.py](producer.py)): Reads file chunks, handles partial lines, yields complete CSV lines
- **Queue**: Bounded asyncio.Queue (maxsize=10) buffers between producer and consumer
- **Consumer**: Placeholder worker in [main.py](main.py) (implement your processing logic here)

See [AGENTS.md](AGENTS.md) for detailed development guidelines, code style, and conventions.

## Project Status

Actively maintained. Currently a template/framework for CSV import workflows.
