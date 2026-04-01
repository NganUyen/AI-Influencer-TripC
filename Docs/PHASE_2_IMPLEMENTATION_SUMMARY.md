# Phase 2 Implementation Summary: Telegram Flow Extension for Recorded Demo Video Mode

**Implementation Date**: 2026-04-01  
**Scope**: Telegram flow extension only (no video analysis, no grounding, no production changes)

---

## Changes Made

### 1. **services/contracts.py** - Data Contract Extensions

**Changes:**
- Extended `ConceptBriefContract.creative_input_mode` from `Literal["idea_brief"]` to `Literal["idea_brief", "recorded_demo_video"]`
- Added optional fields to `ConceptBriefContract`:
  - `demo_video_telegram_file_id: Optional[str] = None`
  - `demo_video_asset_url: Optional[str] = None`

**Lines Changed**: 189-206

**Rationale**: These fields store the Telegram file ID and uploaded video URL for the recorded demo video mode, while keeping the contract backwards compatible with the existing idea_brief mode.

---

### 2. **services/step_config.py** - Telegram Step Definitions

**Changes:**
- Added new step `select_mode` at the beginning of the video-ai flow
  - Allows user to choose between "Idea Brief" and "Recorded Demo Video"
- Added new step `upload_demo_video`
  - Prompts user to upload demo video with requirements
- Added new step `collect_feature_emphasis`
  - Optional feature emphasis for recorded_demo_video mode (replaces required feature_focus)
- Reordered steps to support both modes:
  1. `select_mode` (NEW)
  2. `pick_persona`
  3. `upload_demo_video` (NEW - only for recorded_demo_video)
  4. `collect_idea_brief` (only for idea_brief)
  5. `collect_feature_focus` (only for idea_brief)
  6. `collect_feature_emphasis` (NEW - only for recorded_demo_video, optional)
  7. `choose_video_goal`
  8. `collect_audience`
  9. `collect_cta`
  10. `collect_reference_url`
  11. `choose_access_level`
  12. `confirm_concept`
  13. `confirm_beats`

**Lines Changed**: 215-279

**Rationale**: The new flow branches based on mode selection while preserving the original idea_brief flow unchanged.

---

### 3. **skills/video_ai.py** - Skill Handler Logic

**Changes:**

#### a. Field Mappings (Lines 22-42)
- Added `"demo_video_telegram_file_id": "upload_demo_video"` to `_FIELD_TO_STEP`
- Added new fields to `_RESETTABLE_FIELDS`:
  - `feature_emphasis`
  - `demo_video_telegram_file_id`
  - `demo_video_asset_url`

#### b. Session Initialization (Lines 54-68)
- Added default initialization: `session.collected["creative_input_mode"] = session.collected.get("creative_input_mode") or "idea_brief"`

#### c. Missing Step Logic (Lines 89-122)
- **Completely rewrote** `_missing_step()` to support mode-based routing:
  - Returns `"select_mode"` if mode not set
  - For `recorded_demo_video` mode:
    - Skips `idea_brief` and `feature_focus` (not required)
    - Requires `demo_video_telegram_file_id`
    - All other fields follow same order
  - For `idea_brief` mode:
    - Uses original logic (unchanged)

#### d. Restart Collection Logic (Lines 350-380)
- Updated `_restart_collection()` to restart at mode-appropriate step:
  - `upload_demo_video` for recorded_demo_video mode
  - `collect_idea_brief` for idea_brief mode

#### e. Execute Logic (Lines 451-599)
- Added mode initialization: `current.collected["creative_input_mode"] = current.collected.get("creative_input_mode") or "idea_brief"`
- **Added placeholder logic** for recorded_demo_video concept building:
  - If `creative_input_mode == "recorded_demo_video"`:
    - Fills in temporary values for `idea_brief` and `feature_focus` (required by CreativeDirectorService)
    - Uses `feature_emphasis` if available
    - **PLACEHOLDER**: Uses same CreativeDirectorService for now
    - Stores demo video metadata in concept
  - If `idea_brief` mode: uses original logic unchanged

**Lines Changed**: 22-42, 54-68, 89-122, 350-380, 451-599

**Rationale**: The skill now handles both modes while keeping the original idea_brief flow completely intact. Placeholders are clearly marked for future video analysis integration.

---

### 4. **agents/openclaw_telegram_skill_configs.py** - Skill Registry

