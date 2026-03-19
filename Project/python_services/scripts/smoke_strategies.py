"""
Smoke Test: Carousel + Long Post Strategy
==========================================
Validates generate_carousel_strategy and generate_long_post_strategy
using Gemini AI (no external provider calls needed).

Chạy: .\.venv\Scripts\python scripts/smoke_strategies.py
"""
import asyncio
import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from activities.strategy_activities import generate_carousel_strategy, generate_long_post_strategy


PERSONA_VIETNAM = {
    "language_name": "Vietnamese",
    "voice": "vi-VN-Wavenet-D",
    "skin_color": "light olive skin",
}

PERSONA_EUROPE = {
    "language_name": "German",
    "voice": "de-DE-Wavenet-B",
    "skin_color": "fair caucasian skin",
}


async def main():
    print("=" * 60)
    print("  SMOKE TEST: Carousel + Long Post Strategies")
    print("=" * 60)

    # ── Test 1: Carousel (Vietnamese) ───────────────────────────────
    print("\n[1/2] Carousel Strategy (TikTok / Vietnamese)...")
    carousel = await generate_carousel_strategy({
        "app_name": "TripC",
        "topic": "Top 5 hidden beaches in Da Nang",
        "persona_config": PERSONA_VIETNAM,
        "platform": "tiktok",
        "num_slides": 8,
    })

    slides = carousel.get("slides", [])
    assert len(slides) == 8, f"Expected 8 slides, got {len(slides)}"
    print(f"      ✅ {len(slides)} slides generated")
    print(f"      📌 Platform caption: {carousel.get('platform_caption', '')[:70]}...")
    print(f"      #️⃣  Hashtags: {', '.join(carousel.get('hashtags', [])[:5])}")

    for s in slides[:3]:
        print(f"         Slide {s['slide_num']}: {s['caption']}")

    # Save output
    with open("scripts/output_carousel_smoke.json", "w", encoding="utf-8") as f:
        json.dump(carousel, f, ensure_ascii=False, indent=2)
    print("      💾 Saved: scripts/output_carousel_smoke.json")

    # ── Test 2: Long Post (German) ───────────────────────────────────
    print("\n[2/2] Long Post Strategy (Facebook / German)...")
    post = await generate_long_post_strategy({
        "app_name": "TripC",
        "topic": "Why TripC is the best travel app for Europe",
        "persona_config": PERSONA_EUROPE,
        "platform": "facebook",
        "target_word_count": 400,
    })

    assert post.get("title"), "Missing title"
    assert post.get("hero_image_prompt"), "Missing hero image prompt"
    assert len(post.get("body", "")) > 100, "Body too short"
    print(f"      ✅ Post generated")
    print(f"      📌 Title: {post.get('title')}")
    print(f"      🖼  Hero image prompt: {post.get('hero_image_prompt', '')[:80]}...")
    print(f"      📝 Body length: {len(post.get('body', ''))} chars")
    print(f"      🔗 CTA: {post.get('cta', '')}")

    with open("scripts/output_longpost_smoke.json", "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)
    print("      💾 Saved: scripts/output_longpost_smoke.json")

    print("\n" + "=" * 60)
    print("  STRATEGIES SMOKE TEST PASSED ✅")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
