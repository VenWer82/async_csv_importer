import asyncio

import asyncpg


async def _worker(
    worker_id: int,
    queue: asyncio.Queue[str],
    conn: asyncpg.Connection,
    table_name: str,
    headers: list[str],
):

    # Pre-build the insert query with the specific table and columns
    placeholders = ", ".join([f"${i+1}" for i in range(len(headers))])
    columns_str = ", ".join(headers)
    insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
    value = None
    while True:
        try:
            value = await queue.get()
            # Parse the CSV line (naive split by comma)
            row_data: list[str] = [v.strip() for v in value.split(",")]

            if len(row_data) != len(headers):
                print(
                    f"Worker {worker_id}: Row length mismatch. Expected {len(headers)}, got {len(row_data)}"
                )
                queue.task_done()
                value = None
                continue

            await conn.execute(insert_query, *row_data)
            queue.task_done()
            value = None

        except asyncio.CancelledError:
            if value is not None:
                queue.task_done()
                value = None
            print(f"Worker {worker_id} cancelled")
            break

        except Exception as e:
            if value is not None:
                queue.task_done()
                value = None
                print(f"Worker {worker_id} error processing item: {e}")
            else:
                print(
                    f"Worker {worker_id} encountered an error before retrieving an item."
                )
            raise
