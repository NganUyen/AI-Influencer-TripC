import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def check_persona():
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is missing!")
        return

    try:
        conn = await asyncpg.connect(dsn)
        row = await conn.fetchrow(
            "SELECT id, persona_id, status, avatar_media_asset_id, heygen_avatar_id FROM public.personas WHERE persona_id = 'heyeye' LIMIT 1"
        )
        if row:
            print("--- PERSONA STATUS ---")
            print(f"ID: {row['id']}")
            print(f"Persona ID: {row['persona_id']}")
            print(f"Status: {row['status']}")
            print(f"Avatar media asset ID: {row['avatar_media_asset_id']}")
            print(f"HeyGen avatar ID: {row['heygen_avatar_id']}")
        else:
            print("Persona 'heyeye' not found in database.")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_persona())
