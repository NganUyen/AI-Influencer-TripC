# Recorded Demo Video Mode - Implementation Spec

> **Status**: Draft  
> **Canonical Requirement Spec**: `Docs/RECORDED_VIDEO_MODE.md`  
> **Target Codebase**: `Project/python_services/`

---

## 1. Summary

This document translates the product requirements from `RECORDED_VIDEO_MODE.md` into a concrete implementation plan for the existing AI Influencer codebase. The new `recorded_demo_video` mode is a **pre-production input extension** that:

1. Accepts an uploaded screen recording (demo video) via Telegram
2. Analyzes the video to extract features, UI segments, and timeline structure
3. Grounds extracted features against official website documentation (via OpenClaw)
4. Generates a ConceptBrief and BeatSheet with precise trim timestamps
5. Uses the uploaded video segments as top-half footage in the final split-screen video

**Core Principle**: The production backbone (`ShortVideoWorkflow`) remains unchanged. All new logic lives in pre-production (skills, services, contracts).

---

## 2. Codebase Mapping

| Spec Concept | Current Implementation | Changes Required |
|--------------|------------------------|------------------|
| Input mode selection | `VideoAISkill.pick_persona` step | Add mode selection step before persona |
| Video upload handling | N/A | New step in `step_config.py`, file handler in `video_ai.py` |
| Quality gate | N/A | New `VideoQualityGateService` |
| Video analysis | N/A | New `DemoVideoAnalysisService` |
| Evidence schema | `ConceptBriefContract.creative_input_mode` | Add `RecordedDemoEvidenceContract` |
| Feature grounding | `OpenClawService` (web grounding) | Extend with `ground_features_against_docs()` |
| Preview confirm | N/A | New Telegram step with timeout |
| Beat timestamps | `BeatContract.top_half_target` | Add `trim_start`, `trim_end`, `trim_confidence` |
| Top-half source | `top_half_source_type: "browser_capture"` | Add `"uploaded_video_segment"` option |
| Production handoff | `ApprovedProductionPackageContract` | Add `demo_video_asset_url` field |

### File Impact Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `services/contracts.py` | Extend | New contracts, extended enums |
| `services/step_config.py` | Extend | New steps for recorded_demo flow |
| `skills/video_ai.py` | Major | Add recorded_demo_video handlers |
| `services/creative_director_service.py` | Extend | Handle new evidence type |
| `services/video_analysis_service.py` | **New** | Video analysis pipeline |
| `services/video_quality_gate_service.py` | **New** | Pre-analysis validation |
| `activities/media_activities.py` | Extend | Handle uploaded video segments |
| `agents/openclaw_telegram_skill_configs.py` | Extend | Update skill definition |

---

## 3. Data Contracts

### 3.1 New Contracts

```python
# services/contracts.py

class VideoQualityReport(BaseModel):
    """Result of quality gate checks."""
    passed: bool
    duration_sec: float
    resolution: tuple[int, int]  # (width, height)
    blur_score: float  # 0-1, higher = sharper
    failure_reasons: list[str]  # Empty if passed
    
class ExtractedFeature(BaseModel):
    """A feature detected in the demo video."""
    feature_id: str  # UUID
    name: str
    description: str
    timestamp_range: str  # "HH:MM:SS-HH:MM:SS"
    confidence: Literal["high", "medium", "low"]
    ocr_evidence: list[str]  # Text strings found via OCR
    keyframe_refs: list[str]  # URLs/paths to keyframe images

class GroundedFeature(BaseModel):
    """Feature after OpenClaw grounding."""
    feature: ExtractedFeature
    grounded: bool
    official_name: str | None  # From website docs
    official_description: str | None
    source_url: str | None  # Where it was verified

class TimelineSegment(BaseModel):
    """A logical segment of the demo video."""
    segment_id: str
    start_time: str  # "HH:MM:SS"
    end_time: str  # "HH:MM:SS"
    segment_type: Literal["intro", "feature_demo", "transition", "outro", "unknown"]
    description: str
    features_shown: list[str]  # feature_ids

class RecordedDemoEvidenceContract(BaseModel):
    """Evidence extracted from uploaded demo video."""
    demo_video_asset_url: str  # Telegram file URL or blob storage URL
    original_filename: str
    duration_sec: float
    resolution: tuple[int, int]
    
    # Analysis results
    timeline_segments: list[TimelineSegment]
    extracted_features: list[ExtractedFeature]
    grounded_features: list[GroundedFeature]
    
    # Summaries for LLM consumption
    visual_layout_summary: str  # "Mobile app with bottom nav, card-based UI..."
    timeline_narrative: str  # "Video starts with login screen, then shows..."
    feature_candidates: list[str]  # Top features to highlight
    
    # Confidence
    overall_analysis_confidence: Literal["high", "medium", "low"]
    low_confidence_areas: list[str]  # Areas needing user clarification

class DemoVideoPreviewContract(BaseModel):
    """Preview shown to user before ConceptBrief generation."""
    evidence: RecordedDemoEvidenceContract
    suggested_features: list[str]  # Top 3-5 features to focus on
    suggested_video_goal: Literal["promo", "walkthrough", "tutorial"]
    suggested_duration_sec: int  # Recommended final video length
    user_confirmed: bool = False
    user_adjustments: dict | None = None  # Any changes user made
```

