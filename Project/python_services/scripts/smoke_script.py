"""
Smoke Test: Script Generation
================================
Test ScriptService generates valid ScriptContract output using Gemini.

Chạy: .\.venv\Scripts\python scripts/smoke_script.py
"""
import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import json
from services.script_service import ScriptService
from services.contracts import ScriptContract


async def main():
    print("=" * 55)
    print("  SMOKE TEST: Script Generation (Gemini)")
    print("=" * 55)

    svc = ScriptService()

    print("\n▶ Generating script for TripC / Da Nang topic...")
    print("▶ Model: models/gemini-2.0-flash")

    try:
        contract: ScriptContract = await svc.generate_script(
            app_name="TripC",
            topic="Discover the best beaches in Da Nang",
            language="Vietnamese",
            voice_style="friendly, energetic Gen Z",
            market="Vietnam",
        )

        print(f"\n✅ ScriptContract validated!")
        print(f"   duration_estimate: {contract.duration_estimate}s")
        print(f"   scenes: {len(contract.scenes)}")
        print(f"\n📝 Script preview:")
        print(f"   {contract.script[:120]}...")

        print(f"\n🎬 Scene breakdown:")
        for s in contract.scenes:
            print(f"   [{s.timestamp_start:.0f}s-{s.timestamp_end:.0f}s] {s.caption}")

        # Dump full JSON
        output_file = "scripts/output_script_smoke.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(contract.model_dump(), f, ensure_ascii=False, indent=2)
        print(f"\n💾 Full JSON saved: {output_file}")

        print("\n" + "=" * 55)
        print("  SCRIPT SMOKE TEST PASSED ✅")
        print("=" * 55)

    except Exception as e:
        print(f"\n❌ SCRIPT SMOKE TEST FAILED: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
