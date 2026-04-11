# VIDEO CREATION V2 ARCHITECTURE

**Version:** 2.0  
**Status:** ✅ ACTIVE (Post-Refactor)  
**Last Updated:** 2026-04-09  
**Reviewed By:** Senior Backend Architect + QA Engineer  

---

## 1. OVERVIEW: What Changed V1 → V2

### V1 Architecture (Legacy)

```
User Input
  ├─ /start → menu
  ├─ /create_video → video-planner skill
  │   └─ Planner handles: objective, URL, persona, execution_mode
  │   └─ Returns: approved_package
  │
  └─ Callback from planner → video-ai skill (SEPARATE ENTRY)
      └─ video-ai starts fresh planning
      └─ DUPLICATE: mode selection step exists
      └─ DUPLICATE: plan confirmation logic exists
```

**Problems:**
- ❌ Two execution paths (video-planner and video-ai)
- ❌ Duplicated planner logic in both skills
- ❌ User asked twice to select mode (once in planner, once in video-ai)
- ❌ Workflow started from TWO different places
- ❌ Inconsistent state seeding between skills

---

### V2 Architecture (Current)

```
User Input
  ├─ /start → menu only (no skill)
  ├─ /media → menu only (no skill)
  │
  └─ /create_video (or text "video") → video-ai skill (ONLY ENTRY)
      ├─ Collect: objective, target_url, persona, execution_mode
      ├─ Confirm: plan (execution_mode → creative_input_mode mapping)
      │   └─ creative_input_mode AUTO-SET (NOT asked)
      │   └─ manual_mobile → recorded_demo_video
      │   └─ others → idea_brief
      │
      ├─ Pre-production path (based on mode):
      │   ├─ recorded_demo_video:
      │   │   ├─ Upload demo video
      │   │   ├─ Run Phase 4: Video analysis
      │   │   ├─ Run Phase 5: Feature grounding
      │   │   ├─ Run IdeaResolver
      │   │   └─ Concept → Beat → Package
      │   │
      │   └─ idea_brief:
      │       ├─ Collect: idea_brief, feature_focus
      │       ├─ CreativeDirector: build concept
      │       └─ Beat → Package
      │
      └─ Package ready:
          ├─ Check credential handoff (if needed)
          ├─ POST /api/workflows/start-video (ONLY HERE!)
          └─ Return workflow_id to user
```

**Improvements:**
- ✅ Single execution path (video-ai only)
- ✅ Planner logic embedded in video-ai
- ✅ No duplicate mode selection
- ✅ Creative_input_mode auto-mapped from execution_mode
- ✅ Workflow started from ONE place (video-ai._package_ready_result)
- ✅ Clean state seeding after plan confirmation

---

## 2. FINAL FLOW DIAGRAM

### Complete User Journey