### 3.2 Contract Extensions

```python
# Extend CreativeInputMode
CreativeInputMode = Literal["idea_brief", "recorded_demo_video"]

# Extend ConceptBriefContract
class ConceptBriefContract(BaseModel):
    # ... existing fields ...
    creative_input_mode: CreativeInputMode
    
    # New: only populated for recorded_demo_video mode
    demo_evidence: RecordedDemoEvidenceContract | None = None

# Extend BeatContract
class BeatContract(BaseModel):
    # ... existing fields ...
    beat_number: int
    description: str
    top_half_source_type: Literal["browser_capture", "ai_generated", "uploaded_video_segment"]
    top_half_target: str  # URL for browser, prompt for AI, timestamp for video
    duration_sec: float
    
    # New: for uploaded_video_segment source type
    trim_start: str | None = None  # "HH:MM:SS.mmm"
    trim_end: str | None = None  # "HH:MM:SS.mmm"
    trim_confidence: Literal["high", "medium", "low"] | None = None
    segment_id: str | None = None  # Reference to TimelineSegment

# Extend ApprovedProductionPackageContract
class ApprovedProductionPackageContract(BaseModel):
    # ... existing fields ...
    
    # New: for recorded_demo_video mode
    demo_video_asset_url: str | None = None  # URL to uploaded video for trimming
```

### 3.3 Telegram Session Shape Extension

```python
# agents/openclaw_telegram_skill_configs.py

VIDEO_AI_SESSION_SHAPE = {
    # Existing
    "persona_id": str,
    "idea_brief": str,
    "feature_focus": str,
    "video_goal": str,
    "audience": str,
    "cta": str,
    "reference_url": str,
    "access_level": str,
    
    # New for recorded_demo_video mode
    "creative_input_mode": str,  # "idea_brief" | "recorded_demo_video"
    "demo_video_file_id": str,  # Telegram file_id
    "demo_video_asset_url": str,  # After upload to blob storage
    "demo_evidence": dict,  # Serialized RecordedDemoEvidenceContract
    "preview_confirmed": bool,
    "user_feature_selection": list,  # User-confirmed features to focus on
}
```

---

## 4. Telegram Flow Changes

### 4.1 Step Configuration

