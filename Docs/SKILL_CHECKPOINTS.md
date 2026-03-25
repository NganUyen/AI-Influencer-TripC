# SKILL_CHECKPOINTS

This checkpoint follows the current OpenClaw integration pass. The prompt count says `7 Phase 1 skills + 2 stub skills`, while the implementation surface now contains:

- 7 active modules implemented in `Project/python_services/skills/`
- 1 stub module
- 1 reference-only checkpoint for `image-poster` from the skill catalog, so Telegram wiring has a complete catalog handoff

Runtime note:

- real user entrypoint now goes through `POST /api/webhooks/telegram`
- `services/skill_dispatcher.py` and `services/telegram_renderer.py` are implemented
- the per-skill "Start: POST /skill/start ..." scenarios below should be read as logical dispatcher start points, not as a literal public API route

## image-scene

### Backend status
implemented

### API target
POST /api/media/generate/image

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
collect_prompt | free_text | "What scene image should be generated?" | -
choose_style | inline_keyboard | "Choose a style." | [Clean, Cinematic, Minimal, Custom]
confirm_or_regenerate | inline_keyboard | "Use this image?" | [Use, Regenerate, Cancel]
done | automatic | - | -

### Session shape
```python
{
  "step_key": "collect_prompt",
  "collected": {
    "topic_or_prompt": None,
    "style": None,
    "persona_id": None,
    "aspect_ratio": None,
    "scene_type": None,
    "freeform_brief": None,
    "creative_notes": None,
  },
  "artifacts": {
    "preview_image_url": None,
    "final_image_url": None,
    "storage_key": None,
  },
}
```

### Output shape
```python
{
  "preview_image_url": "https://...",
  "model": "fal-ai/nano-banana-2",
  "prompt": "assembled prompt",
}
```

### Telegram wiring checklist
[ ] step collect_prompt: ask free text question
[ ] step choose_style: show style keyboard
[ ] step generate_preview: show "Generating..." message
[ ] step confirm_or_regenerate: send image + action buttons
[ ] step done: send final asset

### Test scenario
1. Start: POST /skill/start `{"skill": "image-scene", "chat_id": "..."}`
2. Step 1: user enters prompt, then chooses style
3. Step 2: dispatcher calls the image endpoint
4. Expected output: preview image URL in `session.artifacts.preview_image_url`

## image-poster

### Backend status
backend_pending

### API target
POST /api/media/generate/image

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
collect_brief | free_text | "What feature should the poster highlight?" | -
choose_style | inline_keyboard | "Choose a poster style." | [Premium, Clean, Bold, Custom]
choose_tone | inline_keyboard | "Choose a tone." | [Confident, Friendly, Aspirational, Custom]
generate_preview | automatic | - | -
confirm_or_regenerate | inline_keyboard | "Use this poster?" | [Use, Regenerate, Cancel]
done | automatic | - | -

### Session shape
```python
{
  "step_key": "collect_brief",
  "collected": {
    "topic_or_brief": None,
    "style": None,
    "tone": None,
    "cta_text": None,
    "app_name": None,
    "aspect_ratio": None,
    "freeform_brief": None,
    "creative_notes": None,
  },
  "artifacts": {
    "preview_image_url": None,
    "final_image_url": None,
    "storage_key": None,
  },
}
```

### Output shape
```python
{
  "preview_image_url": "https://...",
  "note": "Poster-specific template policy still belongs in Telegram/router logic.",
}
```

### Telegram wiring checklist
[ ] step collect_brief: ask free text question
[ ] step choose_style: show poster style keyboard
[ ] step choose_tone: show tone keyboard
[ ] step generate_preview: show "Generating..." message
[ ] step confirm_or_regenerate: send poster preview + actions
[ ] step done: send final poster output

### Test scenario
1. Start: POST /skill/start `{"skill": "image-poster", "chat_id": "..."}`
2. Step 1: user enters a launch brief
3. Step 2: router assembles poster prompt policy
4. Expected output: poster preview request is ready

## quota-inspector

### Backend status
implemented

