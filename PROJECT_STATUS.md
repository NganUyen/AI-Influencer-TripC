# TripC AI Video Pipeline — Project Status

## 📁 Cấu trúc thư mục

```
python_services/
├── services/           # Lớp giao tiếp API cho từng provider
│   ├── ai_service.py        # GPT-4 / Gemini 2.0 Flash
│   ├── script_service.py    # Sinh ScriptContract (validated JSON)
│   ├── google_tts_service.py# Google TTS Wavenet
│   ├── fal_service.py       # fal.ai image generation
│   ├── heygen_service.py    # HeyGen talking head
│   ├── storage_service.py   # Cloudflare R2 upload
│   ├── region_service.py    # IP Detection + VPN Override
│   ├── browser_automation.py# Web scraper (Playwright)
│   ├── telegram_service.py  # Telegram bot (approval)
│   ├── postiz_service.py    # Social media scheduling
│   ├── contracts.py         # 6 pipeline contracts (Pydantic)
│   └── errors.py            # Error types retryable/non-retryable
│
├── activities/         # Temporal activities (business logic)
│   ├── strategy_activities.py   # Weekly, Carousel, Long Post
│   ├── media_activities.py      # Image gen, TTS, HeyGen, Web Tutorial
│   ├── video_activities.py      # ffmpeg split-screen assembly
│   ├── approval_activities.py   # Telegram approval + preview/publish
│   └── distribution_activities.py # Social media posting
│
├── scripts/            # Smoke tests + setup scripts
│   ├── smoke_script.py       # ✅ Validated
│   ├── smoke_strategies.py   # ✅ Validated
│   ├── smoke_tts.py          # Cần enable Google TTS API
│   ├── smoke_heygen.py       # Cần HEYGEN_TEST_AUDIO_URL
│   ├── smoke_storage.py      # Cần R2 credentials
│   ├── smoke_assembly.py     # Cần all media URLs
│   ├── setup_persona.py      # One-time persona bootstrap
│   └── check_persona.py      # Kiểm tra persona ready
│
├── config/settings.py  # Cấu hình (.env loading)
├── workflows/          # Temporal workflow definitions
└── api/                # FastAPI routes
```

---

## 🚀 Pipeline End-to-End

```
┌──────────────────────────────────────────────────────────────┐
│                    USER INPUT                                │
│  persona_id + topic → Telegram /video command                │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 1: SCRIPT GENERATION                                  │
│                                                              │
│  ScriptService (Gemini 2.0 Flash)                           │
│    → ScriptContract { script, duration, scenes[] }           │
│    → Gửi Telegram preview cho operator                       │
│    → Chờ approval (30 phút timeout)                          │
│                                                              │
│  [Approval] ──→ APPROVED: tiếp tục                           │
│              └→ REJECTED: workflow dừng                       │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 2: MEDIA GENERATION (song song)                       │
│                                                              │
│  ┌── Google TTS ──────→ AudioContract {url, voice}           │
│  │   (vi-VN-Wavenet-D)                                      │
│  │                                                           │
│  ├── fal.ai × 5-8 ──→ ImageContract[] {url, model, prompt}  │
│  │   (nano-banana-2 / flux)                                  │
│  │                                                           │
│  └── HeyGen ─────────→ TalkingHeadContract {url, avatar_id} │
│      (avatar + audio → lip-sync → polling)                   │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 3: VIDEO ASSEMBLY (ffmpeg local)                      │
│                                                              │
│  1. Download tất cả assets (parallel)                        │
│  2. Build slideshow (Ken Burns zoom + caption overlay)       │
│  3. Split screen: Top(1080×960) + Bottom(1080×960)           │
│  4. Mux audio + progress bar                                 │
│  5. Upload → Cloudflare R2                                   │
│                                                              │
│  → FinalVideoContract {video_url, storage_key}               │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 4: PREVIEW & PUBLISH (human-in-the-loop)              │
│                                                              │
│  1. Gửi video URL preview qua Telegram                       │
│  2. Operator chọn: Publish TikTok / Shorts / Schedule / Drop │
│  3. Postiz API trigger publish                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎭 4 Luồng Nội dung (Omni-channel)

### 1. Video Split Screen (TikTok / Shorts / Reels)
```
Input: persona_id + topic
  ↓
ScriptService → ScriptContract (5-8 scenes)
  ↓
┌─────────┬────────────┬──────────┐
│ TTS     │ fal.ai ×5  │ HeyGen   │  ← song song
│ audio   │ scene imgs │ talk vid │
└────┬────┴─────┬──────┴────┬─────┘
     └──────────┼───────────┘
                ▼
        ffmpeg assembly
     ┌─────────────────┐
     │   Top: Slides   │  1080×960
     ├─────────────────┤
     │ Bottom: TalkHead│  1080×960
     └─────────────────┘
           1080×1920 (9:16)
```

### 2. Carousel (TikTok Photo / FB / IG)
```
Input: app_name + topic + persona_config
  ↓
generate_carousel_strategy (Gemini)
  ↓
Output JSON:
  - 8 slides [{image_prompt, caption, cta_overlay}]
  - platform_caption
  - hashtags
  ↓
fal.ai × 8 → 8 ảnh đồng bộ style
  ↓