```python
# services/step_config.py

STEP_CONFIG = {
    "video-ai": {
        # New: Mode selection (first step)
        "select_mode": {
            "prompt": "How would you like to create your video?\n\n"
                      "1️⃣ **Idea Brief** - Describe your video idea\n"
                      "2️⃣ **Demo Video** - Upload a screen recording",
            "type": "choice",
            "choices": ["idea_brief", "recorded_demo_video"],
            "next": {
                "idea_brief": "pick_persona",
                "recorded_demo_video": "upload_demo_video"
            }
        },
        
        # New: Video upload step
        "upload_demo_video": {
            "prompt": "📹 Please upload your demo video.\n\n"
                      "Requirements:\n"
                      "• Duration: 30 seconds to 3 minutes\n"
                      "• Resolution: 720p or higher\n"
                      "• Format: MP4, MOV, or WebM",
            "type": "video",
            "next": "quality_gate",
            "timeout_sec": 300  # 5 min to upload
        },
        
        # New: Quality gate (automatic, no user input)
        "quality_gate": {
            "type": "automatic",
            "action": "run_quality_gate",
            "next_on_pass": "analyzing_video",
            "next_on_fail": "quality_gate_failed"
        },
        
        # New: Quality gate failure
        "quality_gate_failed": {
            "prompt": "❌ Video quality check failed:\n{failure_reasons}\n\n"
                      "Please upload a different video.",
            "type": "video",
            "next": "quality_gate"
        },
        
        # New: Analysis in progress
        "analyzing_video": {
            "prompt": "🔍 Analyzing your demo video...\n"
                      "This may take 1-2 minutes.",
            "type": "automatic",
            "action": "analyze_demo_video",
            "next": "preview_confirm",
            "timeout_sec": 180  # 3 min max
        },
        
        # New: Preview confirmation with timeout
        "preview_confirm": {
            "prompt": "📋 **Analysis Complete**\n\n"
                      "{preview_summary}\n\n"
                      "Detected features:\n{feature_list}\n\n"
                      "Suggested focus: {suggested_features}\n\n"
                      "Does this look correct? You can:\n"
                      "• ✅ Confirm to proceed\n"
                      "• ✏️ Adjust the feature focus\n"
                      "• 🔄 Re-upload a different video",
            "type": "choice",
            "choices": ["confirm", "adjust", "re-upload"],
            "timeout_sec": 900,  # 15 min
            "timeout_action": "auto_confirm",
            "next": {
                "confirm": "pick_persona",
                "adjust": "adjust_features",
                "re-upload": "upload_demo_video"
            }
        },
        
        # New: Feature adjustment
        "adjust_features": {
            "prompt": "Which features should we focus on?\n"
                      "Reply with feature numbers (e.g., '1, 3, 4') or describe what to highlight:",
            "type": "text",
            "next": "pick_persona"
        },
        
        # Existing steps continue...
        "pick_persona": { ... },
        # ... rest unchanged, but skip idea_brief step if mode is recorded_demo_video
    }
}
```

### 4.2 Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      RECORDED DEMO VIDEO FLOW                    │
└─────────────────────────────────────────────────────────────────┘

User starts /video-ai
        │
        ▼
┌───────────────┐
│ select_mode   │──── idea_brief ────► [Existing flow unchanged]
└───────────────┘
        │
    recorded_demo_video
        │
        ▼
┌───────────────────┐
│ upload_demo_video │◄─────────────────┐
└───────────────────┘                  │
        │                              │
        ▼                              │
┌───────────────┐     fail            │
│ quality_gate  │─────────────────────┤
└───────────────┘                     │
        │ pass                         │
        ▼                              │
┌───────────────────┐                  │
│ analyzing_video   │                  │
└───────────────────┘                  │
        │                              │
        ▼                              │
┌───────────────────┐     re-upload    │
│ preview_confirm   │──────────────────┘
└───────────────────┘
        │ confirm/adjust
        ▼
┌───────────────┐
│ pick_persona  │
└───────────────┘
        │
        ▼
┌───────────────┐
│ collect_goal  │  (skip idea_brief, feature_focus optional)
└───────────────┘
        │
        ▼
┌───────────────┐
│ reference_url │  (still needed for grounding)
└───────────────┘
        │
        ▼
┌───────────────────────┐
│ generate_concept      │  (uses demo_evidence)
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ confirm_beats         │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ start_production      │  (handoff to ShortVideoWorkflow)
└───────────────────────┘
```

---

## 5. Backend/Workflow Changes

### 5.1 New Services

#### VideoQualityGateService

```python
# services/video_quality_gate_service.py

class VideoQualityGateService:
    """Validates uploaded demo videos before analysis."""
    
    HARD_LIMITS = {
        "max_duration_sec": 180,
        "min_duration_sec": 30,
        "min_resolution": (1280, 720),  # 720p
        "min_blur_score": 0.3,  # Reject very blurry videos
    }
    
    async def validate(self, video_path: str) -> VideoQualityReport:
        """Run all quality checks on uploaded video."""
        # 1. Extract metadata (ffprobe)
        # 2. Check duration
        # 3. Check resolution
        # 4. Sample frames for blur detection
        # 5. Return report
        
    async def _extract_metadata(self, path: str) -> dict:
        """Use ffprobe to get video metadata."""
        
    async def _check_blur(self, path: str, sample_count: int = 5) -> float:
        """Sample frames and compute average blur score."""
        # Use Laplacian variance method
