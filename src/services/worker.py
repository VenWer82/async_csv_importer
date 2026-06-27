import asyncio
import asyncpg


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
        print(f"Worker {worker_id} cancelled")
