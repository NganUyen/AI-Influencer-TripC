"""
Content Scenes Service
Sinh danh sách scenes: mỗi scene = ảnh fal.ai + caption nội dung phối hợp với nhau.
Đây là "não" của Split Screen top half.
"""

import logging
from typing import List, Dict, Any, Optional
from services.ai_service import AIService
from services.region_service import RegionService

logger = logging.getLogger(__name__)


# ─── Cấu trúc một scene ────────────────────────────────────────────────────
# {
#   "scene_idx": 1,
#   "image_prompt": "...",   → gửi tới fal.ai
#   "caption": "...",        → text overlay trên slide (ngắn gọn)
#   "duration": 4,           → giây
#   "platform": "tiktok",
# }


# ─── Template cảnh mặc định cho TripC Đà Nẵng ─────────────────────────────
DA_NANG_SCENE_TEMPLATES = [
    {
        "scene_idx": 1,
        "role": "hook",
        "image_prompt": (
            "Cinematic aerial view of Da Nang beach at golden hour, "
            "crystal blue water, white sand, dramatic sky, "
            "travel photography style, vertical 9:16, no people, "
            "ultra realistic, professional travel magazine quality"
        ),
        "caption": "🌊 Đà Nẵng đang chờ bạn khám phá...",
        "duration": 3,
    },
    {
        "scene_idx": 2,
        "role": "food",
        "image_prompt": (
            "Authentic Vietnamese street food close-up, Mi Quang noodles "
            "in a rustic bowl, fresh herbs, peanuts, colorful garnish, "
            "Da Nang local restaurant, warm ambient light, "
            "food photography style, vertical 9:16, appetizing"
        ),
        "caption": "🍜 Mì Quảng Bà Ba — vị chuẩn local",
        "duration": 4,
    },
    {
        "scene_idx": 3,
        "role": "app_demo",
        "image_prompt": (
            "Clean minimal travel app UI mockup on smartphone screen, "
            "Da Nang map with restaurant pins, modern blue design, "
            "hand holding phone with blurred beach background, "
            "9:16 vertical, product photography, TripC branded"
        ),
        "caption": "📍 Tìm quán ngon qua TripC — free download",
        "duration": 4,
    },
    {
        "scene_idx": 4,
        "role": "lifestyle",
        "image_prompt": (
            "Stylish young Vietnamese woman exploring Da Nang market, "
            "golden hour light, authentic local atmosphere, "
            "phone showing restaurant discovery app, "
            "vertical 9:16, lifestyle travel photography"
        ),
        "caption": "✨ Khám phá như dân local thật sự",
        "duration": 4,
    },
    {
        "scene_idx": 5,
        "role": "cta",
        "image_prompt": (
            "Dragon Bridge Da Nang at blue hour twilight, "
            "city lights reflection on Han River, "
            "long exposure photography, cinematic, "
            "travel destination quality, 9:16 vertical"
        ),
        "caption": "📲 Tải TripC — link bio nhé!",
        "duration": 3,
    },
]

# ─── Template hướng dẫn App (8 scenes) cho Global 🌏 ────────────────────────
GLOBAL_APP_TUTORIAL_SCENES = [
    {"scene_idx": 1, "role": "hook", "duration": 3, "caption": "🚀 Khám phá sức mạnh của TripC Web App"},
    {"scene_idx": 2, "role": "login", "duration": 3, "caption": "🔐 Đăng nhập chỉ trong 1 nốt nhạc"},
    {"scene_idx": 3, "role": "dashboard", "duration": 4, "caption": "📊 Giao diện quản lý trực quan, hiện đại"},
    {"scene_idx": 4, "role": "feature_1", "duration": 5, "caption": "🔍 Tìm kiếm thông minh với AI Filter"},
    {"scene_idx": 5, "role": "feature_2", "duration": 5, "caption": "⚙️ Tùy chỉnh trải nghiệm theo ý muốn"},
    {"scene_idx": 6, "role": "collaboration", "duration": 4, "caption": "👥 Làm việc nhóm và chia sẻ dễ dàng"},
    {"scene_idx": 7, "role": "mobile_sync", "duration": 4, "caption": "📱 Đồng bộ hóa dữ liệu trên mọi thiết bị"},
    {"scene_idx": 8, "role": "cta", "duration": 3, "caption": "✨ Trải nghiệm ngay tại tripc.ai"},
]

# ─── Hệ thống Persona 5 Châu Lục ───────────────────────────────────────────
CONTINENT_PERSONAS = {
    "asia": {
        "avatar_id": "minh_asia_01",
        "voice": "vi-VN-Wavenet-D",
        "skin_color": "warm light tan",
        "language_name": "Vietnamese",
        "image_prompt": "Portrait of a stylish young Vietnamese man, warm light tan skin, tech-savvy, friendly, modern office background, 9:16"
    },
    "europe": {
        "avatar_id": "lucas_europe_01",
        "voice": "en-GB-Wavenet-B",
        "skin_color": "fair/caucasian",
        "language_name": "English (UK)",
        "image_prompt": "Portrait of a professional European man in London, fair skin, smart casual, clean minimal background, 9:16"
    },
    "america": {
        "avatar_id": "sarah_america_01",
        "voice": "en-US-Studio-O",
        "skin_color": "hispanic/light brown",
        "language_name": "English (US)",
        "image_prompt": "Portrait of a vibrant Hispanic woman in New York, light brown skin, confident, bright urban setting, 9:16"
    },
    "africa": {
        "avatar_id": "kofi_africa_01",
        "voice": "en-US-Standard-C",
        "skin_color": "deep dark brown",
        "language_name": "English",
        "image_prompt": "Portrait of a modern African entrepreneur, deep dark brown skin, Lagos background, colorful tech workspace, 9:16"
    },
    "australia": {
        "avatar_id": "emma_australia_01",
        "voice": "en-AU-Wavenet-C",
        "skin_color": "sun-kissed tan",
        "language_name": "English (AU)",
        "image_prompt": "Portrait of a friendly Australian woman, sun-kissed tan skin, outdoor coastal background, bright natural light, 9:16"
    }
}



