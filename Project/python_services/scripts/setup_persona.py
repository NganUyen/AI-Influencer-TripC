import argparse
import os
import sys

import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import logging

from services.errors import (
    FalAIServiceError,
    HeyGenAvatarSetupError,
    HeyGenTimeoutError,
    PersonaConfigurationError,
)
from services.fal_service import FalAIService
from services.heygen_service import HeyGenService
from services.media_storage_service import MediaStorageService
from services.persona_registry_service import (
    PersonaRegistryService,
    _SYSTEM_PERSONA_USER_ID,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("setup_persona")


async def load_persona(persona_id: str) -> dict:
    """Load the canonical global persona from the system scope."""
    persona = await PersonaRegistryService.get_persona(
        persona_id,
        user_id=_SYSTEM_PERSONA_USER_ID,
    )
    if not persona:
        raise PersonaConfigurationError(f"Persona '{persona_id}' không tìm thấy trong DB.")
    return persona


def validate_persona(persona: dict):
    """Validate các trường bắt buộc."""
    required = ["tts_voice", "display_name"]
    missing = [f for f in required if not persona.get(f)]
    if missing:
        raise PersonaConfigurationError(f"Persona thiếu các trường: {missing}")
    if (
        not persona.get("avatar_image_url")
        and not persona.get("avatar_media_asset_id")
        and not persona.get("avatar_prompt")
    ):
        raise PersonaConfigurationError(
            "Persona thiếu avatar_prompt hoặc avatar image hiện có."
        )


async def _generate_avatar_source(persona: dict) -> str:
    prompt = persona.get("avatar_prompt") or "Professional dynamic headshot"
    fal = FalAIService()
    try:
        img_result = await fal.generate_image(
            prompt=prompt,
            model="fal-ai/flux/dev",
            aspect_ratio="1:1",
        )
    finally:
        await fal.close()

    avatar_image_url = img_result.get("url")
    if not avatar_image_url:
        raise PersonaConfigurationError("fal.ai không trả về URL ảnh")
    return avatar_image_url


async def _persist_avatar_asset(
    *,
    persona_id: str,
    persona: dict,
    source_url: str,
) -> tuple[str, str]:
    media_storage = MediaStorageService()
    result = await media_storage.upload_from_url(
        source_url,
        asset_type="IMAGE",
        asset_kind="avatar",
        asset_origin="generated",
        generation_prompt=persona.get("avatar_prompt") or "",
        user_id=persona.get("user_id") or _SYSTEM_PERSONA_USER_ID,
        persona_id=persona_id,
        metadata={
            "operator": "setup_persona",
            "persona_id": persona_id,
            "display_name": persona.get("display_name"),
        },
        file_name_hint="avatar",
    )
    if not result:
        raise PersonaConfigurationError("Không thể lưu avatar vào object storage.")

    access_url = result.get("access_url") or result.get("url")
    media_asset_id = result.get("media_asset_id")
    if not access_url or not media_asset_id:
        raise PersonaConfigurationError(
            "Avatar đã upload nhưng không nhận được media_asset_id hợp lệ."
        )
    return str(access_url), str(media_asset_id)


async def setup_persona(persona_id: str, force: bool = False):
    print("=" * 60)
    print(f"  PERSONA SETUP: {persona_id}")
    print("=" * 60)

    # 1. Load và validate
    persona = await load_persona(persona_id)
    validate_persona(persona)
    resolved_user_id = persona.get("user_id") or _SYSTEM_PERSONA_USER_ID

    if (
        str(persona.get("status")) == "ready"
        and persona.get("heygen_avatar_id")
        and persona.get("avatar_media_asset_id")
        and not force
    ):
        print(f"\n✅ Persona đã ready. Avatar ID: {persona['heygen_avatar_id']}")
        print("   Dùng --force để setup lại.")
        return

    logger.info(f"Bắt đầu setup persona: {persona.get('display_name')}")

    try:
        # 2. Mark generating
        await PersonaRegistryService.update_persona(
            persona_id,
            {"status": "generating"},
            user_id=resolved_user_id,
        )
        print(f"\n[1/4] Status → generating")

        avatar_source_type = str(persona.get("avatar_source_type") or "fal_ai")
        source_avatar_url = persona.get("avatar_image_url")

        # 3. fal.ai sinh avatar image chất lượng cao (hoặc tái sử dụng)
        if not source_avatar_url or force:
            print("\n[2/4] fal.ai sinh avatar image (chất lượng cao)...")
            source_avatar_url = await _generate_avatar_source(persona)
            avatar_source_type = "fal_ai"
            print(f"      ✅ Avatar image: {source_avatar_url}")
        else:
            print(f"\n[2/4] Sử dụng avatar url hiện có: {source_avatar_url}")

        storage_url = persona.get("avatar_image_url")
        avatar_media_asset_id = persona.get("avatar_media_asset_id")
        if force or not storage_url or not avatar_media_asset_id:
            print("\n[3/4] Upload avatar image len object storage...")
            storage_url, avatar_media_asset_id = await _persist_avatar_asset(
                persona_id=persona_id,
                persona=persona,
                source_url=source_avatar_url,
            )
            print(f"      ✅ Storage URL: {storage_url}")
            print(f"      ✅ Media Asset ID: {avatar_media_asset_id}")
        else:
            print("\n[3/4] Dùng avatar asset hiện có trong object storage...")
            print(f"      ✅ Storage URL: {storage_url}")
            print(f"      ✅ Media Asset ID: {avatar_media_asset_id}")

        await PersonaRegistryService.update_persona(
            persona_id,
            {
                "avatar_image_url": storage_url,
                "avatar_media_asset_id": avatar_media_asset_id,
                "avatar_source_type": avatar_source_type,
            },
            user_id=resolved_user_id,
        )

        # 5. Gửi tới HeyGen
        print("\n[4/4] Tạo HeyGen avatar...")
        heygen = HeyGenService()
        heygen_avatar_id = await heygen.create_avatar(
            image_url=storage_url,
            avatar_name=f"{persona_id}-avatar",
            user_id=resolved_user_id,
        )
        if not heygen_avatar_id:
            raise HeyGenAvatarSetupError("HeyGen không trả về avatar_id")
        print(f"      ✅ HeyGen Avatar ID: {heygen_avatar_id}")
        print("      ⏳ Đợi HeyGen xác nhận avatar đã sẵn sàng...")
        await heygen.wait_for_avatar_ready(
            heygen_avatar_id,
            timeout_seconds=120,
            poll_interval=10,
            user_id=resolved_user_id,
        )
        print("      ✅ HeyGen avatar is ready")

        # 6. Lưu vào DB 
        await PersonaRegistryService.update_persona(
            persona_id,
            {
                "avatar_image_url": storage_url,
                "avatar_media_asset_id": avatar_media_asset_id,
                "avatar_source_type": avatar_source_type,
                "heygen_avatar_id": heygen_avatar_id,
                "status": "ready",
            },
            user_id=resolved_user_id,
        )

        print("\n" + "=" * 60)
        print("  PERSONA SETUP COMPLETE ✅")
        print("=" * 60)
        print(f"\n📋 Summary:")
        print(f"   persona_id:       {persona_id}")
        print(f"   avatar_image_url: {storage_url}")
        print(f"   media_asset_id:   {avatar_media_asset_id}")
        print(f"   heygen_avatar_id: {heygen_avatar_id}")
        print(f"   status:           ready")

    except (PersonaConfigurationError, FalAIServiceError, HeyGenAvatarSetupError, HeyGenTimeoutError) as e:
        await PersonaRegistryService.update_persona(
            persona_id,
            {"status": "failed"},
            user_id=resolved_user_id,
        )
        logger.error(f"Setup failed → status=failed | {e}")
        raise
    except Exception as e:
        await PersonaRegistryService.update_persona(
            persona_id,
            {"status": "failed"},
            user_id=resolved_user_id,
        )
        logger.error(f"Unexpected error → status=failed | {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup AI influencer persona for video pipeline.")
    parser.add_argument("--persona_id", required=True, help="Persona ID to setup")
    parser.add_argument("--force", action="store_true", help="Force re-setup even if already ready")
    args = parser.parse_args()
    asyncio.run(setup_persona(args.persona_id, force=args.force))
