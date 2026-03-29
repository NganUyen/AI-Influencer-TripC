"""
Persona Setup Script (TripC v2 Standard)
==========================================
Mục tiêu: Bootstrap persona một lần duy nhất, lưu heygen_avatar_id vào DB.
Pipeline video sẽ dùng lại ID này mà không cần tạo avatar lại.

Setup flow:
1. Load persona record từ DB
2. Validate trường bắt buộc (voice, appearance_prompt)
3. Mark status = 'generating'
4. fal.ai sinh ảnh avatar chất lượng cao (bỏ qua nếu đã có)
5. Upload anh len object storage
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
from services.persona_registry_service import PersonaRegistryService
from services.errors import PersonaConfigurationError, FalAIServiceError, HeyGenAvatarSetupError, HeyGenTimeoutError
import httpx
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("setup_persona")


async def load_persona(persona_id: str) -> dict:
    """Load persona using PersonaRegistryService"""
    personas = await PersonaRegistryService._find_personas_by_id_global(persona_id)
    if not personas:
        raise PersonaConfigurationError(f"Persona '{persona_id}' không tìm thấy trong DB.")
    return personas[0]  # Take the first matched persona


def validate_persona(persona: dict):
    """Validate các trường bắt buộc."""
    required = ["tts_voice", "display_name"]
    missing = [f for f in required if not persona.get(f)]
    if missing:
        raise PersonaConfigurationError(f"Persona thiếu các trường: {missing}")


async def setup_persona(persona_id: str, force: bool = False):
    print("=" * 60)
    print(f"  PERSONA SETUP: {persona_id}")
    print("=" * 60)

    # 1. Load và validate
    persona = await load_persona(persona_id)
    validate_persona(persona)

    if str(persona.get("status")) == "ready" and persona.get("heygen_avatar_id") and not force:
        print(f"\n✅ Persona đã ready. Avatar ID: {persona['heygen_avatar_id']}")
        print("   Dùng --force để setup lại.")
        return

    logger.info(f"Bắt đầu setup persona: {persona.get('display_name')}")

    try:
        # 2. Mark generating
        await PersonaRegistryService.update_persona(
            persona_id, 
            {"status": "generating"}, 
            user_id=persona.get("user_id")
        )
        print(f"\n[1/4] Status → generating")

        # 3. fal.ai sinh avatar image chất lượng cao (hoặc tái sử dụng)
        if not persona.get("avatar_image_url") or force:
            print("\n[2/4] fal.ai sinh avatar image (chất lượng cao)...")
            fal = FalAIService()
            try:
                img_result = await fal.generate_image(
                    prompt=persona.get("avatar_prompt", "Professional dynamic headshot"),
                    model="fal-ai/flux/dev",  # High quality model cho avatar
                    aspect_ratio="1:1",
                )
                avatar_image_url = img_result.get("url")
                assert avatar_image_url, "fal.ai không trả về URL ảnh"
                print(f"      ✅ Avatar image: {avatar_image_url}")

                # 4. Upload len object storage
                print("\n[3/4] Upload avatar image len object storage...")
                storage = StorageService()
                async with httpx.AsyncClient() as client:
                    r = await client.get(avatar_image_url)
                    r.raise_for_status()

                storage_url = await storage.upload_bytes(
                    data=r.content,
                    filename=f"personas/{persona_id}/avatar.jpg",
                    content_type="image/jpeg",
                )
                print(f"      ✅ Storage URL: {storage_url}")
            finally:
                await fal.close()
        else:
            storage_url = persona.get("avatar_image_url")
            print(f"\n[2/4] Sử dụng avatar url hiện có: {storage_url}")
            print("\n[3/4] Bỏ qua upload storage vì ảnh đã có sẵn...")

        # 5. Gửi tới HeyGen
        print("\n[4/4] Tạo HeyGen avatar...")
        heygen = HeyGenService()
        heygen_avatar_id = await heygen.create_avatar(image_url=storage_url)
        if not heygen_avatar_id:
            raise HeyGenAvatarSetupError("HeyGen không trả về avatar_id")
        print(f"      ✅ HeyGen Avatar ID: {heygen_avatar_id}")
        print("      ⏳ Đợi HeyGen xác nhận avatar đã sẵn sàng...")
        await heygen.wait_for_avatar_ready(
            heygen_avatar_id,
            timeout_seconds=120,
            poll_interval=10,
        )
        print("      ✅ HeyGen avatar is ready")

        # 6. Lưu vào DB 
        await PersonaRegistryService.update_persona(
            persona_id, 
            {
                "avatar_image_url": storage_url,
                "heygen_avatar_id": heygen_avatar_id,
                "status": "ready"
            },
            user_id=persona.get("user_id")
        )

        print("\n" + "=" * 60)
        print("  PERSONA SETUP COMPLETE ✅")
        print("=" * 60)
        print(f"\n📋 Summary:")
        print(f"   persona_id:       {persona_id}")
        print(f"   avatar_image_url: {storage_url}")
        print(f"   heygen_avatar_id: {heygen_avatar_id}")
        print(f"   status:           ready")

    except (PersonaConfigurationError, FalAIServiceError, HeyGenAvatarSetupError, HeyGenTimeoutError) as e:
        await PersonaRegistryService.update_persona(
            persona_id, {"status": "failed"}, user_id=persona.get("user_id")
        )
        logger.error(f"Setup failed → status=failed | {e}")
        raise
    except Exception as e:
        await PersonaRegistryService.update_persona(
            persona_id, {"status": "failed"}, user_id=persona.get("user_id")
        )
        logger.error(f"Unexpected error → status=failed | {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup AI influencer persona for video pipeline.")
    parser.add_argument("--persona_id", required=True, help="Persona ID to setup")
    parser.add_argument("--force", action="store_true", help="Force re-setup even if already ready")
    args = parser.parse_args()
    asyncio.run(setup_persona(args.persona_id, force=args.force))
