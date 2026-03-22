# OpenClaw Telegram Skills

## Purpose

This document defines the menu-driven OpenClaw skill surface for Telegram.

It is intentionally written as a `skill definition first` document.

That means:

- define the Telegram/OpenClaw skill tree now
- keep Telegram router integration for later
- keep API/wiring gaps explicit, while using the canonical backend contracts
  that already exist today

This is different from the lower-level internal project skills documented in:

- [`TRIPC_SKILLS_REFERENCE.md`](./TRIPC_SKILLS_REFERENCE.md)

## Core Principle

There are three layers:

### 1. Telegram entrypoint

Public command:

- `/media`

### 2. OpenClaw Telegram skills

These are the user-facing skills the Telegram/OpenClaw menu should expose.

### 3. Internal project skills

These are the lower-level project capabilities that the OpenClaw Telegram skills dispatch into.

## Target Menu Tree

```text
/media
├── Create Image
│   ├── Marketing Poster    -> image-poster
│   ├── Scene/Slideshow     -> image-scene
│   └── Avatar              -> image-avatar
├── Create Video
│   ├── AI Influencer       -> video-ai
│   └── Tutorial            -> video-tutorial
├── Carousel                -> carousel
├── Long Post               -> long-post
└── Manage
    ├── Personas            -> persona-manager
    │   ├── Create Persona  -> persona-creator
    │   └── Inspect Personas -> persona-inspector
    ├── Quota               -> quota-inspector
    ├── Weekly Plan         -> weekly-planner
    └── Publish Queue       -> publish-manager
```

## Important Note

This file defines the OpenClaw Telegram skill tree before Telegram integration.

At the time of writing:

- the skill definitions are now documented and registered
- the Telegram menu router is not yet implemented
- some target APIs are already exposed and should be treated as the canonical
  skill-facing backend surface
- some target APIs remain planned rather than already exposed

## Input Philosophy

Use `menu-driven` collection as the default operator experience, but do not make
the skill layer overly rigid.

Recommended rule:

- structured fields are the primary control surface
- free text is still allowed as an optional refinement layer
- raw free text should not replace required fields such as `topic`, `platform`,
  `persona_id`, `tone`, or `language`

In practice that means:

- `video-ai` can still accept `hook_idea`, `freeform_brief`, or `creative_notes`
- `carousel` can still accept positioning notes or extra slide direction
- `image-poster` can still accept extra visual brief text
- `persona-creator` can still accept identity or appearance notes

This keeps the menu tree in scope while still letting advanced users shape the
output more precisely.

## Top-Level Menu

When the operator types:

```text
/media
```

The bot should show:

- `🖼️ Create Image`
- `🎬 Create Video`
- `🎠 Carousel`
- `📝 Long Post`
- `⚙️ Manage`

## Skill Catalog

| OpenClaw skill | Menu path | Internal skills | API target | Output | Status |
|---|---|---|---|---|---|
| `image-poster` | `/media -> Create Image -> Marketing Poster` | `image`, `r2-storage` | `POST /api/media/generate/image` | poster image URL | `defined_with_backing_gap` |
| `image-scene` | `/media -> Create Image -> Scene/Slideshow` | `image`, `r2-storage` | `POST /api/media/generate/image` | scene image URL | `implemented_backing` |
| `image-avatar` | `/media -> Create Image -> Avatar` | `image`, `r2-storage`, `persona-setup` | `POST /api/media/generate/image` | avatar preview URL | `partial` |
| `video-ai` | `/media -> Create Video -> AI Influencer` | `persona-picker`, `script-gen`, `google-tts`, `image`, `heygen-video`, `ffmpeg-assembly`, `r2-storage`, `telegram-approval`, `postiz-publish` | `POST /api/workflows/start-video` | final video URL | `implemented_backing` |
| `video-tutorial` | `/media -> Create Video -> Tutorial` | `persona-picker`, `scene-builder`, `google-tts`, `image`, `heygen-video`, `ffmpeg-assembly`, `r2-storage`, `telegram-approval`, `postiz-publish` | `POST /api/workflows/start-tutorial` | final tutorial video URL | `deferred` |
| `carousel` | `/media -> Carousel` | `persona-picker`, `carousel-plan`, `image`, `r2-storage`, `telegram-approval`, `postiz-publish` | `POST /api/media/carousel` | slides JSON + rendered image URLs | `implemented_backing` |
| `long-post` | `/media -> Long Post` | `persona-picker`, `long-post-plan`, `image`, `r2-storage`, `telegram-approval`, `postiz-publish` | `POST /api/media/long-post` | content JSON + hero image URL | `deferred` |
| `persona-manager` | `/media -> Manage -> Personas` | none directly, routes to persona subskills | none | persona management submenu | `defined_only` |
| `persona-creator` | `/media -> Manage -> Personas -> Create Persona` | `image`, `heygen-video`, `r2-storage`, `persona-setup` | `POST /api/personas`, `PATCH /api/personas/{persona_id}`, `GET /api/personas/{persona_id}/readiness` | ready persona record | `partial` |
| `persona-inspector` | `/media -> Manage -> Personas -> Inspect Personas` | `persona-picker`, `persona-setup`, `image`, `heygen-video`, `r2-storage` | `GET /api/personas`, `GET /api/personas/{persona_id}`, `GET /api/personas/{persona_id}/readiness`, `PATCH /api/personas/{persona_id}` | persona cards and actions | `partial` |
| `quota-inspector` | `/media -> Manage -> Quota` | `quota-monitor` | `GET /api/quota/*` | quota summary/detail in Telegram | `implemented_backing` |
| `weekly-planner` | `/media -> Manage -> Weekly Plan` | `weekly-plan`, `telegram-approval`, `postiz-publish` | `POST /api/workflows/start-weekly` | weekly workflow confirmation | `implemented_backing` |
| `publish-manager` | `/media -> Manage -> Publish Queue` | `postiz-publish` | future publish queue endpoints | publish queue actions | `partial` |

