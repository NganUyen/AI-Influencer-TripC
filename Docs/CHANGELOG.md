# Changelog

All notable changes to the Video Generation Pipeline will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-03-29

### Fixed

#### Critical

- **`short_video_workflow.py:264` — Scene duration/image array mismatch**
  - **Root cause:** `image_urls` filtered out `None` values while `scene_durations` kept all N items
  - **Impact:** All scenes after a failed one had wrong duration, video corrupted silently
  - **Fix:** Added pre-assembly guard that raises `SceneAssetMismatchError` immediately when arrays don't match
  - **Code:** Lines 265-304 now detect failed scenes and build aligned arrays

- **`short_video_workflow.py` — No user notification on workflow failure**
  - **Root cause:** Workflow swallowed exceptions, returned `{status: "failed"}` silently
  - **Impact:** Users waited indefinitely with no feedback on what went wrong
  - **Fix:** Added `send_telegram_error_notification` activity in final except block (lines 395-420)

#### Medium

- **`media_activities.py:617` — Orphan asset record on upload failure**
  - **Root cause:** `is_video=True` was set before upload URL was confirmed
  - **Fix:** Flag now set only after upload returns valid URL (lines 607-616)

- **`video_activities.py:97` — Asset type detection failed on presigned URLs**
  - **Root cause:** `url.endswith(".webm")` fails on URLs with `?X-Amz-Signature=...` query params
  - **Fix:** Now uses `urlparse(url).path` before extension check via `_is_video_url()` helper (lines 25-40)

- **`script_service.py:195` — Invalid `top_half_source_type` silently passed through**
  - **Root cause:** No validation against `_TOP_HALF_SOURCE_TYPES` allowed set
  - **Fix:** Invalid values now logged as warning and defaulted to `ai_visual_fallback` (lines 204-214)

### Added

- **`services/errors.py`:** New `SceneAssetMismatchError` exception type for detecting array length mismatches
- **`activities/approval_activities.py`:** New `send_telegram_error_notification` activity for user failure alerts
- **`tests/test_pipeline_robustness.py`:** 7 new pytest cases covering all fixed paths:
  - `test_duration_mismatch_raises_with_failed_scenes`
  - `test_browser_capture_none_source_ref_logs_warning`
  - `test_browser_capture_failure_fallbacks_to_ai`
  - `test_is_video_url_with_presigned_s3_webm`
  - `test_is_video_url_with_presigned_s3_mp4`
  - `test_orphan_asset_not_created_on_upload_failure`
  - `test_workflow_sends_telegram_on_failure`
  - `test_invalid_source_type_defaults_to_ai_visual_fallback`

### Observability

Seven checkpoint logs added for pipeline tracing:

| Checkpoint | Location | Purpose |
|------------|----------|---------|
| CP1 | `script_service.py:243` | SceneContract field dump after build |
| CP2 | `media_activities.py:641` | Warning when `public_page_capture` has no `source_ref` |
| CP3 | `media_activities.py:617,660` | Full asset trace per scene after resolution |
| CP5 | `video_activities.py:128` | URL type detection result per scene |
| CP6 | `video_activities.py:178` | Per-scene assembly details before vstack |
| CP7 | `video_activities.py:345` | Slideshow fallback indicator |

---

## [1.0.0] - 2026-03-28

### Added
- Initial video generation pipeline with Temporal workflow
- Top-half browser capture support (`public_page_capture`)
- AI image fallback (`ai_visual_fallback`)
- HeyGen talking head integration
- Split-screen video assembly (vstack)
- Slideshow fallback when no talking head available
