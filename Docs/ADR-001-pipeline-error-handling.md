# ADR-001: Pipeline Error Handling Strategy for Video Generation

## Status

Accepted

## Date

2026-03-29

## Context

The video generation pipeline runs as a Temporal workflow with multiple asynchronous activities:
1. **Script generation** (`script_service`) — converts approved beat packages into scene contracts
2. **Media generation** (`media_activities`) — resolves top-half assets via browser capture or AI fallback
3. **Video assembly** (`video_activities`) — combines assets into final split-screen or slideshow video

Before this ADR, failures in media and assembly stages were swallowed silently. The workflow's exception handler returned `{status: "failed"}` without raising, which Temporal treated as a successful completion. Users had no visibility into failures and could wait indefinitely for videos that would never arrive. More critically, corrupted videos could be assembled without warning — when individual scenes failed asset generation, the remaining scenes would shift into wrong positions due to array index misalignment.

The codebase also lacked structured observability between stages. When debugging production issues, operators had to correlate logs manually across services with no consistent scene-level trace. Browser capture failures were indistinguishable from intentional AI fallbacks, making success rate monitoring impossible.

## Decision

We adopt the following error handling strategy:

### 1. Raise early on array mismatch, don't attempt recovery

**Rationale:** A duration/image array length mismatch means at least one scene fully failed asset generation. The `image_urls` list filters out `None` values while `scene_durations` maintains all N items from the script. Attempting assembly with misaligned arrays produces a corrupted video that looks valid but has wrong content — scene 3's visual paired with scene 4's audio, etc.

**Implementation:** `SceneAssetMismatchError` raised at `short_video_workflow.py:265-304` before assembly begins. This is marked as non-retryable (`retryable = False`) because the fundamental data is corrupt, not a transient failure.

### 2. Fallback AI image on browser capture failure, but always log it

**Rationale:** Browser capture is best-effort. Target pages can be:
- Temporarily down or slow (timeout)
- Behind authentication (403)
- Geo-blocked or rate-limited
- Structurally changed (element not found)

Blocking the entire video for one scene's capture failure is too disruptive to user experience. However, fallback must be traceable — operators need to monitor capture success rates to detect systematic issues with specific URLs or the capture infrastructure itself.

**Implementation:** 
- CP2 (`media_activities.py:641`) logs warning when `public_page_capture` has no `source_ref`
- CP3 (`media_activities.py:617,660`) logs full asset trace including `fallback_triggered` flag

### 3. Notify user via Telegram on workflow failure

**Rationale:** This is a consumer-facing product. Silent failure equals lost trust. Users who requested a video deserve to know:
- That generation failed
- What topic/workflow was affected
- A brief error summary

**Implementation:** `send_telegram_error_notification` activity called in the final except block (`short_video_workflow.py:395-420`). The notification is fire-and-forget:
- 30-second timeout
- 2 retry attempts
- Caught exceptions don't block the failure path

### 4. Set is_video flag only after upload confirms URL

**Rationale:** Previously, `is_video=True` was set in the return dictionary regardless of upload success. This created orphan asset records — database entries pointing to non-existent storage URLs. Assembly would later attempt to fetch these, failing with a confusing storage 404 instead of a clear "upload failed" error.

**Implementation:** `media_activities.py:607-616` now validates `storage_result.get("url")` exists before returning the asset record with `is_video=True`.

### 5. Use urlparse() for video URL detection

**Rationale:** Storage layer returns presigned URLs with query parameters:
```
https://s3.amazonaws.com/bucket/video.webm?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=...
```

The previous check `url.endswith(".webm")` fails because the URL ends with the signature, not the extension. This caused video assets to be misclassified as images, skipping the vstack split-screen layout entirely.

**Implementation:** `video_activities.py:25-40` adds `_is_video_url()` and `_get_extension_for_url()` helpers that use `urlparse(url).path` before checking extension.

## Consequences

### Positive

- **Fail-fast on corruption:** Videos are either correct or not produced at all — no silent corruption
- **User visibility:** Telegram notifications close the feedback loop on failures
- **Debuggability:** Checkpoint logs (CP1-CP7) provide scene-level traces across the pipeline
- **Capture monitoring:** `fallback_triggered` flag enables capture success rate dashboards
- **Cleaner storage:** No more orphan asset records from partial uploads

### Negative / Tradeoffs

- **Harder to test Temporal activities in isolation:** The error notification activity requires mocking Telegram client
- **More aggressive failure mode:** Some videos that previously "succeeded" (with wrong content) will now fail. Users may perceive increase in failure rate initially.
- **Log volume increase:** 7 new checkpoint logs per video increase storage costs. Consider sampling in high-volume production.

### Neutral

- Temporal retry policy unchanged (3 attempts per activity)
- No changes to API contracts or database schema
- HeyGen integration unaffected
- Browser automation timeout settings unchanged (Playwright default 30s)

## References

- `Project/python_services/services/errors.py` — `SceneAssetMismatchError` definition
- `Project/python_services/workflows/short_video_workflow.py` — Main workflow orchestration
- `Project/python_services/activities/media_activities.py` — Browser capture and AI fallback
- `Project/python_services/activities/video_activities.py` — Video assembly logic
- `Project/python_services/tests/test_pipeline_robustness.py` — Test coverage for all fixes
