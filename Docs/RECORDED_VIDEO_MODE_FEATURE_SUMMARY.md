# Recorded Demo Video Mode - Feature Summary

> **Status**: Complete (Phases 1-8 implemented and verified)  
> **Last Updated**: 2026-04-01

## 1. Feature Overview

Recorded Demo Video Mode allows users to upload a screen recording of their product demo and have the system automatically:

1. Analyze the video to extract features and timeline structure
2. Ground detected features against official documentation
3. Generate a creative concept based on the video content
4. Produce timestamp-aware beat sheets that map to specific video segments
5. Assemble final videos using extracted segments from the original demo

This is an alternative to the existing `idea_brief` flow, where users type a product description.

### Key Differentiator

The pipeline uses the **user's actual recorded demo** as the top-half visual source, rather than generating AI images or capturing live web pages. Timestamp ranges from the beat sheet map directly to video segments extracted via ffmpeg.

## 2. User Flow

```
1. User selects "recorded_demo_video" input mode
2. User uploads demo video via Telegram
3. User provides reference URL (optional) and video goal
4. System analyzes video → extracts features, timeline, OCR text
5. System grounds features against official docs (OpenClaw)
6. System presents preview with detected features + warnings
7. User confirms/corrects/re-emphasizes preview
8. System generates concept brief from grounded evidence
9. User approves concept → system generates beat sheet
10. Beat sheet contains timestamp ranges (e.g., "00:00:05-00:00:10")
11. User approves beats → production package ready
12. Production workflow extracts segments via ffmpeg
13. Final split-screen video assembled with trimmed demo + talking head
```