```

#### DemoVideoAnalysisService

```python
# services/demo_video_analysis_service.py

class DemoVideoAnalysisService:
    """Analyzes demo videos to extract features and timeline."""
    
    def __init__(
        self,
        openclaw_service: OpenClawService,
        storage_service: StorageService,
    ):
        self.openclaw = openclaw_service
        self.storage = storage_service
    
    async def analyze(
        self,
        video_url: str,
        reference_url: str,
    ) -> RecordedDemoEvidenceContract:
        """Full analysis pipeline."""
        # 1. Download video to temp
        # 2. Extract keyframes (scene detection)
        # 3. Run OCR on keyframes
        # 4. Segment timeline
        # 5. Extract features from segments
        # 6. Ground features against reference_url
        # 7. Build evidence contract
        
    async def _extract_keyframes(self, video_path: str) -> list[KeyFrame]:
        """Extract keyframes using scene detection."""
        # Use ffmpeg scene detection or pyscenedetect
        
    async def _run_ocr(self, keyframes: list[KeyFrame]) -> dict[str, list[str]]:
        """Run OCR on keyframes, return {frame_id: [texts]}."""
        # Use pytesseract or cloud OCR
        
    async def _segment_timeline(
        self,
        keyframes: list[KeyFrame],
        ocr_results: dict,
    ) -> list[TimelineSegment]:
        """Group keyframes into logical segments."""
        # Use LLM to classify segments
        
    async def _extract_features(
        self,
        segments: list[TimelineSegment],
        ocr_results: dict,
    ) -> list[ExtractedFeature]:
        """Identify features from segments and OCR."""
        
    async def _ground_features(
        self,
        features: list[ExtractedFeature],
        reference_url: str,
    ) -> list[GroundedFeature]:
        """Verify features against official website."""
        # Use OpenClaw to browse reference_url and verify
```

### 5.2 Service Extensions

#### CreativeDirectorService

```python
# services/creative_director_service.py

class CreativeDirectorService:
    # ... existing methods ...
    
    async def build_concept_from_demo_evidence(
        self,
        evidence: RecordedDemoEvidenceContract,
        persona_id: str,
        video_goal: str,
        audience: str,
        cta: str,
        user_feature_selection: list[str] | None = None,
    ) -> ConceptBriefContract:
        """Build ConceptBrief from demo video evidence."""
        # 1. Select features (user selection or auto from grounded)
        # 2. Build narrative from timeline
        # 3. Generate concept via OpenClaw with evidence context
        
    async def build_beats_from_demo_evidence(
        self,
        concept: ConceptBriefContract,
        evidence: RecordedDemoEvidenceContract,
    ) -> BeatSheetContract:
        """Generate BeatSheet with precise trim timestamps."""
        # 1. Map concept points to timeline segments
        # 2. Generate beats with:
        #    - top_half_source_type = "uploaded_video_segment"
        #    - trim_start/trim_end from segment timestamps
        #    - trim_confidence based on segment detection confidence
```

#### OpenClawService

```python
# services/openclaw_service.py

class OpenClawService:
    # ... existing methods ...
    
    async def ground_features_against_docs(
        self,
        features: list[ExtractedFeature],
        reference_url: str,
    ) -> list[GroundedFeature]:
        """Verify extracted features against official website."""
        # 1. Navigate to reference_url
        # 2. For each feature:
        #    - Search for feature name/description
        #    - Check if feature exists in docs
        #    - Extract official name/description if found
        # 3. Return grounded features
```

### 5.3 Skill Handler Changes

```python
# skills/video_ai.py