async def generate_content_scenes(
    topic: str,
    location: str = "Đà Nẵng",
    platform: str = "tiktok",
    use_ai_captions: bool = False,
) -> List[Dict[str, Any]]:
    """
    Sinh danh sách scenes với ảnh + caption phối hợp theo chủ đề.

    Args:
        topic: Chủ đề bài đăng (VD: "Mì Quảng ven biển")
        location: Địa điểm (default: Đà Nẵng)
        platform: "tiktok" | "shorts" | "instagram"
        use_ai_captions: True = gọi GPT-4 sinh caption   (cần API key)
                         False = dùng template mặc định

    Returns:
        List[Dict] — scenes đã hoàn chỉnh (image_prompt + caption + duration)
    """
    scenes = []

    if use_ai_captions:
        # Gọi AI sinh captions tùy chỉnh theo topic
        async with AIService() as ai:
            for template in DA_NANG_SCENE_TEMPLATES:
                caption = await _ai_caption(ai, template["role"], topic, location)
                scenes.append({**template, "caption": caption, "platform": platform})
    else:
        # Dùng template sẵn, thêm platform
        for template in DA_NANG_SCENE_TEMPLATES:
            scenes.append({**template, "platform": platform})

    logger.info(f"Sinh {len(scenes)} scenes | topic: {topic} | AI captions: {use_ai_captions}")
    return scenes


async def _ai_caption(ai: AIService, role: str, topic: str, location: str) -> str:
    """Sinh caption ngắn (≤8 từ) phù hợp với role và topic."""
    role_guide = {
        "hook": "một câu hook bất ngờ, gây tò mò, ≤8 từ",
        "food": "mô tả món ăn hấp dẫn, có cảm xúc, ≤8 từ",
        "app_demo": "lợi ích app TripC, rõ ràng, ≤8 từ",
        "lifestyle": "lifestyle tích cực, gần gũi, ≤8 từ",
        "cta": "kêu gọi hành động, có emoji, ≤8 từ",
    }
    prompt = (
        f"Viết {role_guide.get(role, '≤8 từ tiếng Việt')} "
        f"cho bài về '{topic}' ở {location}. "
        f"Chỉ trả về caption, không có gì thêm."
    )
    try:
        caption = await ai.generate_text(prompt=prompt, max_tokens=30, temperature=0.8)
        return caption.strip()
    except Exception:
        return "Mời bạn trải nghiệm ngay!"


async def generate_app_tutorial_scenes(
    app_name: str,
    continent: Optional[str] = None,
    use_ai_captions: bool = True
) -> List[Dict[str, Any]]:
    """
    Sinh 8 scenes hướng dẫn sử dụng App. 
    Nếu continent=None, sùng RegionService để tự động phát hiện qua IP.
    """
    if not continent:
        region_svc = RegionService()
        region_info = await region_svc.get_region_info()
        continent = region_info.get("continent", "asia")
        print(f"DEBUG: Detected continent '{continent}' from IP ({region_info.get('country')})")

    persona = CONTINENT_PERSONAS.get(continent, CONTINENT_PERSONAS["asia"])
    scenes = []
    
    if use_ai_captions:
        async with AIService() as ai:
            for template in GLOBAL_APP_TUTORIAL_SCENES:
                scene = template.copy()
                scene["image_prompt"] = (
                    f"High quality screenshot of {app_name} web application UI, "
                    f"showing {scene['role']} feature. In foreground, hand of a person with "
                    f"{persona['skin_color']} skin is interacting with the screen. "
                    f"clean modern design, software demo style, professional, 9:16 vertical"
                )
                prompt = (
                    f"Viết 1 câu hướng dẫn ngắn (<8 từ) cho tính năng '{scene['role']}' "
                    f"của app '{app_name}'. Sử dụng ngôn ngữ '{persona['language_name']}'. "
                    f"Giữ giọng điệu chuyên nghiệp."
                )
                try:
                    scene["caption"] = await ai.generate_text(prompt=prompt)
                except: pass
                scene["persona_config"] = persona
                scenes.append(scene)
    else:
        for template in GLOBAL_APP_TUTORIAL_SCENES:
            scene = template.copy()
            scene["image_prompt"] = (
                f"High quality screenshot of {app_name} web application UI, "
                f"showing {scene['role']} feature. In foreground, hand of a person with "
                f"{persona['skin_color']} skin is interacting with the screen. "
                f"clean modern design, software demo style, professional, 9:16 vertical"
            )
            scene["persona_config"] = persona
            scenes.append(scene)
        
    return scenes