## Structured Input With Optional Freeform Brief

Creative leaf skills should follow this input pattern:

1. collect the required structured fields first
2. optionally let the operator add extra free text
3. build the final provider prompt from both layers

Suggested freeform fields:

- `freeform_brief`
- `creative_notes`
- `hook_idea`
- `identity_notes`

This means the future Telegram/OpenClaw layer should support both:

- quick menu-only usage
- menu plus free text refinement

Examples:

- `image-poster`
  - required: topic/brief
  - optional: style, tone, `freeform_brief`, `creative_notes`
- `video-ai`
  - required: persona, topic, tone
  - optional: platform, duration target, `hook_idea`, `freeform_brief`
- `long-post`
  - required: topic, platform
  - optional: persona, tone, `freeform_brief`

## Reusable Helper Skill

### `persona-picker`

This is a reusable helper skill, not a top-level menu leaf.

It should be reused by:

- `video-ai`
- `video-tutorial`
- `carousel`
- `long-post`
- `persona-manager`

Purpose:

- load personas from the registry
- filter by readiness when needed
- allow inline selection
- allow `Create New Persona` where appropriate

Current reality:

- this helper is defined at the skill layer
- the backend persona API exists and should be the canonical source
- a shared Telegram persona picker UI/session layer does not yet exist

## Skill Details

### `image-poster`

**Function**

Generate a marketing poster image with a poster-specific prompt/template policy.

**Why separate this from generic image generation**

Poster generation usually needs:

- ad-style composition
- text-aware prompting
- CTA framing
- brand-oriented defaults

**Current repo reality**

- can reuse the existing image API
- needs bot-side prompt policy and poster-specific menu logic
- should allow optional free text briefing beyond menu selections

### `image-scene`

**Function**

Generate images intended for scene or slideshow use.

**Current repo reality**

- backed by the current image provider lane
- one of the easiest media skills to integrate early
- should still allow extra visual notes in plain text

### `image-avatar`

**Function**

Generate avatar preview images for personas.

**Current repo reality**

- the image generation path exists
- persona registry and Telegram persona flow are still incomplete
- appearance can stay partly freeform even inside a menu-driven flow

### `video-ai`

**Function**

Run the full AI influencer video lane:

1. pick persona
2. collect topic
3. collect tone
4. optionally collect platform
5. generate script
6. generate audio
7. generate scene images
8. generate talking-head
9. assemble final video
10. send preview and later publish

**Current repo reality**

- most internal project capabilities exist
- the dedicated Telegram/OpenClaw wrapper still needs to be built
- the canonical `POST /api/workflows/start-video` endpoint exists
- it should be the only video-start contract the skill depends on
- a user should still be able to add hook ideas or extra brief text before script generation

### `video-tutorial`

**Function**

Run the tutorial video lane:

1. pick persona if needed
2. collect topic or tutorial subject
3. build scenes
4. generate audio
5. generate images
6. generate talking-head
7. assemble final video

**Current repo reality**

- this overlaps heavily with `video-ai`
- still depends on a future workflow entrypoint and Telegram wrapper
- defer this lane for now and reuse/focus on the existing `start-video` lane during current OpenClaw integration
- it should still accept extra tutorial angle or notes in plain text

### `carousel`

**Function**

Generate carousel planning JSON plus matching slide images.

**Current repo reality**

- planning activity already exists
- `POST /api/media/carousel` exists as the canonical carousel backend entrypoint
- backend now generates slide plans, creates slide images, overlays text, and uploads final slide assets
- extra freeform direction should remain optional, not required

### `long-post`

**Function**

Generate long-form content plus a hero image.

**Current repo reality**

- planning activity already exists
- a dedicated `/api/media/long-post` endpoint is still a target endpoint
- defer this lane for now until there is a completed backend endpoint and a real integration need
- extra freeform angle or messaging notes should remain optional

