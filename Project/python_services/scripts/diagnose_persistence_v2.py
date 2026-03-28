import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def diagnose_persistence_v2():
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is missing!")
        return

    try:
        conn = await asyncpg.connect(dsn)
        
        # 1. Check persona
        persona = await conn.fetchrow(
            "SELECT id, persona_id, user_id, status FROM public.personas WHERE persona_id = 'heyeye' LIMIT 1"
        )
        if not persona:
            print("Persona 'heyeye' not found.")
            return

        user_id = persona['user_id']
        print(f"Persona 'heyeye' is owned by user_id: {user_id}")

        # 2. Check user existence
        user = await conn.fetchrow(
            "SELECT id, email, name FROM public.users WHERE id = $1::uuid", user_id
        )
        if user:
            print(f"User exists: {user['email']} ({user['name']})")
        else:
            print(f"User {user_id} DOES NOT EXIST in public.users table!")

        # 3. Check Telegram linking (CORRECTED TABLE NAME)
        links = await conn.fetch(
            "SELECT chat_id, user_id, telegram_username FROM public.telegram_user_links WHERE user_id = $1::uuid", user_id
        )
        if links:
            print("Telegram Links for this user:")
            for l in links:
                print(f" - Chat ID: {l['chat_id']}, Username: {l['telegram_username']}")
        else:
            print("No Telegram Links found for this user_id in 'telegram_user_links'.")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_persistence_v2())