```
START: /create_video or "video" text
├─ Video-AI Skill Initialized
│  └─ plan_confirmed = False
│  └─ creative_input_mode = None (will be auto-set)
│
├─ PHASE 1: PLANNING (new flow)
│  ├─ User provides objective
│  ├─ User provides target URL
│  ├─ WebsiteReviewService analyzes URL
│  ├─ User selects persona
│  ├─ User selects execution_mode
│  │  ├─ Autonomous Screen Recording
│  │  ├─ Authenticated PC Recording
│  │  └─ Manual Mobile Recording
│  │
│  └─ User confirms plan
│     ├─ _seed_preproduction_from_plan() called
│     ├─ execution_mode → creative_input_mode mapping
│     │  ├─ manual_mobile_recording → recorded_demo_video ✅
│     │  └─ others → idea_brief ✅
│     └─ plan_confirmed = True
│
├─ PHASE 2a: PRE-PRODUCTION (Recorded Demo Path)
│  [IF creative_input_mode == recorded_demo_video]
│  ├─ User uploads demo video
│  ├─ VideoQualityGateService validation ✅
│  ├─ MediaStorageService storage ✅
│  │
│  ├─ PHASE 4: Demo Video Analysis
│  │ ├─ DemoVideoAnalyzerService analyzes frames
│  │ ├─ FrameUnderstandingService processes visuals
│  │ └─ Evidence contract built
│  │
│  ├─ PHASE 5: Feature Grounding
│  │ ├─ OfficialSourceResolverService resolves website
│  │ ├─ OfficialFeatureCatalogService extracts catalog
│  │ ├─ DemoFeatureGroundingService grounds features
│  │ └─ IdeaResolverService determines main idea
│  │
│  ├─ User reviews proposed main idea
│  │ ├─ Option 1: Approve → proceed to ConceptBrief
│  │ ├─ Option 2: Pick alternate feature
│  │ ├─ Option 3: Rewrite main idea
│  │ └─ Option 4: Re-upload video
│  │
│  └─ Concept generation (from demo evidence)
│
├─ PHASE 2b: PRE-PRODUCTION (Idea Brief Path)
│  [IF creative_input_mode == idea_brief]
│  ├─ User provides idea_brief
│  ├─ User provides feature_focus
│  ├─ User provides video_goal
│  ├─ User provides audience
│  ├─ User provides CTA
│  ├─ User provides reference_url (optional)
│  └─ User provides access_level (or auto-set from plan)
│
├─ PHASE 3: CONCEPT & BEAT GENERATION
│ ├─ All paths converge here
│ ├─ CreativeDirectorService builds ConceptBrief
│ ├─ User reviews & approves concept
│ ├─ BeatSheetService builds beat sheet
│ ├─ User reviews & approves beats
│ └─ ApprovedProductionPackageContract created
│
├─ PHASE 4: HANDOFF (if needed)
│ [IF execution_mode == authenticated_pc_recording]
│ ├─ VideoCaptureHandoffService creates token
│ ├─ User receives handoff_url (opens in dashboard)
│ ├─ User authenticates to target website
│ ├─ User completes PC setup in dashboard
│ ├─ Returns to Telegram (session preserved!)
│ └─ Resumes with "Retry Start" button
│
├─ PHASE 5: WORKFLOW START ✅
│ ├─ _package_ready_result() ONLY CALLER
│ ├─ Builds production_payload:
│ │  ├─ persona_id
│ │  ├─ topic (from idea_brief or demo evidence)
│ │  ├─ approved_package (ConceptBrief + BeatSheet)
│ │  ├─ execution_mode (persisted)
│ │  └─ talking_head_optional (from persona readiness)
│ │
│ ├─ POST /api/workflows/start-video (ONLY HERE!)
│ ├─ Response: workflow_id
│ └─ Return to user with workflow status
│
└─ END: User sees workflow_id and status message
   🎉 "Production workflow started! Workflow ID: xyz..."
```

### Decision Tree by Execution Mode

```
execution_mode selection
│
├─ Autonomous Screen Recording
│  ├─ creative_input_mode = "idea_brief"
│  ├─ Path: idea_brief → feature_focus → pre-prod fields
│  └─ Workflow: No handoff needed, direct start
│
├─ Authenticated PC Recording
│  ├─ creative_input_mode = "idea_brief"
│  ├─ Path: idea_brief → feature_focus → pre-prod fields
│  └─ Workflow: Requires handoff, blocks on completion
│
└─ Manual Mobile Recording
   ├─ creative_input_mode = "recorded_demo_video"
   ├─ Path: upload → analysis → preview → concept
   └─ Workflow: Direct start after package approval
```

---

## 3. KEY DECISIONS

### 3.1 Why Merge Planner into video-ai?

**Decision:** Consolidate video-planner logic into video-ai skill.

**Rationale:**
- **Reduce Duplication:** Both skills had identical planning logic
- **Single Execution Path:** One skill means one point of entry, one point of exit
- **Cleaner State:** No state handoff between skills
- **Easier Testing:** Single skill to test instead of two
- **User Experience:** No jarring context switches between skills
- **Maintenance:** One place to fix bugs, not two

**Impact:**
- ✅ Reduced lines of duplicate code
- ✅ Reduced execution paths from 2 to 1
- ✅ Simplified session state management

---

### 3.2 Why Preserve approved_package?

**Decision:** Continue using ApprovedProductionPackageContract as the workflow payload.

**Rationale:**
- **Type Safety:** Contract validates all required fields
- **Versioning:** Future workflow changes stay decoupled
- **Audit Trail:** Package persisted, immutable record of what was approved
- **Workflow Reproducibility:** If workflow fails, we have exact approved state

**Implementation:**
```python
production_payload = {
    "approved_package": package.model_dump(mode="json"),  # ← Versioned structure
    "persona_id": persona_id,                             # ← Additional context
    "execution_mode": execution_mode,                     # ← Mode for video gen
    ...
}
```

