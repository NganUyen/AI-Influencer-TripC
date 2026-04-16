# QUICK REFERENCE - ĐÃ CÓ vs CHƯA CÓ

## ✅ ĐANG CÓ (Existing & Functional)

### Backend APIs (Ready to Use)
- ✅ /api/customer/personas/* - Full CRUD
- ✅ /api/customer/review-engine/source/validate - Extract URL metadata
- ✅ /api/customer/review-engine/jobs - Generate scripts for personas

### Backend Services (Ready to Use)
- ✅ PersonaRegistryService - Persona management
- ✅ WebsiteReviewService - URL metadata extraction
- ✅ ScriptService - Script generation from persona + URL
- ✅ ShortVideoWorkflow - Video creation orchestration
- ✅ Media generation (audio, images, video)

### Database Tables (Exist)
- ✅ personas - Basic persona data
- ✅ social_accounts - Channel connections (FK to personas)
- ✅ content - Video/media items
- ✅ workflows - Workflow tracking

### Frontend Components (Partial)
- ✅ PersonasTab - Persona list & selection
- ✅ LiveFeedTab - Step 1, 2, 3 UI scaffolding (mock data)
- ✅ customer-dashboard.tsx - Main layout

---

## ❌ CHƯA CÓ (Need to Build)

### Backend Endpoints (NEED TO CREATE)
```
❌ POST /api/customer/review-engine/plans - Store plans
❌ PATCH /api/customer/review-engine/plans/{plan_id} - Update plan
❌ GET /api/customer/review-engine/plans/{plan_id} - Retrieve plan
❌ DELETE /api/customer/review-engine/plans/{plan_id} - Delete plan
❌ POST /api/customer/review-engine/plans/{plan_id}/approve - Approve & workflow
❌ POST /api/customer/review-engine/publish - Batch publish
❌ GET /api/customer/review-engine/publish-jobs/{job_id} - Publish status
```

### Database Tables (NEED TO CREATE)
```
❌ video_render_plans
   Fields: plan_id, persona_id, script_text, scenes_data, status, 
           workflow_id, video_url, publish_settings, ...

❌ Modify personas table
   Add: gender, channel_configs
```

### Frontend Components (NEED TO CREATE)
```
❌ PlanReviewStep - Show & manage all generated plans
❌ PlanCard - Expandable plan display card
❌ PlanEditModal - Edit script & scenes
❌ PublishingTab - New tab for publishing settings & batch publish
❌ Update PersonasTab - Add channel config UI (TikTok, YouTube, etc)
```

### Frontend Types (NEED TO CREATE)
```
❌ ScriptPlan interface
❌ VideoScene interface
❌ PersonaChannelConfig interface
❌ Zustand store: useVideoPlanningStore
```

---

## 🎯 NEW FLOW - 4 TABS + 3 STEPS

### Tab 1: PERSONAS (Enhanced)
```
├─ Left: List personas (existing)
└─ Right: When selected
   ├─ Persona info (existing)
   ├─ [NEW] Channel Integration
   │  ├─ TikTok: username, bio, posting_time
   │  ├─ YouTube: channel_id, url
   │  ├─ Instagram: handle, bio
   │  └─ LinkedIn: profile_url
   └─ [Generate Video] button
```

### Tab 2: VIDEO EDITING (Refactored - 3 Steps)
```
STEP 1: URL Input + Persona Selection
├─ Input product URL
├─ [Validate] → Extract metadata
├─ Select personas (max 5)
└─ [Next: Generate Plans]

↓ API: POST /api/customer/review-engine/jobs
↓ Generate scripts for each persona

STEP 2: Plan Review & Edit [NEW]
├─ Show N plan cards (one per persona)
├─ Each plan shows:
│  ├─ Script preview
│  ├─ Scenes list (6-8 scenes)
│  └─ Action buttons:
│     ├─ [✏️ Edit] → Open edit modal
│     ├─ [✕ Reject] → Delete plan
│     └─ [✓ Approve & Generate] → Start workflow
└─ Edit modal allows:
   ├─ Edit script narration
   ├─ Edit scene prompts, captions, timestamps
   ├─ Add/remove scenes
   └─ [Save Changes]

↓ API: PATCH /api/customer/review-engine/plans/{plan_id}
↓ API: POST /api/customer/review-engine/plans/{plan_id}/approve

STEP 3: Video Rendering (Background)
├─ Show progress per persona
├─ Status: "Generating audio" → "Generating images" → "Creating video" → "Quality check"
├─ Progress bar (0-100%)
└─ When complete: Show ✓ Ready for Publishing

↓ Auto navigate to Publishing tab
```

### Tab 3: PUBLISHING [NEW]
```
Section 1: Completed Videos
├─ List videos with status 'complete'
├─ Show: thumbnail, persona, duration
└─ [Preview] [Configure]

Section 2: Per-Platform Settings
├─ For each platform (TikTok, YouTube, Instagram, LinkedIn):
│  ├─ Account: [dropdown with channels]
│  ├─ Title: [text input] (custom override)
│  ├─ Description: [textarea]
│  ├─ Hashtags: [editable tags]
│  ├─ Schedule: [date/time picker]
│  └─ [Save for {Platform}]
└─ Can configure multiple platforms per video

Section 3: Publish Actions
├─ [Preview All] - Show video previews
├─ [Draft All] - Save without publishing
└─ [Publish Now] - Start publishing workflow
   → Shows: "Publishing 3 videos to TikTok, YouTube..."
   → Returns: Post URLs when complete
```

### Tab 4: ACTIVITY FEED (Existing)
```
Shows: Workflows, approvals, content, campaigns (unchanged)
```

---

## 🔀 NEW FLOW - DATA FLOW

```
BEFORE: Personas → Script generation (hidden) → Approval (Telegram-only)

AFTER:
  1. Personas [TAB 1]
     └─ Select + [Generate Video]

  2. Video Editing [TAB 2] - Step 1
     └─ Input URL → Validate → Select personas

  3. Video Editing [TAB 2] - Step 2 [NEW]
     └─ Generate plans → Review/Edit scripts → Approve

  4. Video Editing [TAB 2] - Step 3
     └─ Render videos (show progress bars)

  5. Publishing [TAB 3] [NEW]
     └─ Configure per-platform settings → Publish

BACKEND FLOW:
  1. POST /api/customer/review-engine/jobs
     → Generate scripts (existing ScriptService)
     → Return script_contract[] to frontend

  2. POST /api/customer/review-engine/plans [NEW]
     → Save plans in DB with plan_id

  3. User edits plans in UI
     → PATCH /api/customer/review-engine/plans/{plan_id}
     → Update script_text + scenes_data in DB

  4. User approves plans
     → POST /api/customer/review-engine/plans/{plan_id}/approve
     → Start ShortVideoWorkflow with edited script (don't regenerate)
     → Update plan status to 'approved' + set workflow_id

  5. Workflow runs in background
     → Emit progress updates
     → Frontend polls GET /api/customer/review-engine/plans/{plan_id}
     → Update progress bar in Step 3 UI

  6. When video complete
     → Plan status = 'complete', video_url populated
     → Frontend shows "Ready for Publishing"
     → Auto navigate to Tab 3 Publishing

  7. User configures publishing settings
     → PATCH /api/customer/review-engine/plans/{plan_id}/publish-settings
     → Save: platforms, titles, descriptions, hashtags, schedule times

  8. User clicks [Publish Now]
     → POST /api/customer/review-engine/publish
     → For each plan/platform: Call platform API (TikTok, YouTube, etc.)
     → Save post_url to DB
     → Return publish job status

  9. Frontend polls GET /api/customer/review-engine/publish-jobs/{job_id}
     → Show publishing progress
     → When complete: Show post URLs
```

---

## 📊 IMPLEMENTATION SUMMARY

### What Exists (Can Use As-Is)
| Item | Status | Notes |
|------|--------|-------|
| Persona CRUD | ✅ | Just need to add channel configs |
| URL validation | ✅ | WebsiteReviewService ready |
| Script generation | ✅ | ScriptService ready |
| Video workflow | ✅ | ShortVideoWorkflow ready |
| Database (personas, etc) | ✅ | Schema exists |

### What's Partially Done
| Item | Current | Needed |
|------|---------|--------|
| Plan generation | ✅ Endpoint works | ❌ Plans not saved to DB |
| LiveFeedTab UI | ✅ Layout exists | ❌ Connect to real data |
| Approval flow | ✅ Telegram approval | ❌ UI-based approval |

### What Needs to Be Built
| Item | Effort | Days |
|------|--------|------|
| Backend: 7 new endpoints | MEDIUM | 2-3 |
| Database: 2 new tables | SMALL | 0.5 |
| Frontend: 4 new components | MEDIUM | 2-3 |
| Frontend: Type definitions | SMALL | 0.5 |
| Integration & testing | MEDIUM | 1-2 |
| **TOTAL** | | **6-8 days** |

---

## 🚀 START HERE - RECOMMENDED ORDER

### Day 1: Database Setup
```sql
1. Create video_render_plans table
2. Add gender, channel_configs to personas
3. Run migrations
```

### Days 2-3: Backend Endpoints
```python
1. POST /api/customer/review-engine/plans
2. PATCH /api/customer/review-engine/plans/{plan_id}
3. POST /api/customer/review-engine/plans/{plan_id}/approve
   └─ Modify ShortVideoWorkflow to accept pre-approved script
4. POST /api/customer/review-engine/publish
5. Add progress tracking to workflow
```

### Day 4: Frontend Foundation
```typescript
1. Create types: ScriptPlan, VideoScene, etc.
2. Create store: useVideoPlanningStore
3. Hook up Step 1 → POST /jobs
```

### Days 5-6: Frontend Components
```typescript
1. PlanReviewStep (show plans)
2. PlanEditModal (edit script/scenes)
3. PublishingTab (new tab)
4. Wire everything together
```

### Day 7: Integration & Testing
```
1. E2E test: URL → Plans → Edit → Approve → Video → Publish
2. Error handling
3. Polish UX
```

---

## 💡 KEY CHANGES FROM CURRENT

### Before
```
Personas → [Generate] → Scripts created in backend
         → Approval via Telegram only
         → No user edit capability
         → No UI-based publishing
```

### After
```
Personas → [Generate Plans] → Plans stored in DB with plan_id
        → [Review & Edit] in UI → Edit script + scenes
        → [Approve] in UI → Start workflow
        → [Monitor Progress] real-time
        → [Configure Publishing] per-platform settings
        → [Batch Publish] to multiple platforms
```

---

## 📝 IMPORTANT NOTES

1. **Plans are stored in DB** - All generated plans saved with `plan_id` for retrieval/editing
2. **Edit before approval** - User can modify scripts/scenes before workflow starts
3. **No Telegram blocking** - Approval happens in UI, not Telegram (cleaner UX)
4. **Per-persona progress** - See status for each video separately
5. **Batch publishing** - Configure multiple videos → publish to multiple platforms at once
6. **Platform-specific settings** - Each video/platform combo can have custom title, description, schedule
7. **Reuse infrastructure** - Leverages existing ScriptService, ShortVideoWorkflow, etc.

