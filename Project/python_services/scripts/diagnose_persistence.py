import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def diagnose_persistence():
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
            print(f"CRITICAL: User {user_id} DOES NOT EXIST in public.users table!")

        # 3. Check Telegram linking
        # Since I don't have the chat_id from the user's message, 
        # let's look for any links to this user_id.
        links = await conn.fetch(
            "SELECT owner_key, user_id FROM public.telegram_links WHERE user_id = $1::uuid", user_id
        )
        if links:
            print("Telegram Links for this user:")
            for l in links:
                print(f" - {l['owner_key']}")
        else:
            print("No Telegram Links found for this user_id.")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_persistence())