---

### 3.3 Why Remove select_mode?

**Decision:** Remove the `select_mode` step that asked user to choose creative_input_mode.

**Rationale:**
- **Redundant Prompt:** User already chose execution_mode at confirm_plan
- **Auto-Derivable:** creative_input_mode can be determined from execution_mode
- **UX Improvement:** One less step = faster workflow
- **Logic Clarity:** Decision tree is deterministic, not user choice

**Derivation:**
```python
session.collected["creative_input_mode"] = (
    "recorded_demo_video"      # Only if user selected manual_mobile_recording
    if execution_mode == "manual_mobile_recording"
    else "idea_brief"          # For all other execution modes
)
```

**Result:**
- ✅ Reduced user prompts from N+1 to N
- ✅ Removed ambiguous step (user doesn't need to understand modes)
- ✅ Automated decision improves consistency

---

### 3.4 Why video-ai is Single Execution Engine

**Decision:** Only video-ai skill can trigger `/api/workflows/start-video`.

**Rationale:**
- **One Source of Truth:** All video creation goes through one path
- **Easier Testing:** Single entry point to test and debug
- **Consistent Payload:** All workflows receive same well-formed payload
- **Audit Trail:** All workflow starts logged from same method
- **Security:** Easier to apply permissions/validation at one point

**Enforcement:**
```python
# video_ai.py:_package_ready_result() at line 722-726
response = await http_client.post(
    cls._build_url(backend_url, "/api/workflows/start-video"),  # ← ONLY HERE
    json=production_payload,
    headers=cls._auth_headers(),
)
```

**No other code path can trigger this endpoint:**
- ❌ video-planner doesn't call it (unreachable)
- ❌ Other skills don't call it
- ❌ telegram_webhook doesn't call it
- ❌ skill_dispatcher doesn't call it

---

## 4. MODE MAPPING

### 4.1 Mapping Table

| User Selection | Execution Mode | Auto-Determined Mode | Flow |
|---|---|---|---|
| "Autonomous Screen Recording" | `autonomous_screen_recording` | `idea_brief` | Collect idea → feature focus → pre-prod |
| "Authenticated PC Recording" | `authenticated_pc_recording` | `idea_brief` | Collect idea → (handoff) → pre-prod |
| "Manual Mobile Recording" | `manual_mobile_recording` | `recorded_demo_video` | Upload video → analysis → preview → concept |

### 4.2 Where Mapping Happens

**Location:** `video_ai.py:_seed_preproduction_from_plan()` (line 250-254)

**When:** After user confirms plan (line 1155)

**Process:**
```python
# User just clicked "Confirm Plan" button
decision = session.collected.get("plan_decision")
if decision == "confirm":
    cls._seed_preproduction_from_plan(current)  # ← MAPPING HAPPENS HERE
    # Inside _seed_preproduction_from_plan():
    #   plan = cls._build_or_refresh_review_plan(session, confirmed=True)
    #   execution_mode = plan.execution_mode  # ← GET execution_mode from plan
    #   session.collected["creative_input_mode"] = (
    #       "recorded_demo_video" if execution_mode == "manual_mobile_recording"
    #       else "idea_brief"
    #   )  # ← SET creative_input_mode based on execution_mode
    #   session.artifacts["plan_confirmed"] = True  # ← LOCK the plan
    
    current.step_key = None  # ← Reset step to re-evaluate with new mode
    return await cls.execute(current, backend_url, http_client)  # ← Continue with mapped mode
```

### 4.3 Mode Usage in Pre-Production

**recorded_demo_video mode:**
```python
if creative_input_mode == "recorded_demo_video":
    # Check: demo_video_telegram_file_id AND demo_video_asset_url
    if missing: return "upload_demo_video"  # ← User uploads
    # Skip: idea_brief, feature_focus (not needed)
    # Check: video_goal, audience, cta, reference_url, access_level
    if missing: return "choose_video_goal"  # ← Standard pre-prod fields
    # Phase 4-5: Demo analysis and grounding
    if not "demo_preview_confirmed": return "demo_preview_confirm"  # ← Preview
    return None  # ← Ready for concept generation
```

**idea_brief mode:**
```python
if creative_input_mode == "idea_brief":
    # Check: idea_brief (populated from plan objective)
    if missing: return "collect_idea_brief"  # ← User inputs
    # Check: feature_focus
    if missing: return "collect_feature_focus"  # ← User inputs
    # Check: remaining required params
    missing = cls._missing_required_params(session)
    if missing: return next_field(missing)  # ← Standard pre-prod flow
    return None  # ← Ready for concept generation
```

---

## 5. EXECUTION OWNERSHIP

### 5.1 Workflow Start Responsibility

**ONLY video-ai skill can start workflows.**

```
User Request
  ↓
Entry Point Router (telegram_webhook.py)
  ├─ /start → TelegramRenderer.render_menu() (NO WORKFLOW)
  ├─ /media → TelegramRenderer.render_menu() (NO WORKFLOW)
  └─ /create_video → SkillDispatcher.start_skill("video-ai")
                      ↓
                      VideoAISkill.initial_session()
                      VideoAISkill.execute()
                      ├─ Collect planning fields
                      ├─ Generate pre-production
                      ├─ Approve package
                      └─ _package_ready_result()
                         ├─ Build production_payload
                         └─ POST /api/workflows/start-video ✅ (ONLY HERE)
                            └─ Workflow executes in Temporal
```

### 5.2 Workflow Payload Structure

**Source:** `video_ai.py:_package_ready_result()` at line 707-718

```python
production_payload = {
    "persona_id": persona_id,                      # Who is speaking
    "topic": topic,                                 # From idea_brief (or demo evidence)
    "tone": "natural",                              # Fixed
    "platform": platform,                           # e.g., "tiktok"
    "telegram_chat_id": telegram_chat_id,           # For async notifications
    "user_id": None,                                # Legacy, unused
    "owner_key": f"telegram:{telegram_chat_id}",    # For billing/scoping
    "talking_head_optional": talking_head_optional, # If persona lacks HeyGen avatar
    "approved_package": package.model_dump(mode="json"),  # ← Full pre-production approved
    "execution_mode": execution_mode,               # For video gen strategy
}
```

### 5.3 What Workflow Does With Payload

**Execution modes affect how workflow processes:**

| execution_mode | Workflow Behavior |
|---|---|
| `autonomous_screen_recording` | Performs autonomous screen recording of website, no user credential needed |
| `authenticated_pc_recording` | Uses provided credentials to authenticate, then records PC screen |
| `manual_mobile_recording` | Uses approved demo video + creative strategy to generate new video |

---

## 6. REMOVED / DEPRECATED

### 6.1 video-planner Skill

**Status:** ❌ **DEPRECATED** (unreachable, kept for backward compatibility)

**Location:** `skills/video_planner.py`

**Why Kept:**
- ✅ Registered in SKILL_REGISTRY (harmless, not used)
- ✅ Can be removed in next cleanup sprint
- ✅ No active references in production flow

**How Removed from Routing:**
```python
# telegram_webhook.py:711-712 (Explicit filter)
if skill_name == "video-planner":
    continue  # ← Removes from OpenClaw routing
```

**Cleanup (future):**
```
[ ] Delete skills/video_planner.py
[ ] Remove from skills/__init__.py imports
[ ] Remove from step_config.py entries (all video-planner steps)
[ ] Remove from openclaw_telegram_skill_configs.py
```

---

### 6.2 select_mode Step

**Status:** ❌ **REMOVED**

**What It Was:**
```python
"select_mode": {
    "input_type": "inline_keyboard",
    "field": "creative_input_mode",
    "prompt_text": "🎬 How would you like to create your video?",
    "options": [
        ("💡 Idea Brief", "idea_brief"),
        ("📹 Recorded Demo Video", "recorded_demo_video"),
    ],
}
```

**Why Removed:**
- ❌ Duplicate of execution_mode choice
- ❌ Can be auto-derived, no user decision needed
- ❌ UX friction (one less prompt)

**Replaced By:**
```python
# Automatic mapping in _seed_preproduction_from_plan()
session.collected["creative_input_mode"] = (
    "recorded_demo_video" if execution_mode == "manual_mobile_recording"
    else "idea_brief"
)
```

---

### 6.3 Direct Planner Workflow Execution

**Status:** ❌ **REMOVED**

**What It Was:**
- video-planner skill could directly call workflow API
- Allowed two execution paths to workflow

**Why Removed:**
- ❌ Caused duplicate workflow starts
- ❌ Made state management harder
- ❌ Increased attack surface (multiple entry points to API)

**Now:**
- ✅ Only video-ai calls `/api/workflows/start-video`
- ✅ All workflow starts go through one code path
- ✅ Easier to audit, test, and secure

---

## 7. SAFETY NOTES

### 7.1 APIs Unchanged

**Workflow API Unchanged:**
```
POST /api/workflows/start-video
Input: Same payload structure (persona_id, topic, approved_package, etc.)
Output: Same workflow_id + status
```

**No API versioning needed.** Payload structure preserved.

---

### 7.2 Workflow Engine Unchanged

**Temporal workflows execute identically:**
- ✅ Same workflow logic
- ✅ Same video generation pipeline
- ✅ Same output format
- ✅ Same error handling

**Refactor is transparent to workflow layer.**

---

### 7.3 Backward Compatibility

**Session Handling:**
- ✅ Existing sessions with `creative_input_mode` already set are preserved
- ✅ Legacy sessions auto-detect mode from collected fields
- ✅ Default fallback: `idea_brief` (safe default)

**Pre-Approved Packages:**
- ✅ Already-approved packages still work
- ✅ Package schema unchanged
- ✅ Workflow accepts same payload

**Ongoing Workflows:**
- ✅ Workflows in progress are unaffected
- ✅ Can resume sessions from previous version
- ✅ No data migration needed

---

### 7.4 Edge Cases Handled

**User closes Telegram mid-flow:**
- ✅ Session saved in TelegramSkillSessionStore
- ✅ User can resume (click "Open Studio" or send /media)
- ✅ Mode preserved from last state

**Credential Handoff Timeout:**
- ✅ Session saved with pending credential_handoff
- ✅ User can retry without re-entering planning
- ✅ Package approved state cached

**Network Failure During Workflow Start:**
- ✅ Workflow start is atomic (Temporal sees it or doesn't)
- ✅ On retry, checks for active_workflow_id
- ✅ No duplicate workflows created

**User Changes Execution Mode:**
- ✅ At confirm_plan: user can click "Change Mode"
- ✅ Resets execution_mode and credential_handoff
- ✅ Re-enters planning flow

---

## 8. VERIFICATION CHECKLIST

### Pre-Deployment Verification

- ✅ All entry points route to video-ai
- ✅ /start is menu-only (no skill)
- ✅ /media is menu-only (no skill)
- ✅ video-planner unreachable from UI
- ✅ select_mode step removed from config
- ✅ creative_input_mode never asked from user
- ✅ Workflow started only from video-ai
- ✅ Mode mapping tested (all 3 execution modes)
- ✅ No infinite loops in _missing_step()
- ✅ Session fields initialized after confirm_plan
- ✅ Test fixtures updated (5 files)
- ✅ Documentation complete

### Production Monitoring

**Metrics to track:**
- Workflow start success rate (should be 100%)
- Mode distribution (manual_mobile vs idea_brief ratio)
- User drop-off after confirm_plan step
- Handoff completion rate (authenticated_pc mode)

---

## 9. SUMMARY

### What Changed
```
V1: Two execution paths (video-planner + video-ai)
    Duplicate prompts (mode asked twice)
    Inconsistent state seeding

V2: One execution path (video-ai only)
    Auto-determined mode (no duplication)
    Clean state seeding after plan confirmation
```

### How It Works Now
```
/create_video → video-ai skill
             → Planning phase (objective, URL, persona, execution_mode)
             → Confirm plan (execution_mode → creative_input_mode auto-mapped)
             → Pre-production (based on auto-mapped mode)
             ├─ recorded_demo_video: upload → analysis → preview → concept
             └─ idea_brief: idea → feature focus → concept
             → Concept + Beat approval
             → Workflow start (from video-ai ONLY)
```

### Key Improvements
- ✅ Single execution engine (video-ai)
- ✅ No duplicate prompts (mode auto-determined)
- ✅ Clean architecture (one entry → one exit)
- ✅ Easier to test and maintain
- ✅ Backward compatible (existing sessions work)

---

**Status:** ✅ **PRODUCTION READY**

For QA verification details, see: `VIDEO_CREATION_QA_VERIFICATION_REPORT.md`
