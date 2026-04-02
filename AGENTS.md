# Project Guidelines

## Overview

**async-csv-importer** is a FastAPI-based service for asynchronously processing and importing CSV data. It streams large files to avoid memory overload, using a producer-consumer pattern with asyncio queues.

## Code Style

- **Python 3.12+** with type hints (PEP 484). All functions and public APIs must have type annotations.
- **Async/await**: All I/O operations use `async`/`await`. Never use blocking I/O in async contexts.
- **File encoding**: UTF-8 by default. Explicitly decode bytes to strings with `decode("utf-8")`.
- **Imports**: Organize as standard library → third-party → local modules, each group separated by a blank line.
- **Naming**: Use snake_case for functions/variables, CamelCase for classes.

## Architecture

The project follows a **producer-consumer pattern** with three main components:

1. **main.py** (FastAPI Application)
   - Handles HTTP endpoints for file uploads
   - Creates an asyncio.Queue (buffered, bounded to 10 items)
   - Orchestrates producer → queue → consumer flow
   - CORS middleware allows all origins (`*`)

2. **producer.py** (CSV Reader)
   - Async generator that reads file chunks (default 1024 bytes)
   - Handles partial line buffering: incomplete lines at chunk boundaries stay in `remainder` until the next chunk
   - Yields complete, stripped CSV lines
   - Processes files streaming without loading into memory

3. **test.py** (Test/Utility)
   - Currently a placeholder; should contain pytest tests

**Design rationale**: Streaming prevents memory exhaustion on large files. The bounded queue naturally throttles producers when consumers lag, preventing runaway memory growth.

## Build and Test

**Setup**:

```bash
# Create virtual environment (uv handles this)
uv sync

# Or manually create and activate .venv
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Run the server**:

```bash
# Development server with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or production
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Test**:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest test.py -v
```

**Test the upload endpoint**:

```bash
curl -F "file=@example.csv" http://localhost:8000/upload/
```

## Conventions

### Error Handling

- Partial reads (non-blocking) are normal in async I/O; handle `chunk_bytes == b""` as EOF
- Queue operations (put, get) should have explicit timeout handling in production code
- All exceptions in worker tasks must be caught to prevent silent failures

### File Processing

- Line splitting uses `"\n"` as the delimiter (hard-coded in producer.py)
- Whitespace on both ends of each line is stripped before yielding
- Empty remainder after EOF is skipped (see `if remainder: yield remainder.strip()`)

### Testing

- Use `pytest-asyncio` for async test functions (mark with `@pytest.mark.asyncio`)
- Mock UploadFile objects in tests; real file I/O is integration-tested via curl
- Queue sizes and chunk boundaries are critical; test edge cases (empty files, single byte, exact chunk boundaries)

### Queue & Buffering

- Queue maxsize=10 is hardcoded; adjust based on memory constraints
- The `_worker` coroutine in main.py is unused (placeholder); actual consumer implementation goes here
- All queue producers/consumers must handle `asyncio.CancelledError` gracefully

## Key Files

- **main.py**: Entry point; FastAPI app and upload handler
- **producer.py**: Core streaming logic; read this to understand chunking and line buffering
- **pyproject.toml**: Project metadata and dependencies; update version when releasing
- **.python-version**: Pins Python 3.12; matches pyproject.toml requirement
