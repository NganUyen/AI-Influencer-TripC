import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def list_tables():
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is missing!")
        return

    try:
        conn = await asyncpg.connect(dsn)
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        print("--- TABLES IN PUBLIC SCHEMA ---")
        for row in rows:
            print(f" - {row['table_name']}")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_tables())