class VideoAISkill(BaseSkill):
    # ... existing methods ...
    
    async def handle_select_mode(
        self,
        session: SkillSession,
        message: str,
    ) -> SkillResult:
        """Handle mode selection."""
        mode = self._parse_mode_choice(message)
        session.data["creative_input_mode"] = mode
        
        if mode == "recorded_demo_video":
            return SkillResult(
                next_step="upload_demo_video",
                message="Please upload your demo video...",
            )
        else:
            return SkillResult(
                next_step="pick_persona",
                message="Great! Let's pick a persona...",
            )
    
    async def handle_upload_demo_video(
        self,
        session: SkillSession,
        message: Message,  # Telegram message with video
    ) -> SkillResult:
        """Handle video upload."""
        if not message.video and not message.document:
            return SkillResult(
                next_step="upload_demo_video",
                message="Please upload a video file.",
                error=True,
            )
        
        # 1. Download video from Telegram
        file_id = message.video.file_id if message.video else message.document.file_id
        video_path = await self._download_telegram_file(file_id)
        
        # 2. Upload to blob storage
        asset_url = await self.storage.upload(video_path, "demo-videos/")
        
        session.data["demo_video_file_id"] = file_id
        session.data["demo_video_asset_url"] = asset_url
        
        return SkillResult(
            next_step="quality_gate",
            auto_advance=True,
        )
    
    async def handle_quality_gate(
        self,
        session: SkillSession,
    ) -> SkillResult:
        """Run quality gate checks."""
        video_url = session.data["demo_video_asset_url"]
        report = await self.quality_gate_service.validate(video_url)
        
        if not report.passed:
            return SkillResult(
                next_step="quality_gate_failed",
                message=f"Video quality check failed:\n" + 
                        "\n".join(f"• {r}" for r in report.failure_reasons),
            )
        
        session.data["quality_report"] = report.model_dump()
        return SkillResult(
            next_step="analyzing_video",
            auto_advance=True,
        )
    
    async def handle_analyzing_video(
        self,
        session: SkillSession,
    ) -> SkillResult:
        """Run video analysis."""
        video_url = session.data["demo_video_asset_url"]
        reference_url = session.data.get("reference_url", "")
        
        evidence = await self.analysis_service.analyze(
            video_url=video_url,
            reference_url=reference_url,
        )
        
        session.data["demo_evidence"] = evidence.model_dump()
        
        # Build preview
        preview = self._build_preview_message(evidence)
        
        return SkillResult(
            next_step="preview_confirm",
            message=preview,
        )
    
    async def handle_preview_confirm(
        self,
        session: SkillSession,
        message: str,
    ) -> SkillResult:
        """Handle preview confirmation."""
        choice = self._parse_preview_choice(message)
        
        if choice == "confirm":
            session.data["preview_confirmed"] = True
            return SkillResult(
                next_step="pick_persona",
                message="Great! Let's pick a persona...",
            )
        elif choice == "adjust":
            return SkillResult(
                next_step="adjust_features",
                message="Which features should we focus on?",
            )
        else:  # re-upload
            return SkillResult(
                next_step="upload_demo_video",
                message="Please upload a different video.",
            )
```

### 5.4 Activity Changes for Production

```python
# activities/media_activities.py

@activity.defn
async def generate_scene_images(
    scene: SceneContract,
    approved_package: ApprovedProductionPackageContract,
) -> str:
    """Generate top-half image/video for a scene."""
    
    beat = _find_beat_for_scene(scene, approved_package)
    
    if beat.top_half_source_type == "uploaded_video_segment":
        # NEW: Extract segment from uploaded demo video
        return await _extract_video_segment(
            video_url=approved_package.demo_video_asset_url,
            trim_start=beat.trim_start,
            trim_end=beat.trim_end,
            target_duration=beat.duration_sec,
        )
    elif beat.top_half_source_type == "browser_capture":
        # Existing: Browser capture via OpenClaw
        return await _capture_browser_screenshot(beat.top_half_target)
    else:
        # Existing: AI-generated fallback
        return await _generate_ai_image(beat.top_half_target)


async def _extract_video_segment(
    video_url: str,
    trim_start: str,
    trim_end: str,
    target_duration: float,
) -> str:
    """Extract and process a segment from the demo video."""
    # 1. Download video (or use cached)
    # 2. Use ffmpeg to extract segment
    # 3. Scale/crop to target dimensions
    # 4. Upload to storage
    # 5. Return URL