**Changes:**
- Updated `video-ai` skill definition:
  - Changed description to mention both input modes
  - Updated `required_params`: removed `idea_brief` and `feature_focus` (now mode-dependent)
  - Added to `optional_params`:
    - `creative_input_mode`
    - `idea_brief` (now optional)
    - `feature_focus` (now optional)
    - `demo_video_telegram_file_id`
    - `demo_video_asset_url`
    - `feature_emphasis`
  - Updated `input_contract` to describe both modes
  - Added new steps to `steps` array: `select_mode`, `upload_demo_video`, `collect_feature_emphasis`
  - Updated `session_shape` with new fields
  - Changed initial `step_key` from `"pick_persona"` to `"select_mode"`

**Lines Changed**: 353-438

**Rationale**: The skill registry now accurately reflects the dual-mode capability and updated session state.

---

## Placeholders & Future Work

### Clearly Marked Placeholders

1. **video_ai.py, line ~485-495**: Concept building for recorded_demo_video mode
   ```python
   # PLACEHOLDER: For now, build concept using the same method
   # In future phases, this will use demo video analysis results
   ```
   - Current behavior: Uses temporary strings for `idea_brief` and `feature_focus`
   - Future: Will use `RecordedDemoEvidenceContract` from video analysis service

2. **step_config.py, line 240-247**: Video upload step
   - Current: Defines UI prompt only
   - Future: Will integrate with quality gate and video analysis pipeline

3. **step_config.py, line 248-253**: Feature emphasis step
   - Current: Collects optional text input
   - Future: May integrate with preview confirmation flow after analysis

### Not Implemented (Out of Scope for Phase 2)

- ❌ Video quality gate service
- ❌ Demo video analysis service
- ❌ Feature grounding via OpenClaw
- ❌ Preview confirmation with timeout
- ❌ Video segment extraction for production
- ❌ Actual video file upload/storage handling
- ❌ Beat timestamp generation from video segments

---

## Backwards Compatibility

✅ **100% backwards compatible** with existing idea_brief flow:
- If `creative_input_mode` is not set, defaults to `"idea_brief"`
- Original step order preserved for idea_brief mode
- All existing required parameters remain required for idea_brief
- No changes to `CreativeDirectorService` behavior for idea_brief
- No changes to production workflow
- Existing sessions will continue to work

---

## Files Changed

| File | Lines Changed | Change Type |
|------|---------------|-------------|
| `services/contracts.py` | 189-206 | Extended |
| `services/step_config.py` | 215-279 | Extended |
| `skills/video_ai.py` | 22-42, 54-68, 89-122, 350-380, 451-599 | Major Extension |
| `agents/openclaw_telegram_skill_configs.py` | 353-438 | Extended |

**Total**: 4 files modified, 0 files added

---

## Manual Test Checklist

### Test Environment Setup
- [ ] Python services running locally or in dev environment
- [ ] Telegram bot connected to test instance
- [ ] At least one ready persona available

---

### Test Case 1: Mode Selection

**Objective**: Verify mode selection step appears first

1. [ ] Start new video-ai skill session via Telegram
2. [ ] **Expected**: Bot presents mode selection with two options:
   - "💡 Idea Brief"
   - "📹 Recorded Demo Video"
3. [ ] **Verify**: Both buttons are clickable
4. [ ] **Verify**: No other steps shown yet

---

### Test Case 2: Idea Brief Mode (Regression Test)

**Objective**: Ensure existing idea_brief flow works unchanged

1. [ ] Select "💡 Idea Brief" from mode selection
2. [ ] **Expected**: Bot asks for persona selection
3. [ ] Select a ready persona
4. [ ] **Expected**: Bot asks for idea_brief
5. [ ] Enter: "Showcasing the trip planning feature"
6. [ ] **Expected**: Bot asks for feature_focus
7. [ ] Enter: "Group trip booking"
8. [ ] **Expected**: Bot asks for video_goal
9. [ ] Select: "Feature Demo"
10. [ ] **Expected**: Bot asks for audience
11. [ ] Enter: "Vietnamese travelers aged 20-35"
12. [ ] **Expected**: Bot asks for CTA
13. [ ] Enter: "Book your trip at tripc.vn"
14. [ ] **Expected**: Bot asks for reference_url
15. [ ] Enter: "https://tripc.vn/features/group-trips"
16. [ ] **Expected**: Bot asks for access_level
17. [ ] Select: "Public Page Only"
18. [ ] **Expected**: Bot generates concept brief and shows preview
19. [ ] Approve concept
20. [ ] **Expected**: Bot generates beat sheet and shows preview
21. [ ] Approve beats
22. [ ] **Expected**: Production workflow starts

**Success Criteria**: All steps execute in original order, no errors, workflow starts successfully

---

### Test Case 3: Recorded Demo Video Mode - Complete Flow

**Objective**: Verify new recorded_demo_video flow

