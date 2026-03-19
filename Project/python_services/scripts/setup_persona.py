"""
Persona Setup Script (TripC v2 Standard)
==========================================
Mục tiêu: Bootstrap persona một lần duy nhất, lưu heygen_avatar_id vào DB.
Pipeline video sẽ dùng lại ID này mà không cần tạo avatar lại.

Setup flow:
1. Load persona record từ DB
2. Validate trường bắt buộc (voice, appearance_prompt)
3. Mark status = 'generating'
4. fal.ai sinh ảnh avatar chất lượng cao
5. Upload ảnh lên R2
6. Gửi ảnh tới HeyGen → nhận heygen_avatar_id
7. Lưu: avatar_image_url, heygen_avatar_id, avatar_status='ready'
8. In summary để operator xác nhận

Idempotency: Nếu persona đã có avatar_id hợp lệ → bỏ qua (dùng --force để ghi đè)

Chạy:
  .\.venv\Scripts\python scripts/setup_persona.py --persona_id=<ID>
  .\.venv\Scripts\python scripts/setup_persona.py --persona_id=<ID> --force
"""
import asyncio
import argparse
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.fal_service import FalAIService
from services.heygen_service import HeyGenService
from services.storage_service import StorageService
from services.errors import PersonaConfigurationError, FalAIServiceError, HeyGenAvatarSetupError
import httpx
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("setup_persona")


# ─── Fake in-memory persona store (thay bằng Supabase query thực tế) ──────────
DEMO_PERSONAS = {
    "persona_asia_01": {
        "persona_id": "persona_asia_01",
        "display_name": "Minh",
        "continent": "asia",
        "language": "vi-VN",
        "voice": "vi-VN-Wavenet-C",
        "appearance_prompt": (
            "Professional Asian male, 24 years old, friendly smile, "
            "modern casual clothing, high quality portrait, studio lighting, "
            "olive skin tone, dark hair"
        ),
        "heygen_avatar_id": None,
        "avatar_image_url": None,
        "avatar_status": "pending",
    }
}


def load_persona(persona_id: str) -> dict:
    """Load persona (thay bằng Supabase query thực tế)."""
    persona = DEMO_PERSONAS.get(persona_id)
    if not persona:
        raise PersonaConfigurationError(f"Persona '{persona_id}' không tìm thấy trong DB.")
    return persona


def validate_persona(persona: dict):
    """Validate các trường bắt buộc."""
    required = ["voice", "appearance_prompt", "display_name"]
    missing = [f for f in required if not persona.get(f)]
    if missing:
        raise PersonaConfigurationError(f"Persona thiếu các trường: {missing}")


async def setup_persona(persona_id: str, force: bool = False):
    print("=" * 60)
    print(f"  PERSONA SETUP: {persona_id}")
    print("=" * 60)

    # 1. Load và validate
    persona = load_persona(persona_id)
    validate_persona(persona)

    if persona.get("avatar_status") == "ready" and persona.get("heygen_avatar_id") and not force:
        print(f"\n✅ Persona đã ready. Avatar ID: {persona['heygen_avatar_id']}")
        print("   Dùng --force để setup lại.")
        return

    logger.info(f"Bắt đầu setup persona: {persona['display_name']}")

    try:
        # 2. Mark generating
        persona["avatar_status"] = "generating"
        print(f"\n[1/4] Status → generating")

        # 3. fal.ai sinh avatar image chất lượng cao
        print("\n[2/4] fal.ai sinh avatar image (chất lượng cao)...")
        fal = FalAIService()
        img_result = await fal.generate_image(
            prompt=persona["appearance_prompt"],
            model="fal-ai/flux/dev",  # High quality model cho avatar
            aspect_ratio="1:1",
        )
        avatar_image_url = img_result.get("url")
        assert avatar_image_url, "fal.ai không trả về URL ảnh"
        print(f"      ✅ Avatar image: {avatar_image_url}")

        # 4. Upload lên R2 (backup copy)
        print("\n[3/4] Upload avatar image lên R2...")
        storage = StorageService()
        async with httpx.AsyncClient() as client:
            r = await client.get(avatar_image_url)
            r.raise_for_status()

        r2_url = await storage.upload_bytes(
            data=r.content,
            filename=f"personas/{persona_id}/avatar.jpg",
            content_type="image/jpeg",
        )
        print(f"      ✅ R2 URL: {r2_url}")

        # 5. Gửi tới HeyGen
        print("\n[4/4] Tạo HeyGen avatar...")
        heygen = HeyGenService()
        heygen_result = await heygen.create_avatar(image_url=r2_url)
        heygen_avatar_id = heygen_result.get("avatar_id")
        if not heygen_avatar_id:
            raise HeyGenAvatarSetupError("HeyGen không trả về avatar_id")
        print(f"      ✅ HeyGen Avatar ID: {heygen_avatar_id}")

        # 6. Lưu vào DB (thay bằng Supabase update thực tế)
        persona.update({
            "avatar_image_url": r2_url,
            "heygen_avatar_id": heygen_avatar_id,
            "avatar_status": "ready",
        })

        print("\n" + "=" * 60)
        print("  PERSONA SETUP COMPLETE ✅")
        print("=" * 60)
        print(f"\n📋 Summary:")
        print(f"   persona_id:       {persona_id}")
        print(f"   avatar_image_url: {r2_url}")
        print(f"   heygen_avatar_id: {heygen_avatar_id}")
        print(f"   avatar_status:    ready")
        print(f"\n   ⚠️  Lưu heygen_avatar_id này vào Supabase personas table!")

    except (PersonaConfigurationError, FalAIServiceError, HeyGenAvatarSetupError) as e:
        persona["avatar_status"] = "failed"
        logger.error(f"Setup failed → status=failed | {e}")
        raise
    except Exception as e:
        persona["avatar_status"] = "failed"
        logger.error(f"Unexpected error → status=failed | {e}")
        raise
    finally:
        await fal.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup AI influencer persona for video pipeline.")
    parser.add_argument("--persona_id", required=True, help="Persona ID to setup")
    parser.add_argument("--force", action="store_true", help="Force re-setup even if already ready")
    args = parser.parse_args()
    asyncio.run(setup_persona(args.persona_id, force=args.force))