```

---

## 6. Error Handling

### 6.1 Error Categories

| Error Type | Handling | User Message |
|------------|----------|--------------|
| Upload timeout | Retry prompt | "Upload timed out. Please try again." |
| Quality gate fail | Re-upload prompt | "Video doesn't meet requirements: {reasons}" |
| Analysis timeout | Retry or fallback | "Analysis taking longer than expected. Retrying..." |
| Analysis failure | Fall back to idea_brief | "Couldn't analyze video. Would you like to describe it instead?" |
| Grounding failure | Continue with ungrounded | "Couldn't verify some features. Proceeding with analysis results." |
| Preview timeout | Auto-confirm | "No response received. Proceeding with suggested settings." |
| Trim extraction fail | AI fallback | Beat uses AI-generated top-half instead |

### 6.2 Timeout Configuration

```python
# services/timeout_config.py

RECORDED_DEMO_TIMEOUTS = {
    "upload": 300,  # 5 minutes
    "quality_gate": 60,  # 1 minute
    "analysis": 180,  # 3 minutes
    "preview_confirm": 900,  # 15 minutes
    "feature_adjust": 600,  # 10 minutes
}
```

### 6.3 Graceful Degradation

```python
# skills/video_ai.py

async def handle_analysis_failure(
    self,
    session: SkillSession,
    error: Exception,
) -> SkillResult:
    """Handle analysis failure with graceful degradation."""
    
    # Option 1: Retry with simpler analysis
    if session.data.get("analysis_retry_count", 0) < 2:
        session.data["analysis_retry_count"] = session.data.get("analysis_retry_count", 0) + 1
        return SkillResult(
            next_step="analyzing_video",
            message="Analysis encountered an issue. Retrying with simplified settings...",
        )
    
    # Option 2: Fall back to idea_brief mode
    return SkillResult(
        next_step="fallback_to_idea_brief",
        message="We couldn't fully analyze your video. Would you like to:\n"
                "1. Describe the video content manually\n"
                "2. Try uploading a different video",
    )