1. [ ] Start new video-ai skill session
2. [ ] Select "📹 Recorded Demo Video" from mode selection
3. [ ] **Expected**: Bot asks for persona selection
4. [ ] Select a ready persona
5. [ ] **Expected**: Bot asks for demo video upload with requirements message
6. [ ] **Verify**: Message includes:
   - Duration requirement: 30s to 3 min
   - Resolution: 720p or higher
   - Format: MP4, MOV, or WebM
7. [ ] Upload a video file (or any file as placeholder)
8. [ ] **Expected**: Bot stores file_id and proceeds to next step
9. [ ] **Expected**: Bot asks for video_goal (skips idea_brief and feature_focus)
10. [ ] Select: "Walkthrough"
11. [ ] **Expected**: Bot asks for audience
12. [ ] Enter: "First-time app users"
13. [ ] **Expected**: Bot asks for CTA
14. [ ] Enter: "Download the app today"
15. [ ] **Expected**: Bot asks for reference_url
16. [ ] Enter: "https://tripc.vn"
17. [ ] **Expected**: Bot asks for access_level
18. [ ] Select: "Public Page Only"
19. [ ] **Expected**: Bot generates concept brief (with placeholder values)
20. [ ] **Verify**: Concept brief contains:
    - `creative_input_mode: "recorded_demo_video"`
    - `demo_video_telegram_file_id` is populated
21. [ ] Approve concept
22. [ ] **Expected**: Bot generates beat sheet
23. [ ] Approve beats
24. [ ] **Expected**: Production workflow starts

**Success Criteria**: 
- Flow skips idea_brief and feature_focus
- demo_video_telegram_file_id is stored in session
- Concept brief is generated with placeholder values
- Workflow starts successfully

---

### Test Case 4: Optional Feature Emphasis

**Objective**: Verify feature_emphasis is optional

1. [ ] Start new video-ai session
2. [ ] Select "📹 Recorded Demo Video"
3. [ ] Select persona
4. [ ] Upload video
5. [ ] **Expected**: Bot may ask for optional feature_emphasis
6. [ ] Send: "/skip" or leave empty
7. [ ] **Expected**: Bot proceeds to video_goal without error
8. [ ] Complete rest of flow
9. [ ] **Expected**: Concept generated successfully without feature_emphasis

**Success Criteria**: Flow completes without requiring feature_emphasis

---

### Test Case 5: Session Persistence

**Objective**: Verify session state is preserved across restarts

1. [ ] Start recorded_demo_video flow
2. [ ] Complete steps up to audience collection
3. [ ] Stop bot or simulate disconnect
4. [ ] Restart bot
5. [ ] Resume session
6. [ ] **Expected**: Bot remembers:
   - Selected mode (recorded_demo_video)
   - Uploaded video file_id
   - All collected fields
7. [ ] **Expected**: Bot asks for next missing field (CTA)
8. [ ] Complete flow
9. [ ] **Expected**: Workflow starts with all data intact

**Success Criteria**: Session state preserved, no data loss

---

### Test Case 6: Edit/Regenerate Actions

**Objective**: Verify edit/regenerate restarts at correct step

1. [ ] Complete recorded_demo_video flow to concept preview
2. [ ] Select "Edit" instead of "Approve"
3. [ ] **Expected**: Bot restarts at `upload_demo_video` step (not idea_brief)
4. [ ] Upload new video
5. [ ] Complete flow
6. [ ] **Expected**: New video is used in concept

**Repeat for idea_brief mode:**
7. [ ] Complete idea_brief flow to concept preview
8. [ ] Select "Edit"
9. [ ] **Expected**: Bot restarts at `collect_idea_brief` step
10. [ ] Complete flow

**Success Criteria**: Restart step matches selected mode

---

### Test Case 7: Field Validation

**Objective**: Ensure required fields are enforced per mode

**For recorded_demo_video mode:**
1. [ ] Start recorded_demo_video flow
2. [ ] Try to skip persona selection
3. [ ] **Expected**: Error or re-prompt
4. [ ] Try to skip video upload
5. [ ] **Expected**: Error or re-prompt
6. [ ] Try to skip video_goal
7. [ ] **Expected**: Error or re-prompt

**For idea_brief mode:**
1. [ ] Start idea_brief flow
2. [ ] Try to skip idea_brief field
3. [ ] **Expected**: Error or re-prompt
4. [ ] Try to skip feature_focus
5. [ ] **Expected**: Error or re-prompt

**Success Criteria**: Required fields are enforced, optional fields are skippable

---

### Test Case 8: Contract Serialization

**Objective**: Verify ConceptBriefContract handles both modes

1. [ ] Complete recorded_demo_video flow
2. [ ] In backend logs, inspect concept_brief artifact
3. [ ] **Verify** JSON contains:
   ```json
   {
     "creative_input_mode": "recorded_demo_video",
     "demo_video_telegram_file_id": "<file_id>",
     "demo_video_asset_url": null,
     "feature_focus": "Feature highlights from demo video",
     "idea_brief": "Demo video showcase",
     ...
   }
   ```