Post lên platform với captions
```

### 3. Single Image + Long Post (FB / Blog / LinkedIn)
```
Input: app_name + topic + persona_config
  ↓
generate_long_post_strategy (Gemini)
  ↓
Output JSON:
  - hero_image_prompt
  - title (SEO)
  - body (~500 từ, có subheadings)
  - meta_description
  - hashtags + CTA
  ↓
fal.ai × 1 → hero image
  ↓
Publish bài viết kèm ảnh
```

### 4. Web Tutorial (AI đọc Web → Sinh Video)
```
Input: url + country_code (VPN override)
  ↓
BrowserAutomationService
  → get_page_content(url)
  → take_screenshots()
  ↓
RegionService
  → IP detect hoặc VPN override
  → Gán persona (skin, voice, language)
  ↓
AI phân tích UI → 8 bước hướng dẫn
  ↓
Pipeline Video Split Screen (luồng 1)
```

---

## 🌍 Persona System (5 Châu Lục)

| Châu lục | Persona | Skin | Voice | Language |
|---|---|---|---|---|
| Asia | Minh | Warm olive | vi-VN-Wavenet-D | Vietnamese |
| Europe | Lucas | Fair/Caucasian | en-GB-Wavenet-B | English UK |
| Americas | Carlos | Hispanic brown | en-US-Wavenet-D | English US |
| Africa | Amara | Deep dark brown | en-US-Wavenet-D | English |
| Oceania | Liam | Sun-kissed tan | en-AU-Wavenet-B | English AU |

**IP Detection:** RegionService gọi API địa lý → mapping country → continent → persona.
**VPN Override:** Truyền `country_code="DE"` → ép dùng persona Europe (Lucas).

---

## 🔒 Pipeline Contracts (Pydantic)

File: `services/contracts.py`

| Contract | Trả về từ | Fields chính |
|---|---|---|
| `ScriptContract` | ScriptService | script, duration_estimate, scenes[] |
| `SceneContract` | ScriptService | id, timestamp_start/end, caption, prompt |
| `ImageContract` | FalAIService | url, width, height, model, prompt |
| `AudioContract` | GoogleTTSService | url, voice, duration |
| `TalkingHeadContract` | HeyGenService | url, avatar_id, heygen_video_id |
| `FinalVideoContract` | video_activities | video_url, storage_key, resolution |

---

## ⚠️ Error Handling & Retry

File: `services/errors.py`

**Nguyên tắc:** Không rerun toàn bộ pipeline khi 1 provider fail. Mỗi phase persist artifacts.

| Error Type | Retryable? | Khi nào |
|---|---|---|
| `FalAIRetryableError` | ✅ | Network timeout, 5xx |
| `FalAIAuthError` | ❌ | Invalid API key |
| `TTSAuthError` | ❌ | Invalid TTS key |
| `HeyGenTimeoutError` | ✅ | Polling vượt timeout |
| `HeyGenAuthError` | ❌ | Invalid HeyGen key |
| `AssemblyMissingAssetError` | ❌ | Thiếu file input |
| `ScriptContractError` | ❌ | AI output sai schema |
| `PersonaNotReadyError` | ❌ | Persona chưa setup |

**Kịch bản HeyGen fail muộn:** Giữ script + images + audio → chỉ retry HeyGen + assembly.

---

## ✅ Trạng thái triển khai

| Component | Status |
|---|---|
| fal.ai image | ✅ Integrated + Validated |
| Google TTS | ✅ Integrated (cần enable API) |
| HeyGen | ✅ Integrated |
| ffmpeg assembly | ✅ Integrated |
| R2 Storage | ✅ Integrated |
| Script Generation | ✅ Validated (Gemini) |
| Carousel Strategy | ✅ Validated (8 slides) |
| Long Post Strategy | ✅ Validated (SEO) |
| Telegram Approval | ✅ Integrated |
| Preview/Publish | ✅ Integrated |
| IP Detection + VPN | ✅ Validated |
| Persona 5 Châu Lục | ✅ Validated |
| Web Tutorial | ✅ Integrated |
| Error Types | ✅ Integrated |
| Pipeline Contracts | ✅ Integrated |
| Persona Setup Script | ✅ Integrated |

---

## 📋 Setup nhanh

```powershell
# 1. Cài dependencies
pip install -r requirements.txt

# 2. Cài ffmpeg
winget install Gyan.FFmpeg

# 3. Enable Google TTS API
# → https://console.cloud.google.com/apis/library/texttospeech.googleapis.com

# 4. Smoke tests (theo thứ tự)
.\.venv\Scripts\python scripts/smoke_script.py      # AI script gen
.\.venv\Scripts\python scripts/smoke_strategies.py   # Carousel + SEO
.\.venv\Scripts\python scripts/smoke_tts.py          # Google TTS
.\.venv\Scripts\python scripts/smoke_heygen.py       # HeyGen avatar
.\.venv\Scripts\python scripts/smoke_storage.py      # R2 upload
.\.venv\Scripts\python scripts/smoke_assembly.py     # ffmpeg full

# 5. Persona setup (1 lần)
.\.venv\Scripts\python scripts/setup_persona.py --persona_id=persona_asia_01
.\.venv\Scripts\python scripts/check_persona.py --persona_id=persona_asia_01
```