```

---

## 7. Acceptance Mapping

Mapping each acceptance criterion from `RECORDED_VIDEO_MODE.md` to implementation:

| # | Acceptance Criterion | Implementation Location |
|---|---------------------|------------------------|
| 1 | User can upload video via Telegram | `video_ai.py:handle_upload_demo_video` |
| 2 | Quality gate rejects videos >180s | `video_quality_gate_service.py:validate` |
| 3 | Quality gate rejects <720p | `video_quality_gate_service.py:validate` |
| 4 | Quality gate rejects blurry videos | `video_quality_gate_service.py:_check_blur` |
| 5 | System extracts keyframes | `demo_video_analysis_service.py:_extract_keyframes` |
| 6 | System runs OCR on keyframes | `demo_video_analysis_service.py:_run_ocr` |
| 7 | System segments timeline | `demo_video_analysis_service.py:_segment_timeline` |
| 8 | System extracts features | `demo_video_analysis_service.py:_extract_features` |
| 9 | Features grounded via OpenClaw | `openclaw_service.py:ground_features_against_docs` |
| 10 | User sees preview before confirm | `video_ai.py:handle_preview_confirm` |
| 11 | 15-min timeout on preview | `step_config.py:preview_confirm.timeout_sec` |
| 12 | User can adjust feature selection | `video_ai.py:handle_adjust_features` |
| 13 | BeatSheet has trim timestamps | `BeatContract.trim_start/trim_end` |
| 14 | Timestamps in HH:MM:SS format | `TimelineSegment`, `BeatContract` |
| 15 | Top-half uses uploaded segments | `media_activities.py:generate_scene_images` |
| 16 | Production uses ApprovedPackage | No change - existing contract extended |
| 17 | Low confidence triggers clarify | `video_ai.py:handle_low_confidence` |
| 18 | Fallback to AI on trim failure | `media_activities.py:_extract_video_segment` |

---

## 8. Risks & Open Questions

### 8.1 Technical Risks

| Risk | Mitigation | Severity |
|------|------------|----------|
| Video analysis latency | Async processing, progress updates | Medium |
| OCR accuracy on mobile UIs | Multiple OCR backends, confidence thresholds | Medium |
| Keyframe extraction quality | Scene detection + fixed interval hybrid | Low |
| Storage costs for videos | Set retention policy, compress uploads | Low |
| FFmpeg dependency on workers | Containerize, use cloud transcoding fallback | Medium |

### 8.2 Open Questions

1. **Video storage**: Where should uploaded demo videos be stored?
   - Option A: Azure Blob Storage (existing)
   - Option B: Dedicated video storage service
   - **Recommendation**: Azure Blob with dedicated container

2. **OCR service**: Which OCR provider?
   - Option A: pytesseract (local, free)
   - Option B: Azure Computer Vision (cloud, paid)
   - Option C: Google Cloud Vision (cloud, paid)
   - **Recommendation**: Start with pytesseract, add cloud fallback

3. **Scene detection**: Library choice?
   - Option A: pyscenedetect (Python, robust)
   - Option B: FFmpeg scene filter (simpler)
   - **Recommendation**: pyscenedetect for accuracy

4. **Keyframe storage**: Store permanently or generate on-demand?
   - **Recommendation**: Store during analysis, delete after production complete

5. **Blur detection threshold**: What Laplacian variance is acceptable?
   - **Recommendation**: Start with 100.0 threshold, tune based on feedback

---

## 9. Recommended Implementation Order

### Phase 1: Foundation (Week 1)
1. ✅ Extend data contracts (`contracts.py`)
2. ✅ Add new Telegram steps (`step_config.py`)
3. ✅ Implement mode selection in skill (`video_ai.py`)
4. ✅ Create `VideoQualityGateService`
5. ✅ Add video upload handling

### Phase 2: Analysis Pipeline (Week 2)
6. ✅ Create `DemoVideoAnalysisService` scaffold
7. ✅ Implement keyframe extraction
8. ✅ Implement OCR pipeline
9. ✅ Implement timeline segmentation
10. ✅ Implement feature extraction

### Phase 3: Grounding & Preview (Week 3)
11. ✅ Extend `OpenClawService` for feature grounding
12. ✅ Implement preview generation
13. ✅ Implement preview confirm flow with timeout
14. ✅ Implement feature adjustment flow

### Phase 4: Integration (Week 4)
15. ✅ Extend `CreativeDirectorService` for demo evidence
16. ✅ Generate ConceptBrief from evidence
17. ✅ Generate BeatSheet with trim timestamps
18. ✅ Extend `ApprovedProductionPackageContract`

### Phase 5: Production Handoff (Week 5)
19. ✅ Extend `media_activities.py` for video segment extraction
20. ✅ Implement FFmpeg trim pipeline
21. ✅ End-to-end testing
22. ✅ Error handling & fallbacks

### Phase 6: Polish (Week 6)
23. ✅ Timeout handling & auto-confirm
24. ✅ Graceful degradation flows
25. ✅ Performance optimization
26. ✅ Documentation & cleanup

---

## Appendix A: Timestamp Format Reference

All timestamps in the system use the canonical format `HH:MM:SS` or `HH:MM:SS.mmm` for millisecond precision.

```python
def parse_timestamp(ts: str) -> float:
    """Parse HH:MM:SS or HH:MM:SS.mmm to seconds."""
    parts = ts.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds

def format_timestamp(seconds: float, include_ms: bool = False) -> str:
    """Format seconds to HH:MM:SS or HH:MM:SS.mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if include_ms:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    return f"{hours:02d}:{minutes:02d}:{int(secs):02d}"
```

---

## Appendix B: FFmpeg Commands Reference

```bash
# Extract keyframe at timestamp
ffmpeg -ss 00:01:23 -i input.mp4 -frames:v 1 keyframe.jpg

# Extract video segment
ffmpeg -ss 00:01:00 -to 00:01:30 -i input.mp4 -c copy segment.mp4

# Extract with re-encoding (for precise cuts)
ffmpeg -ss 00:01:00 -to 00:01:30 -i input.mp4 -c:v libx264 -c:a aac segment.mp4

# Get video metadata
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4

# Scene detection
ffmpeg -i input.mp4 -filter:v "select='gt(scene,0.3)',showinfo" -f null -
```

---

## Appendix C: Dependency Additions

```toml
# pyproject.toml additions

[project.dependencies]
# Existing...

# New for recorded_demo_video mode
pyscenedetect = "^0.6"
pytesseract = "^0.3"
opencv-python-headless = "^4.8"
Pillow = "^10.0"
```

```dockerfile
# Dockerfile additions

# Install tesseract for OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```