## 3. Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 4: Analysis                                                │
│  DemoVideoAnalyzerService.analyze_demo_video()                  │
│  → metadata, keyframes, segments, OCR text, features            │
│  → RecordedDemoEvidenceContract                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 5: Grounding                                               │
│  DemoFeatureGroundingService.enrich_with_official_names()       │
│  → OpenClaw lookup against reference URL                        │
│  → grounded_features[], official_name, value_proposition        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 5b: Preview                                                │
│  video_ai.py → build_preview_summary() + build_preview_warnings()│
│  → User sees features, timeline, confidence warnings            │
│  → Actions: confirm, correct, re-emphasize, reupload            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6: Concept                                                 │
│  CreativeDirectorService.build_concept_from_demo_evidence()     │
│  → ConceptBriefContract with demo_video_asset_url               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6b: Beats                                                  │
│  CreativeDirectorService.build_beat_sheet_from_demo_evidence()  │
│  → BeatSheetContract with timestamp ranges + trim_confidence    │
│  → top_half_source_type = "uploaded_demo_video"                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 7: Production                                              │
│  generate_scene_images() → routes to _extract_uploaded_demo_segment()│
│  → Downloads demo video                                          │
│  → ffmpeg extracts segment by timestamp range                   │
│  → Uploads to storage                                            │
│  → Returns {url, is_video: True}                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 7b: Assembly                                               │
│  build_split_screen_video()                                      │
│  → Stacks extracted demo segment (top) + talking head (bottom)  │
│  → Final 1080x1920 vertical video                               │
└─────────────────────────────────────────────────────────────────┘
```

## 4. What Was Added by Phase

| Phase | What | Files |
|-------|------|-------|
| **1** | Input mode toggle, Telegram upload handler | `skills/video_ai.py`, `telegram_renderer.py` |
| **2** | Video storage, asset upload | `services/media_storage_service.py` |
| **3** | Input routing for recorded_demo_video | `skills/video_ai.py` |
| **4** | Video analysis (ffprobe, scene detection, OCR) | `services/demo_video_analyzer_service.py` |
| **5** | Feature grounding via OpenClaw | `services/demo_feature_grounding_service.py` |
| **5b** | Preview flow with confirm/correct/re-emphasize | `skills/video_ai.py`, `telegram_renderer.py` |
| **6** | Concept brief from demo evidence | `services/creative_director_service.py` |
| **6b** | Beat sheet with timestamp ranges | `services/creative_director_service.py` |
| **7** | Segment extraction via ffmpeg | `activities/media_activities.py` |
| **7b** | Split-screen assembly with video segments | `activities/video_activities.py` |
| **8** | Failure policy, OCR signals, warnings, sanitization | `services/recorded_demo_failure_policy.py` |

## 5. Key Contracts and Important Fields

### RecordedDemoEvidenceContract
```python
demo_video_asset_url: str          # Storage URL of uploaded demo
duration_sec: float                # Video length
width: int, height: int            # Resolution
keyframes: List[KeyframeContract]  # Representative frames
segments: List[TimelineSegmentContract]  # Timeline breakdown
extracted_features: List[ExtractedFeatureContract]  # OCR-detected features
grounded_features: List[GroundedFeatureContract]    # Verified features
analysis_confidence_overall: "high" | "medium" | "low"
confidence_signals: Dict[str, Any]  # OCR signals, debug info
```

### Beat with uploaded_demo_video
```python
{
    "idx": 1,
    "top_half_source_type": "uploaded_demo_video",
    "top_half_target": "00:00:05-00:00:10",  # Timestamp range
    "source_ref": "<demo_video_asset_url>",  # Video URL
    "trim_confidence": 0.85,                  # Range confidence
    "bottom_half_message": "...",
    "overlay_text": "...",
    "duration_sec": 5
}
```

### SceneContract additions
```python
source_ref: Optional[str]  # Demo video URL for uploaded_demo_video type
```

### VALID_TOP_HALF_SOURCE_TYPES
```python
{
    "public_page_capture",
    "authenticated_capture_later",
    "ai_visual_fallback",
    "hybrid_candidate",
    "uploaded_demo_video",  # ← New
}
```

## 6. Failure Handling Behavior

### Severity Levels
- **silent**: Continue without notification
- **warn**: Continue with preview warning (user sees it, doesn't block)
- **block**: Stop and require user action

### Analysis Stage
| Condition | Result |
|-----------|--------|
| Metadata extraction failed (duration=0) | Block |
| Low confidence + no features + no OCR | Block |
| Low confidence + has features | Warn |
| OCR unavailable | Warn |
| Medium/high confidence | Silent |

### Grounding Stage
| Condition | Result |
|-----------|--------|
| Zero grounded features + low confidence | Block |
| Zero grounded features + medium+ confidence | Warn |
| Has grounded features | Silent |

### Trim Confidence (Production)
| Range | Semantics |
|-------|-----------|
| >= 0.8 | Normal - proceed with trim |
| 0.5-0.79 | Caution - warn boundaries may be approximate |
| < 0.5 | Conservative hold - use conservative window |

### Error Sanitization
Technical errors are sanitized before Telegram notification:
- `ffmpeg` errors → "Video processing encountered an issue. Please try again."
- `/tmp/` paths → "Temporary storage issue. Please try again in a few minutes."
- Stack traces → "An internal error occurred. Our team has been notified."

## 7. Backward Compatibility

- Existing `idea_brief` flow is unchanged
- `creative_input_mode` defaults to `"idea_brief"` if not specified
- New `uploaded_demo_video` source type is additive
- Existing `public_page_capture` and `ai_visual_fallback` continue to work
- All existing tests pass (no regressions)

## 8. What Is Intentionally Out of Scope

1. **Vision model frame analysis** - OCR-only for Phase 4
2. **Authenticated page capture** - Uses public URLs only
3. **Auto-retry on trim failure** - Requires user action
4. **Real-time progress during analysis** - Single progress notification
5. **Multiple demo video uploads** - One video per session
6. **Video preview in Telegram** - Text summary only
7. **Automatic timestamp refinement** - Uses detected ranges as-is
8. **idea_brief flow changes** - Completely separate path

## 9. Current Verification Status

### Test Coverage
| Test File | Tests | Status |
|-----------|-------|--------|
| `test_recorded_demo_failure_policy.py` | 11 | Pass |
| `test_video_ai_demo_preview.py` | 28 | Pass |
| `test_telegram_renderer.py` | 16 | Pass |
| `test_pipeline_robustness.py` (recorded_demo) | 1 | Pass |
| **Total Phase 8 focused** | **56** | **Pass** |

### Verified Behaviors
- Low confidence warns when usable, blocks only on combined weakness
- OCR unavailable vs weak distinguished correctly
- Zero grounding warns, blocks only on combined low confidence
- Trim confidence stays in conservative_hold semantics
- Telegram error messages sanitized (no ffmpeg, paths, traces leaked)
- Demo preview renders warnings section
- Production failure propagates sanitized error to user

## 10. Recommended Next Improvements

### High Priority
1. **Vision model integration** - Replace OCR-only with frame analysis for better feature detection
2. **Trim preview** - Show user the detected timestamp ranges before production
3. **Segment confidence feedback** - Allow user to adjust timestamp ranges manually

### Medium Priority
4. **Multiple demo support** - Allow stitching segments from different recordings
5. **Audio extraction** - Use original demo audio for voiceover context
6. **Progress streaming** - Real-time updates during analysis/grounding

### Lower Priority
7. **Scene change visualization** - Show detected transitions in preview
8. **Feature deduplication** - Merge overlapping OCR detections
9. **Grounding cache** - Reuse OpenClaw results for same reference URL

---

## Quick Reference: File Locations

| Component | Path |
|-----------|------|
| Skill orchestration | `skills/video_ai.py` |
| Video analysis | `services/demo_video_analyzer_service.py` |
| Feature grounding | `services/demo_feature_grounding_service.py` |
| Failure policy | `services/recorded_demo_failure_policy.py` |
| Concept/beats | `services/creative_director_service.py` |
| Segment extraction | `activities/media_activities.py` |
| Video assembly | `activities/video_activities.py` |
| Workflow error handling | `workflows/short_video_workflow.py` |
| Telegram rendering | `services/telegram_renderer.py` |
| Contracts | `services/contracts.py` |
