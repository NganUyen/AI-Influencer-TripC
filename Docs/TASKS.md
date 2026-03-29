# Task Tracker — Video Generation Pipeline

## ✅ Done (Sprint 2026-03-29)

### Pipeline Robustness Fixes

- [x] **CRITICAL:** Fix scene duration/image array mismatch — `short_video_workflow.py:265-304`
  - Added `SceneAssetMismatchError` with failed scene detection
  - Aligned array building to filter both arrays together
  
- [x] **CRITICAL:** Add Telegram failure notification — `short_video_workflow.py:395-420` + `approval_activities.py`
  - New `send_telegram_error_notification` activity
  - Fire-and-forget with 30s timeout, 2 retries
  
- [x] **MEDIUM:** Prevent orphan asset record — `media_activities.py:607-616`
  - `is_video=True` only set after URL confirmed
  
- [x] **MEDIUM:** Fix presigned URL extension detection — `video_activities.py:25-40`
  - New `_is_video_url()` and `_get_extension_for_url()` helpers
  - Uses `urlparse(url).path` before extension check
  
- [x] **MEDIUM:** Validate `top_half_source_type` against allowed set — `script_service.py:204-214`
  - Invalid values logged as warning, default to `ai_visual_fallback`

### Observability (Checkpoint Logs)

- [x] **CP1:** SceneContract build log — `script_service.py:243`
- [x] **CP2:** Missing `source_ref` warning — `media_activities.py:641`
- [x] **CP3:** Per-scene asset resolution trace — `media_activities.py:617,660`
- [x] **CP5:** URL type detection log — `video_activities.py:128`
- [x] **CP6:** Per-scene assembly log — `video_activities.py:178`
- [x] **CP7:** Slideshow fallback log — `video_activities.py:345`

### Tests

- [x] `test_duration_mismatch_raises_with_failed_scenes`
- [x] `test_browser_capture_none_source_ref_logs_warning`
- [x] `test_browser_capture_failure_fallbacks_to_ai`
- [x] `test_is_video_url_with_presigned_s3_webm`
- [x] `test_is_video_url_with_presigned_s3_mp4`
- [x] `test_orphan_asset_not_created_on_upload_failure`
- [x] `test_workflow_sends_telegram_on_failure`
- [x] `test_invalid_source_type_defaults_to_ai_visual_fallback`

### Documentation

- [x] `Docs/CHANGELOG.md` — Keep a Changelog format
- [x] `Docs/ADR/001-pipeline-error-handling.md` — Decision record
- [x] `Docs/RUNBOOK.md` — Operator alert guide
- [x] `Docs/TASKS.md` — This file

---

## 🔄 In Progress

- [ ] **Review test coverage** — Confirm all 8 tests pass in CI
  - File: `tests/test_pipeline_robustness.py`
  - Blocked by: CI runner setup

- [ ] **Verify Telegram notification in staging** — End-to-end test
  - Trigger intentional failure in staging workflow
  - Confirm notification arrives in test Telegram channel

---

## 🔴 Open Issues (Not Yet Fixed)

### High Priority

- [ ] **CP4 missing from assembly** — Mismatch guard added but CP4 structured log (with full scene list) not yet wired to monitoring dashboard
  - Owner: TBD
  - File: `short_video_workflow.py:265-304`
  - Action: Add structured JSON log compatible with DataDog/CloudWatch

- [ ] **No retry for browser capture** — Current behavior: fail once → AI fallback immediately
  - Consider: 1 retry with 5s delay before fallback
  - File: `media_activities.py:559-573`
  - Risk: Adds latency per scene; needs timeout budget analysis first
  - Decision needed: Is 5s extra latency acceptable for higher capture success?

- [ ] **Telegram notification content too generic**
  - Current: `"Video generation failed: SceneAssetMismatchError"`
  - Better: Include scene count, which scenes failed, estimated retry time
  - File: `approval_activities.py` → `send_telegram_error_notification`

### Medium Priority

- [ ] **No capture success rate metric** — CP2/CP3 logs exist but not aggregated
  - Need: Dashboard showing `fallback_triggered` rate per day
  - Requires: Log aggregation setup (DataDog / CloudWatch / custom)
  - Effort: ~2 days with existing log infrastructure

- [ ] **`script_service.py:195` default hardcoded as `ai_visual_fallback`**
  - Should be configurable via env var or config file
  - Low effort, reduces risk of silent behavior change on contract update
  - File: `script_service.py:210`

- [ ] **No integration test for full workflow** — Current tests are unit-level only
  - Need: End-to-end test with mocked Temporal worker + mocked storage
  - File: `tests/test_workflow_integration.py` (new)
  - Effort: ~3 days

### Low Priority

- [ ] **ADR-002 needed: Top half routing strategy**
  - Current routing logic (capture → fallback) is not documented as a decision
  - Pair with any future change to `source_type` priority order
  - File: `Docs/ADR/002-top-half-routing.md` (new)

- [ ] **RUNBOOK not linked from README**
  - Add `## Operations` section to `README.md` pointing to `Docs/RUNBOOK.md`
  - Effort: 5 minutes

- [ ] **Cleanup old workflow versions** — Deprecated workflow code still in repo
  - Identify: `workflows/old_*.py` files
  - Action: Remove after confirming no running instances

---

## 📌 Notes

### Breaking Changes
- None. All fixes in this sprint are additive/non-breaking.
- No API contract changes.
- No database schema changes.

### Configuration
- `_VALID_TOP_HALF_SOURCE_TYPES` in `script_service.py` is the single source of truth for valid types:
  - `public_page_capture`
  - `authenticated_capture_later`
  - `ai_visual_fallback`
  - `hybrid_candidate`
  - `search`

### Temporal Settings
- Activity retry policy: 3 attempts per activity (default)
- No workflow-level restart on completion
- `SceneAssetMismatchError` marked as non-retryable

### File References

| Component | Primary File | Key Lines |
|-----------|--------------|-----------|
| Workflow orchestration | `workflows/short_video_workflow.py` | 79-420 |
| Script generation | `services/script_service.py` | 166-250 |
| Media activities | `activities/media_activities.py` | 549-670 |
| Video assembly | `activities/video_activities.py` | 62-350 |
| Error types | `services/errors.py` | 121-124 |
| Tests | `tests/test_pipeline_robustness.py` | all |

---

## 📅 Sprint History

| Sprint | Focus | Completed |
|--------|-------|-----------|
| 2026-03-29 | Pipeline robustness, error handling, observability | 5 fixes, 7 logs, 8 tests |
| 2026-03-28 | Top-half implementation, browser capture | Initial pipeline |