### `persona-manager`

**Function**

Act as a persona management submenu:

- `Create Persona`
- `Inspect Personas`

**Current repo reality**

- this is now a routing/menu skill, not the persona creation flow itself

### `persona-creator`

**Function**

Create a new persona step by step:

1. collect persona ID
2. choose language
3. choose voice
4. collect appearance prompt or photo
5. preview avatar
6. register HeyGen avatar
7. save DB record

**Current repo reality**

- the underlying setup/check logic exists only as scripts today
- persona CRUD/readiness APIs exist, but full Telegram setup orchestration is still incomplete
- language/voice stay structured, but appearance and identity notes can remain partly freeform

**Session shape**

```python
{
  "step_key": "collect_persona_id",
  "collected": {
    "persona_id": None,
    "language": None,
    "voice": None,
    "appearance_prompt_or_photo": None,
  },
  "artifacts": {
    "preview_image_url": None,
    "avatar_image_url": None,
    "heygen_avatar_id": None,
  },
}
```

### `persona-inspector`

**Function**

List, inspect, and rebuild existing personas.

**Current repo reality**

- backend persona registry/readiness APIs exist
- Telegram-facing list/inspect/rebuild UX still needs to be built

### `quota-inspector`

**Function**

Inspect provider readiness and usage before expensive actions.

**Current repo reality**

- this has one of the strongest management backings in the repo today

### `weekly-planner`

**Function**

Trigger the weekly planning lane from Telegram/OpenClaw.

**Current repo reality**

- the weekly workflow API already exists
- this is a good candidate for early Telegram integration

### `publish-manager`

**Function**

Inspect or manage pending publish actions from Telegram.

**Current repo reality**

- publish capability exists
- a Telegram-facing publish queue endpoint and UI still need to be built

## Recommended Implementation Order

From simplest to most complex:

1. `image-scene`
2. `image-poster`
3. `quota-inspector`
4. `carousel`
5. `weekly-planner`
6. `image-avatar`
7. `persona-inspector`
8. `persona-creator`
9. `persona-manager`
10. `video-ai`

Deferred outside the current OpenClaw integration phase:

- `video-tutorial`
- `long-post`

## Session State Guidance

Each leaf skill should define its own `session_shape`.

This is important because the menu-driven Telegram router will need to know:

- what step the operator is currently on
- which parameters have already been collected
- which artifacts have already been generated
- which optional freeform notes were supplied and should be carried forward

Examples already included in the registry:

- `video-ai`
- `video-tutorial`
- `carousel`
- `long-post`
- `persona-creator`
- `quota-inspector`
- `weekly-planner`
- `publish-manager`

Recommended structure:

```python
{
  "step_key": "<current_step>",
  "collected": {
    # user inputs
  },
  "artifacts": {
    # generated outputs / ids / URLs
  },
}
```

Using this per-skill session schema makes the future Telegram router much easier
to implement consistently.

## Definition-First Note

This document and the registry are intentionally ahead of runtime integration.

That is acceptable and expected.

The goal right now is:

1. define the OpenClaw Telegram skill tree clearly
2. map each skill to internal project skills
3. identify the target API entrypoint
4. expose backend gaps before Telegram implementation begins

Current OpenClaw integration focus:

- `video-ai`
- `carousel`
- `weekly-planner`
- `persona-manager` and persona helper flows
- `quota-inspector`

The canonical backend contracts for current skills are:

- `POST /api/workflows/start-video`
- `POST /api/workflows/start-weekly`
- `GET /api/personas`
- `POST /api/personas`
- `GET /api/personas/{persona_id}`
- `PATCH /api/personas/{persona_id}`
- `GET /api/personas/{persona_id}/readiness`
- `GET /api/quota/*`

Still planned and not yet exposed:

- `POST /api/workflows/start-tutorial`
- `POST /api/media/long-post`

Deferred and not part of the current OpenClaw implementation scope:

- `video-tutorial`
- `long-post`

## Current Registry

The current registry is defined in:

- [`../Project/python_services/agents/openclaw_telegram_skill_configs.py`](../Project/python_services/agents/openclaw_telegram_skill_configs.py)

## Related Code

- [`../Project/python_services/agents/openclaw_telegram_skill_configs.py`](../Project/python_services/agents/openclaw_telegram_skill_configs.py)
- [`../Project/python_services/api/media.py`](../Project/python_services/api/media.py)
- [`../Project/python_services/api/workflows.py`](../Project/python_services/api/workflows.py)
- [`../Project/python_services/services/openclaw_service.py`](../Project/python_services/services/openclaw_service.py)
- [`../Project/python_services/services/telegram_service.py`](../Project/python_services/services/telegram_service.py)
- [`./TRIPC_SKILLS_REFERENCE.md`](./TRIPC_SKILLS_REFERENCE.md)