4. [ ] Complete idea_brief flow
5. [ ] In backend logs, inspect concept_brief artifact
6. [ ] **Verify** JSON contains:
   ```json
   {
     "creative_input_mode": "idea_brief",
     "demo_video_telegram_file_id": null,
     "demo_video_asset_url": null,
     "feature_focus": "<user_input>",
     "idea_brief": "<user_input>",
     ...
   }
   ```

**Success Criteria**: Contracts serialize correctly for both modes

---

### Test Case 9: Error Handling

**Objective**: Verify graceful error handling

1. [ ] Start recorded_demo_video flow
2. [ ] Upload video, complete all steps
3. [ ] At concept generation, if error occurs:
4. [ ] **Expected**: Bot shows retryable error message
5. [ ] Select "Regenerate"
6. [ ] **Expected**: Bot retries concept generation
7. [ ] **Verify**: Session state preserved (video file_id intact)

**Success Criteria**: Errors are recoverable, session not lost

---

### Test Case 10: Production Workflow Integration

**Objective**: Verify approved package reaches production correctly

1. [ ] Complete recorded_demo_video flow, approve all steps
2. [ ] **Expected**: Production workflow starts
3. [ ] In workflow logs, verify payload contains:
   - `approved_package.concept_brief.creative_input_mode == "recorded_demo_video"`
   - `approved_package.concept_brief.demo_video_telegram_file_id` is populated
4. [ ] **Expected**: Workflow executes without errors (even though video analysis is placeholder)

**Success Criteria**: Production workflow accepts recorded_demo_video packages

---

## Expected Behavior Summary

### For Recorded Demo Video Mode:

**Input Collection Order**:
1. Mode selection → "Recorded Demo Video"
2. Persona selection
3. Demo video upload
4. Video goal
5. Audience
6. CTA
7. Reference URL
8. Access level
9. (Optional: Feature emphasis at any point)

**Not Asked**:
- ❌ Idea brief (skipped)
- ❌ Feature focus (replaced by optional feature_emphasis)

**Output**:
- ConceptBrief with `creative_input_mode: "recorded_demo_video"`
- Placeholder values for `idea_brief` and `feature_focus`
- Demo video metadata stored

---

### For Idea Brief Mode (Unchanged):

**Input Collection Order**:
1. Mode selection → "Idea Brief"
2. Persona selection
3. Idea brief (required)
4. Feature focus (required)
5. Video goal
6. Audience
7. CTA
8. Reference URL
9. Access level

**Output**:
- ConceptBrief with `creative_input_mode: "idea_brief"`
- User-provided values for all fields

---

## Known Limitations (Phase 2)

1. **No Video Processing**: Uploaded videos are stored as file_id only, not analyzed
2. **Placeholder Concept Generation**: Uses same CreativeDirectorService logic for both modes
3. **No Quality Gate**: No validation of video duration, resolution, or blur
4. **No Feature Extraction**: Feature emphasis is user-provided text, not extracted from video
5. **No Preview Step**: No analysis preview confirmation step
6. **No Segment Timestamps**: BeatSheet does not contain trim_start/trim_end yet
7. **No Grounding**: No OpenClaw verification of features against reference URL

These limitations are **intentional** for Phase 2 and will be addressed in subsequent phases.

---

## Next Steps (Future Phases)

**Phase 3**: Video Analysis Integration
- Implement VideoQualityGateService
- Implement DemoVideoAnalysisService
- Replace placeholder concept generation

**Phase 4**: Grounding & Preview
- Extend OpenClawService for feature grounding
- Implement preview confirmation flow with timeout

**Phase 5**: Production Integration
- Extend BeatContract with trim timestamps
- Implement video segment extraction in media_activities
- Update generate_scene_images to handle uploaded_video_segment

---

## Rollback Plan

If issues arise, rollback by reverting these 4 files to previous versions:
1. `services/contracts.py`
2. `services/step_config.py`
3. `skills/video_ai.py`
4. `agents/openclaw_telegram_skill_configs.py`

All changes are additive and backwards compatible, so partial rollback is also safe.

---

## Summary

✅ **Completed**: Phase 2 Telegram flow extension for recorded_demo_video mode  
✅ **Backwards Compatible**: Original idea_brief flow unchanged  
✅ **State Ready**: Session state structure supports future video analysis integration  
✅ **Placeholders Marked**: Clear separation between implemented and future work  

The implementation provides a complete user-facing flow for recorded demo video mode while preserving all existing functionality. Future phases can integrate video analysis without modifying the Telegram flow logic.