### API target
GET /api/quota/*

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
choose_provider_or_summary | inline_keyboard | "View summary or one provider?" | [Summary, fal_ai, google_tts, heygen, postiz]
fetch_quota | automatic | - | -
render_quota_view | automatic | - | -
done | automatic | - | -

### Session shape
```python
{
  "step_key": "choose_provider_or_summary",
  "collected": {"provider": None},
  "artifacts": {"quota_summary": None, "quota_detail": None},
}
```

### Output shape
```python
{
  "quota_summary": {...}
  # or
  "provider": "fal_ai",
  "quota_detail": {...},
}
```

### Telegram wiring checklist
[ ] step choose_provider_or_summary: show provider buttons
[ ] step fetch_quota: show loading state
[ ] step render_quota_view: format summary/detail
[ ] step done: send final quota message

### Test scenario
1. Start: POST /skill/start `{"skill": "quota-inspector", "chat_id": "..."}`
2. Step 1: user chooses `Summary`
3. Step 2: dispatcher calls the quota summary endpoint
4. Expected output: summary payload in `SkillResult.output`

## persona-inspector

### Backend status
implemented

### API target
GET /api/personas
GET /api/personas/{persona_id}
GET /api/personas/{persona_id}/readiness
PATCH /api/personas/{persona_id}

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
list_personas | automatic | - | -
select_persona | inline_keyboard | "Choose a persona to inspect." | [persona ids from API]
view_details_or_rebuild | inline_keyboard | "What do you want to do?" | [View, Rebuild, Cancel]
done | automatic | - | -

### Session shape
```python
{
  "step_key": "list_personas",
  "collected": {"persona_id": None},
  "artifacts": {"persona_summary": None, "available_personas": []},
}
```

### Output shape
```python
{
  "available_personas": [...],
  "persona": {...},
  "readiness": {...},
}
```

### Telegram wiring checklist
[ ] step list_personas: fetch persona list
[ ] step select_persona: show inline keyboard
[ ] step view_details_or_rebuild: show persona card + actions
[ ] step done: send persona detail and readiness report

### Test scenario
1. Start: POST /skill/start `{"skill": "persona-inspector", "chat_id": "..."}`
2. Step 1: dispatcher lists personas
3. Step 2: user selects a persona
4. Expected output: detail + readiness payload

## persona-creator

### Backend status
implemented

### API target
POST /api/personas
PATCH /api/personas/{persona_id}
GET /api/personas/{persona_id}/readiness

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
collect_persona_id | free_text | "Enter a persona ID." | -
choose_language | inline_keyboard | "Choose a language." | [vi, en, Custom]
choose_voice | inline_keyboard | "Choose a voice." | [male_friendly, female_warm, Custom]
collect_appearance | free_text | "Describe the avatar or upload a photo." | -
preview_avatar | automatic | - | -
register_heygen | automatic | - | -
save_db | automatic | - | -
done | automatic | - | -

### Session shape
```python
{
  "step_key": "collect_persona_id",
  "collected": {
    "persona_id": None,
    "language": None,
    "voice": None,
    "appearance_prompt_or_photo": None,
    "identity_notes": None,
    "creative_notes": None,
  },
  "artifacts": {
    "preview_image_url": None,
    "avatar_image_url": None,
    "heygen_avatar_id": None,
  },
}
```

### Output shape
```python
{
  "persona": {...},
  "readiness": {...},
  "backend_status": "partial",
  "note": "Avatar/HeyGen orchestration still belongs to the router layer.",
}
```

### Telegram wiring checklist
[ ] step collect_persona_id: ask for ID
[ ] step choose_language: show language keyboard
[ ] step choose_voice: show voice keyboard
[ ] step collect_appearance: ask for text/photo
[ ] step preview_avatar: show draft avatar state
[ ] step register_heygen: show progress state
[ ] step done: send persona + readiness result

### Test scenario
1. Start: POST /skill/start `{"skill": "persona-creator", "chat_id": "..."}`
2. Step 1: user enters ID, language, voice, appearance
3. Step 2: dispatcher creates the persona and checks readiness
4. Expected output: draft persona record and readiness report

## video-ai

### Backend status
implemented

### API target
POST /api/workflows/start-video

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
pick_persona | inline_keyboard | "Choose a ready persona." | [ready persona ids]
collect_topic | free_text | "What should the video be about?" | -
generate_script | automatic | - | -
approve_script | inline_keyboard | "Use this script direction?" | [Approve, Regenerate, Cancel]
generate_media | automatic | - | -
assemble_video | automatic | - | -
approve_video | inline_keyboard | "Use this video?" | [Approve, Retry, Cancel]
publish_or_finish | inline_keyboard | "What next?" | [Finish, Publish Later]
done | automatic | - | -

### Session shape
```python
{
  "step_key": "pick_persona",
  "collected": {
    "persona_id": None,
    "topic": None,
    "tone": "natural",
    "platform": "tiktok",
    "duration_target": None,
    "hook_idea": None,
    "freeform_brief": None,
    "creative_notes": None,
  },
  "artifacts": {
    "script_id": None,
    "script_preview": None,
    "audio_url": None,
    "scene_image_urls": [],
    "heygen_video_url": None,
    "final_video_url": None,
    "storage_key": None,
  },
}
```

### Output shape
```python
{
  "workflow_id": "video-...",
  "run_id": "...",
  "status": "started",
  "approval_required": True,
}
```

### Telegram wiring checklist
[ ] step pick_persona: show only ready personas
[ ] step collect_topic: ask free text question
[ ] step generate_script: show workflow progress
[ ] step approve_video: render preview/result + actions
[ ] step done: send workflow completion handoff

### Test scenario
1. Start: POST /skill/start `{"skill": "video-ai", "chat_id": "..."}`
2. Step 1: user picks persona and enters topic
3. Step 2: dispatcher starts `POST /api/workflows/start-video`
4. Expected output: `workflow_id` saved in `session.control.workflow_id`

## weekly-planner

### Backend status
implemented

### API target
POST /api/workflows/start-weekly

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
collect_brand_config | free_text | "Send brand config JSON or choose a preset." | -
start_workflow | automatic | - | -
await_approval | automatic | - | -
done | automatic | - | -

### Session shape
```python
{
  "step_key": "collect_brand_config",
  "collected": {
    "brand_config": None,
    "user_id": None,
    "freeform_brief": None,
  },
  "artifacts": {
    "workflow_id": None,
    "run_id": None,
  },
}
```

### Output shape
```python
{
  "workflow_id": "weekly-marketing-...",
  "run_id": "...",
  "status": "started",
  "approval_required": True,
}
```

### Telegram wiring checklist
[ ] step collect_brand_config: accept preset or JSON text
[ ] step start_workflow: send "Starting..." message
[ ] step await_approval: show workflow status / approval handoff
[ ] step done: send workflow confirmation

### Test scenario
1. Start: POST /skill/start `{"skill": "weekly-planner", "chat_id": "..."}`
2. Step 1: user sends `brand_config`
3. Step 2: dispatcher starts the weekly workflow
4. Expected output: workflow ID and run ID saved in `session.artifacts`

## carousel

### Backend status
implemented

### API target
POST /api/media/carousel

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
pick_persona | inline_keyboard | "Choose a persona or skip." | [persona ids, Skip]
collect_topic | free_text | "What should the carousel explain?" | -
choose_platform | inline_keyboard | "Choose a platform." | [instagram, linkedin, facebook]
choose_slide_count | inline_keyboard | "How many slides?" | [4, 6, 8, 10]
choose_tone | inline_keyboard | "Choose a tone." | [Educational, Bold, Clean, Custom]
generate_plan | automatic | - | -
generate_images | automatic | - | -
preview | inline_keyboard | "Use this carousel?" | [Use, Regenerate, Cancel]
done | automatic | - | -

### Session shape
```python
{
  "step_key": "pick_persona",
  "collected": {
    "persona_id": None,
    "topic": None,
    "platform": None,
    "tone": None,
    "num_slides": None,
    "freeform_brief": None,
    "creative_notes": None,
  },
  "artifacts": {
    "slides_json": None,
    "image_urls": [],
    "storage_keys": [],
  },
}
```

### Output shape
```python
{
  "type": "carousel",
  "topic": "...",
  "platform": "...",
  "slides": [
    {
      "slide_num": 1,
      "caption": "...",
      "cta_overlay": "...",
      "image_url": "https://...",
      "source_image_url": "https://...",
      "storage_key": "carousels/...",
      "metadata": {...},
    }
  ],
  "platform_caption": "...",
  "hashtags": ["#tripc"],
  "metadata": {
    "slide_count": 8,
    "storage_prefix": "carousels/..."
  },
  "manifest_url": "https://.../manifest.json",
}
```

### Telegram wiring checklist
[ ] step pick_persona: show ready personas or skip
[ ] step collect_topic: ask free text question
[ ] step choose_platform: show platform keyboard
[ ] step choose_slide_count: show slide-count keyboard
[ ] step generate_images: show progress message
[ ] step preview: send slide previews + actions
[ ] step done: send final carousel artifact and manifest link

### Test scenario
1. Start: POST /skill/start `{"skill": "carousel", "chat_id": "..."}`
2. Step 1: user fills the structured inputs
3. Step 2: dispatcher calls `POST /api/media/carousel`
4. Expected output: rendered slide image URLs plus `manifest_url`

## long-post

### Backend status
backend_pending

### API target
POST /api/media/long-post

### Steps
step_key | input_type | prompt_text | options
─────────────────────────────────────────────
pick_persona | inline_keyboard | "Choose a persona or skip." | [persona ids, Skip]
collect_topic | free_text | "What topic should the long post cover?" | -
choose_platform | inline_keyboard | "Choose a platform." | [linkedin, facebook, blog]
choose_tone | inline_keyboard | "Choose a tone." | [Professional, Educational, Bold, Custom]
generate_content | automatic | - | -
generate_hero_image | automatic | - | -
preview | inline_keyboard | "Use this post?" | [Use, Regenerate, Cancel]
done | automatic | - | -

### Session shape
```python
{
  "step_key": "pick_persona",
  "collected": {
    "persona_id": None,
    "topic": None,
    "platform": None,
    "tone": None,
    "freeform_brief": None,
    "creative_notes": None,
  },
  "artifacts": {
    "content_json": None,
    "hero_image_url": None,
    "storage_key": None,
  },
}
```

### Output shape
```python
{
  "error": "Backend endpoint not yet available: POST /api/media/long-post",
}
```

### Telegram wiring checklist
[ ] step pick_persona: show ready personas or skip
[ ] step collect_topic: ask free text question
[ ] step choose_platform: show platform keyboard
[ ] step choose_tone: show tone keyboard
[ ] step generate_content: show progress message
[ ] step preview: send content preview + actions

### Test scenario
1. Start: POST /skill/start `{"skill": "long-post", "chat_id": "..."}`
2. Step 1: user fills the structured inputs
3. Step 2: dispatcher calls the stub skill
4. Expected output: backend-pending error message
