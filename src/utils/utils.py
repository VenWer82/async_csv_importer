import os
import asyncpg


async def prepare_table(
    header_line: str, conn: asyncpg.Connection, table_name: str
) -> tuple[str, list[str]]:
    # Sanitize headers for SQL compatibility (lowercase, underscores instead of spaces/hyphens)
    raw_headers = [h.strip() for h in header_line.split(",")]
    sanitized_headers = [
        h.lower().replace(" ", "_").replace("-", "_") for h in raw_headers
    ]

    # Create a unique table for this import session

    col_defs = ", ".join([f"{h} TEXT" for h in sanitized_headers])
    try:
        await conn.execute(f"CREATE TABLE {table_name} ({col_defs})")

    except Exception as e:
        print(f"Error creating table {table_name}: {e}")
        raise
    print(f"Created table {table_name} with columns: {sanitized_headers}")
    return table_name, sanitized_headers
