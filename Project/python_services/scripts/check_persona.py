"""
Check Persona Readiness
========================
Dùng trước khi trigger pipeline đắt tiền.
Kiểm tra persona có đủ điều kiện để generate video không.

Chạy: .\.venv\Scripts\python scripts/check_persona.py --persona_id=<ID>
"""
import asyncio
import argparse
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


DEMO_PERSONAS = {
    "persona_asia_01": {
        "persona_id": "persona_asia_01",
        "display_name": "Minh",
        "voice": "vi-VN-Wavenet-C",
        "heygen_avatar_id": None,     # Set sau khi chạy setup_persona.py
        "avatar_image_url": None,
        "avatar_status": "pending",
    }
}


def check_persona(persona_id: str):
    print("=" * 55)
    print(f"  CHECK PERSONA: {persona_id}")
    print("=" * 55)

    persona = DEMO_PERSONAS.get(persona_id)
    if not persona:
        print(f"\n❌ Persona '{persona_id}' không tìm thấy.")
        return False

    checks = {
        "display_name": bool(persona.get("display_name")),
        "voice": bool(persona.get("voice")),
        "heygen_avatar_id": bool(persona.get("heygen_avatar_id")),
        "avatar_image_url": bool(persona.get("avatar_image_url")),
        "avatar_status == ready": persona.get("avatar_status") == "ready",
    }

    all_pass = all(checks.values())
    print()
    for field, ok in checks.items():
        status = "✅" if ok else "❌"
        value = persona.get(field.split(" ")[0], "—")
        print(f"  {status}  {field:30s}  {str(value)[:40]}")

    print()
    if all_pass:
        print("✅ Persona READY — có thể đưa vào pipeline video.")
    else:
        missing = [f for f, ok in checks.items() if not ok]
        print(f"❌ Persona NOT READY. Thiếu: {missing}")
        print("   → Chạy scripts/setup_persona.py trước.")

    return all_pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check persona readiness for video pipeline.")
    parser.add_argument("--persona_id", required=True, help="Persona ID to check")
    args = parser.parse_args()
    ready = check_persona(args.persona_id)
    sys.exit(0 if ready else 1)
