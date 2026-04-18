import asyncio
from services.database_service import DatabaseService
import json

async def run():
    pool = await DatabaseService.get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT metadata FROM public.media_assets LIMIT 1")
        print(f"Type: {type(val)} Value: {repr(val)}")

asyncio.run(run())
