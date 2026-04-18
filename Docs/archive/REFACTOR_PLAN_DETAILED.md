# VIDEO CREATION REFACTOR - COMPLETE BLUEPRINT

## ✅ PHẦN ĐÃ CÓ (Can Reuse)

### Backend - Fully Functional
- ✅ `PersonaRegistryService` - CRUD personas (/api/personas/*)
- ✅ `WebsiteReviewService` - Extract page metadata từ URL
- ✅ `ScriptService.generate_script_from_review_plan()` - Tạo script plan từ persona + URL
- ✅ `ShortVideoWorkflow` - Tạo video từ approved script
- ✅ Approval activities (`generate_and_send_script_for_approval`, `wait_for_script_approval`)
- ✅ Media generation (audio, images, talking head)
- ✅ `social_accounts` table - Channel integration (FK to personas)

### Backend - Partial
- ⚠️ `/api/customer/review-engine/jobs` (POST) - Generate scripts for multiple personas
  - ✅ Takes: { source_url, target_personas[], objective }
  - ✅ Returns: { status, jobs: [{ persona_id, script_contract, campaign_id }] }
  - ❌ Doesn't store plans in DB
  - ❌ Doesn't track plan_id for later retrieval

### Frontend - UI Components Exist
- ✅ `PersonasTab.tsx` - List & select personas
- ✅ `LiveFeedTab.tsx` - 3-step video editing flow (Step 1, 2, 3 UI scaffolding)
- ✅ `customer-dashboard.tsx` - Main dashboard structure
- ✅ API client: `customerApiRequest()` - HTTP requests

### Frontend - Partial
- ⚠️ `LiveFeedTab.tsx` Step 3 (Factory Output)
  - ✅ Video preview layout exists
  - ✅ Script editor textarea exists
  - ✅ Persona actions panel exists
  - ❌ NOT connected to actual script data
  - ❌ Mock/placeholder content only

### Database - Existing Schema
```sql
✅ personas table:
   - persona_id, display_name, language, tts_voice, avatar_image_url
   - heygen_avatar_id, status, video_count, user_id

✅ social_accounts table:
   - persona_id (FK), platform, account_handle, oauth_token, connection_status

✅ content table:
   - user_id, campaign_id, title, platform[], status, media_urls

✅ approvals table:
   - workflow_id, status (pending/approved/rejected)

❌ NO: video_render_plans table
❌ NO: persona_channel_configs table
```

---

## ❌ PHẦN CHƯA CÓ (Need to Build)

---

## 🗄️ PLAN PERSISTENCE STRATEGY - WHY DB, NOT CACHE

### Decision: Plans MUST be persisted in Database (NOT temporary cache)

**Why?** This is a critical architectural decision that enables the entire editing + approval workflow:

#### 1. **Session Persistence & User Control**
```
Scenario A (Cache only - BROKEN):
  User: Generate 5 plans → Edit 3 → Reload page → ALL PLANS LOST ❌

Scenario B (DB Persistence - CORRECT):
  User: Generate 5 plans → Edit 3 → Reload page → Plans still there ✅
  User can:
    - Come back later to finish editing
    - Have multiple editing sessions
    - Share plan links with team
```

#### 2. **Edit Workflow Requires Plan IDs**
```
Flow:
  1. POST /api/customer/review-engine/jobs
     ← Returns: scripts (ephemeral)
  
  2. [MUST save to DB]
     POST /api/customer/review-engine/plans
     ← Returns: [{ plan_id: "uuid-123", persona_id, status: 'generated' }]
  
  3. User edits in UI (1 hour later)
     PATCH /api/customer/review-engine/plans/uuid-123
     ← Requires plan_id to identify WHICH plan to update
     ← Cannot work without DB persistence
  
  4. User approves
     POST /api/customer/review-engine/plans/uuid-123/approve
     ← Again: MUST have persisted plan_id
```

#### 3. **Batch Operations & Selective Approval**
```
User workflow:
- Generate 5 plans for 5 personas
- Approve: Persona A, C, D (3/5)
- Reject: Persona B, E (2/5)
- Later: Start renders for approved only
- Later: Come back to edit & approve B, E

Without DB: Impossible (no way to track which is which)
With DB: Each plan has plan_id, status persists independently
```

#### 4. **Rendering Progress Tracking**
```
Timeline:
  1. User approves plan/uuid-123
     → POST /approve starts ShortVideoWorkflow
     → Returns: workflow_id, status='approved'
     → Saves to video_render_plans.workflow_id
  
  2. Frontend polls progress
     GET /api/customer/review-engine/plans/uuid-123
     ← Queries DB for current status + progress_percent
     ← Returns: { status: 'in_progress', progress: 45%, ... }
  
  3. Workflow completes (30 mins later)
     → Updates DB: status='complete', video_url='s3://...'
  
  4. User checks dashboard next day
     GET /api/customer/review-engine/plans/uuid-123
     ← Retrieves: video_url, allows publishing
```

#### 5. **Publishing Settings Persistence**
```
After video renders complete:
  User sees: "Ready for Publishing"
  User configures:
    - TikTok: Title, description, hashtags, schedule time
    - YouTube: Title, description, category
    - Instagram: Caption, hashtags, schedule
  
  PATCH /api/customer/review-engine/plans/uuid-123/publish-settings
  Body: {
    platforms: {
      tiktok: { title, description, hashtags, schedule_time },
      youtube: { title, description, category },
      instagram: { caption, hashtags, schedule_time }
    }
  }
  ← Saves to video_render_plans.publish_settings JSONB column
  
  Later, user clicks "Publish Now"
  POST /api/customer/review-engine/publish
  ← Reads ALL plans with status='complete' + publish_settings
  ← Publishes to configured platforms
  
  Without DB: Publishing config lost on page refresh ❌
```

### Data Lifecycle Table

| Step | Action | Location | Persistence |
|------|--------|----------|--------------|
| 1 | User generates scripts | Frontend → Backend | Ephemeral (POST /jobs response) |
| 2 | **Save plans to DB** | Backend | **DB: video_render_plans** ← plan_id created |
| 3 | User edits script/scenes | Frontend UI | Temporary (form state) |
| 4 | **Save edits to DB** | Backend (PATCH) | **DB: update script_text + scenes_data** |
| 5 | User approves plan | Frontend | Triggers POST /approve |
| 6 | **Start workflow** | Backend | **DB: status='approved', workflow_id set** |
| 7 | Workflow renders (30 min) | Background | **DB: updated with progress, video_url** |
| 8 | User configures publishing | Frontend | Temporary (form state) |
| 9 | **Save publish settings** | Backend (PATCH) | **DB: publish_settings JSONB** |
| 10 | User publishes | Frontend → API | **DB: reads plans, publishes to platforms** |

### Implementation Note

**Editing updates ONLY if plan is in 'generated' or 'edited' state:**
```python
# PATCH /api/customer/review-engine/plans/{plan_id}
if plan.status not in ['generated', 'edited']:
    raise BadRequest(
        f"Cannot edit plan in {plan.status} state. "
        f"Only 'generated' and 'edited' plans can be modified."
    )
plan.script_text = body.script
plan.scenes_data = body.scenes
plan.status = 'edited'  # Mark as user-edited
plan.save()
```

This prevents accidental edits to plans that are already rendering or approved.

---

### Backend - New Endpoints Needed

#### 1. Store Generated Plans
```python
# POST /api/customer/review-engine/plans
# Body: { source_url, objective, target_personas[], generated_jobs }
# Return: { status: "stored", plans: [{ plan_id, persona_id, campaign_id }] }

Purpose: Save generated script plans so they can be retrieved & edited later
```

#### 2. Update/Edit Plan
```python
# PATCH /api/customer/review-engine/plans/{plan_id}
# Body: { script, scenes[] }
# Return: { plan_id, status: "updated", script, scenes }

Purpose: User edits script narration or scenes
```

#### 3. Retrieve Single Plan
```python
# GET /api/customer/review-engine/plans/{plan_id}
# Return: { plan_id, persona_id, script, scenes, status, duration }

Purpose: Load plan data for display/editing
```

#### 4. List Plans by Campaign
```python
# GET /api/customer/review-engine/campaigns/{campaign_id}/plans
# Return: { plans: [{ plan_id, persona_id, status, created_at }] }

Purpose: Show all generated plans for a campaign
```

#### 5. Approve & Start Workflow
```python
# POST /api/customer/review-engine/plans/{plan_id}/approve
# Body: { approved: true }
# Return: { workflow_id, status: "queued", plan_id }

Purpose: User approves edited plan → Start ShortVideoWorkflow
```

#### 6. Reject/Delete Plan
```python
# DELETE /api/customer/review-engine/plans/{plan_id}
# Return: { status: "deleted" }

Purpose: Discard a plan
```

### Database - New Tables

#### Table 1: video_render_plans
```sql
CREATE TABLE video_render_plans (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL,
  campaign_id UUID,
  persona_id UUID NOT NULL,
  
  -- Input context
  source_url TEXT NOT NULL,
  objective TEXT,
  
  -- Script content (editable)
  script_text TEXT NOT NULL,
  scenes_data JSONB NOT NULL,  -- [{id, timestamp_start, timestamp_end, caption, image_prompt}]
  duration_estimate FLOAT,
  
  -- Status tracking
  status TEXT DEFAULT 'generated',  -- 'generated' | 'edited' | 'approved' | 'rejected' | 'in_progress' | 'complete' | 'failed'
  
  -- Workflow link
  workflow_id TEXT,
  video_url TEXT,
  
  -- Audit
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  approved_at TIMESTAMP,
  
  -- Constraints
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
  FOREIGN KEY (persona_id) REFERENCES personas(id),
  CONSTRAINT video_render_plans_pkey PRIMARY KEY (id)
);

CREATE INDEX idx_video_render_plans_user_id ON video_render_plans(user_id);
CREATE INDEX idx_video_render_plans_campaign_id ON video_render_plans(campaign_id);
CREATE INDEX idx_video_render_plans_workflow_id ON video_render_plans(workflow_id);
```

#### Table 2: persona_channel_configs
```sql
CREATE TABLE persona_channel_configs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  persona_id UUID NOT NULL,
  platform TEXT NOT NULL,  -- 'tiktok' | 'youtube' | 'instagram' | 'linkedin'
  
  -- Channel metadata
  channel_name TEXT,
  bio TEXT,
  banner_url TEXT,
  verified_status BOOLEAN DEFAULT false,
  
  -- Upload preferences
  upload_preferences JSONB DEFAULT '{}',  -- { posting_time, category, hashtags, description_template }
  
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  
  FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE,
  UNIQUE(persona_id, platform)
);
```

### Database - Schema Modifications

#### Modify: personas table
```sql
-- Add missing fields
ALTER TABLE personas ADD COLUMN IF NOT EXISTS gender VARCHAR(20);
ALTER TABLE personas ADD COLUMN IF NOT EXISTS channel_configs JSONB DEFAULT '{}';

-- Example data:
channel_configs: {
  "tiktok": {
    "username": "@persona_name",
    "bio": "AI Influencer - Product Reviews",
    "posting_time": "19:00",
    "hashtags": ["#tech", "#review"]
  },
  "youtube": {
    "channel_id": "UC123",
    "description": "AI Channel"
  }
}
```

### Frontend - New Type Definitions

```typescript
// types/video-planning.ts

export interface VideoScene {
  id: number;
  timestamp_start: number;
  timestamp_end: number;
  caption: string;
  image_prompt: string;
}

export interface ScriptPlan {
  plan_id: string;
  persona_id: string;
  persona_name: string;
  campaign_id?: string;
  source_url: string;
  objective: string;
  script: string;
  scenes: VideoScene[];
  duration_estimate: number;
  status: 'generated' | 'edited' | 'approved' | 'in_progress' | 'complete' | 'failed';
  created_at: string;
  updated_at: string;
  workflow_id?: string;
  video_url?: string;
  error?: string;
}

export interface ScriptPlanUpdatePayload {
  script: string;
  scenes: VideoScene[];
}

export interface PersonaChannelConfig {
  platform: 'tiktok' | 'youtube' | 'instagram' | 'linkedin';
  channel_name?: string;
  bio?: string;
  banner_url?: string;
  verified_status?: boolean;
  upload_preferences?: {
    posting_time?: string;
    category?: string;
    hashtags?: string[];
    description_template?: string;
  };
}

export interface PersonaWithChannels extends Persona {
  gender?: string;
  channels?: {
    [key: string]: PersonaChannelConfig;
  };
}
```

### Frontend - New Components

#### Component 1: PlanReviewStep
```typescript
// components/video-editing/PlanReviewStep.tsx

interface PlanReviewStepProps {
  plans: ScriptPlan[];
  isLoading: boolean;
  onApprove: (plan_id: string) => Promise<void>;
  onEdit: (plan: ScriptPlan) => void;
  onReject: (plan_id: string) => Promise<void>;
}

export function PlanReviewStep({
  plans,
  isLoading,
  onApprove,
  onEdit,
  onReject,
}: PlanReviewStepProps) {
  const [expandedPlan, setExpandedPlan] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const handleApprove = async (plan_id: string) => {
    setApprovingId(plan_id);
    try {
      await onApprove(plan_id);
      // Navigate to next step or show success
    } finally {
      setApprovingId(null);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h2 className="text-3xl font-bold">Review & Edit Plans</h2>
        <p className="text-gray-600 mt-2">
          {plans.length} plan{plans.length !== 1 ? 's' : ''} generated. Edit as needed, then approve.
        </p>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p>Generating plans...</p>
        </div>
      ) : (
        <div className="space-y-4">
          {plans.map((plan) => (
            <PlanCard
              key={plan.plan_id}
              plan={plan}
              isExpanded={expandedPlan === plan.plan_id}
              onToggleExpand={() =>
                setExpandedPlan(expandedPlan === plan.plan_id ? null : plan.plan_id)
              }
              onEdit={() => onEdit(plan)}
              onApprove={() => handleApprove(plan.plan_id)}
              onReject={() => onReject(plan.plan_id)}
              isApproving={approvingId === plan.plan_id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

#### Component 2: PlanCard
```typescript
// components/video-editing/PlanCard.tsx

interface PlanCardProps {
  plan: ScriptPlan;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onEdit: () => void;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
  isApproving: boolean;
}

export function PlanCard({
  plan,
  isExpanded,
  onToggleExpand,
  onEdit,
  onApprove,
  onReject,
  isApproving,
}: PlanCardProps) {
  const [isRejecting, setIsRejecting] = useState(false);

  return (
    <div className="border rounded-lg bg-white hover:shadow-md transition-shadow overflow-hidden">
      {/* Header - Always visible */}
      <div className="flex items-center justify-between p-6 border-b hover:bg-gray-50 cursor-pointer" onClick={onToggleExpand}>
        <div className="flex-1">
          <h3 className="font-bold text-lg">{plan.persona_name}</h3>
          <div className="flex gap-4 mt-2 text-sm text-gray-600">
            <span>📊 {plan.duration_estimate.toFixed(1)}s duration</span>
            <span>🎬 {plan.scenes.length} scenes</span>
            <span>
              Status:{' '}
              <span className={`font-semibold ${
                plan.status === 'approved' ? 'text-green-600' :
                plan.status === 'edited' ? 'text-blue-600' :
                'text-yellow-600'
              }`}>
                {plan.status.toUpperCase()}
              </span>
            </span>
          </div>
        </div>
        <div className="text-gray-400">{isExpanded ? '▼' : '▶'}</div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="p-6 space-y-6 border-t bg-gray-50">
          {/* Script Preview */}
          <div>
            <h4 className="font-semibold mb-2">📝 Narration Script</h4>
            <div className="bg-white p-4 rounded border italic">
              "{plan.script}"
            </div>
          </div>

          {/* Scenes Preview */}
          <div>
            <h4 className="font-semibold mb-2">🎨 Scenes ({plan.scenes.length})</h4>
            <div className="grid gap-3">
              {plan.scenes.map((scene) => (
                <div key={scene.id} className="bg-white p-4 rounded border-l-4 border-blue-500">
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-mono text-xs text-gray-500">
                      Scene {scene.id}: {scene.timestamp_start.toFixed(1)}s - {scene.timestamp_end.toFixed(1)}s
                    </span>
                  </div>
                  <p className="font-semibold text-sm mb-1">{scene.caption}</p>
                  <p className="text-sm text-gray-600">{scene.image_prompt}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4 border-t">
            <button
              onClick={onEdit}
              className="flex-1 px-4 py-2.5 rounded font-semibold text-sm bg-gray-200 text-gray-800 hover:bg-gray-300 transition"
            >
              ✏️ Edit Script
            </button>
            <button
              onClick={() => {
                setIsRejecting(true);
                onReject().finally(() => setIsRejecting(false));
              }}
              disabled={isRejecting}
              className="flex-1 px-4 py-2.5 rounded font-semibold text-sm bg-red-100 text-red-700 hover:bg-red-200 transition disabled:opacity-50"
            >
              {isRejecting ? '⏳ Rejecting...' : '✕ Reject'}
            </button>
            <button
              onClick={onApprove}
              disabled={isApproving}
              className="flex-1 px-4 py-2.5 rounded font-semibold text-sm bg-green-600 text-white hover:bg-green-700 transition disabled:opacity-50"
            >
              {isApproving ? '⏳ Approving...' : '✓ Approve & Generate'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

#### Component 3: PlanEditModal
```typescript
// components/video-editing/PlanEditModal.tsx

interface PlanEditModalProps {
  plan: ScriptPlan;
  isOpen: boolean;
  isSaving: boolean;
  onSave: (updated: ScriptPlanUpdatePayload) => Promise<void>;
  onCancel: () => void;
}

export function PlanEditModal({
  plan,
  isOpen,
  isSaving,
  onSave,
  onCancel,
}: PlanEditModalProps) {
  const [editedScript, setEditedScript] = useState(plan.script);
  const [editedScenes, setEditedScenes] = useState<VideoScene[]>(plan.scenes);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setError(null);
    try {
      if (!editedScript.trim()) {
        setError('Script cannot be empty');
        return;
      }
      if (editedScenes.length === 0) {
        setError('At least one scene is required');
        return;
      }
      await onSave({
        script: editedScript,
        scenes: editedScenes,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-96 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b flex justify-between items-center">
          <h3 className="text-xl font-bold">Edit Plan - {plan.persona_name}</h3>
          <button
            onClick={onCancel}
            className="text-gray-500 hover:text-gray-700"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded">
              {error}
            </div>
          )}

          {/* Edit Script */}
          <div>
            <label className="block font-semibold mb-2">Narration Script</label>
            <textarea
              value={editedScript}
              onChange={(e) => setEditedScript(e.target.value)}
              rows={4}
              className="w-full border rounded p-3 font-body resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter the script narration..."
            />
            <p className="text-xs text-gray-500 mt-1">{editedScript.length} / 200 characters</p>
          </div>

          {/* Edit Scenes */}
          <div>
            <label className="block font-semibold mb-2">Scenes</label>
            <div className="space-y-3">
              {editedScenes.map((scene, idx) => (
                <div key={scene.id} className="border rounded p-4 space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="font-mono text-xs text-gray-600">Scene {scene.id}</span>
                    <button
                      onClick={() => setEditedScenes(editedScenes.filter((_, i) => i !== idx))}
                      className="text-red-600 text-sm hover:font-bold"
                    >
                      Remove
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={scene.timestamp_start}
                      onChange={(e) => {
                        const updated = [...editedScenes];
                        updated[idx].timestamp_start = parseFloat(e.target.value);
                        setEditedScenes(updated);
                      }}
                      placeholder="Start time (s)"
                      className="border rounded px-2 py-1 text-sm"
                    />
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={scene.timestamp_end}
                      onChange={(e) => {
                        const updated = [...editedScenes];
                        updated[idx].timestamp_end = parseFloat(e.target.value);
                        setEditedScenes(updated);
                      }}
                      placeholder="End time (s)"
                      className="border rounded px-2 py-1 text-sm"
                    />
                  </div>

                  <input
                    type="text"
                    value={scene.caption}
                    onChange={(e) => {
                      const updated = [...editedScenes];
                      updated[idx].caption = e.target.value;
                      setEditedScenes(updated);
                    }}
                    placeholder="Scene caption (8 words max)"
                    className="w-full border rounded px-3 py-1 text-sm"
                  />

                  <textarea
                    value={scene.image_prompt}
                    onChange={(e) => {
                      const updated = [...editedScenes];
                      updated[idx].image_prompt = e.target.value;
                      setEditedScenes(updated);
                    }}
                    placeholder="Image generation prompt..."
                    rows={2}
                    className="w-full border rounded px-3 py-2 text-sm resize-none"
                  />
                </div>
              ))}
            </div>

            <button
              onClick={() =>
                setEditedScenes([
                  ...editedScenes,
                  {
                    id: Math.max(...editedScenes.map((s) => s.id), 0) + 1,
                    timestamp_start: editedScenes[editedScenes.length - 1]?.timestamp_end || 0,
                    timestamp_end: (editedScenes[editedScenes.length - 1]?.timestamp_end || 0) + 5,
                    caption: '',
                    image_prompt: '',
                  },
                ])
              }
              className="mt-3 text-sm text-blue-600 hover:font-bold"
            >
              + Add Scene
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={isSaving}
            className="px-4 py-2 rounded border border-gray-300 hover:bg-gray-100 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? '⏳ Saving...' : '💾 Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Frontend - New Stores (Zustand)

```typescript
// store/video-planning-store.ts

import { create } from 'zustand';
import { ScriptPlan } from '@/types/video-planning';

interface VideoPlanningState {
  // Current workflow state
  sourceUrl: string;
  objective: string;
  selectedPersonaIds: string[];
  
  // Generated plans
  plans: ScriptPlan[];
  isGeneratingPlans: boolean;
  
  // Edit mode
  editingPlanId: string | null;
  
  // Actions
  setSourceUrl: (url: string) => void;
  setObjective: (obj: string) => void;
  setSelectedPersonaIds: (ids: string[]) => void;
  setPlans: (plans: ScriptPlan[]) => void;
  setIsGeneratingPlans: (loading: boolean) => void;
  setEditingPlanId: (id: string | null) => void;
  
  // Computed
  approvedPlans: () => ScriptPlan[];
  editingPlan: () => ScriptPlan | undefined;
  
  // Reset
  reset: () => void;
}

export const useVideoPlanningStore = create<VideoPlanningState>((set, get) => ({
  sourceUrl: '',
  objective: '',
  selectedPersonaIds: [],
  plans: [],
  isGeneratingPlans: false,
  editingPlanId: null,
  
  setSourceUrl: (url) => set({ sourceUrl: url }),
  setObjective: (obj) => set({ objective: obj }),
  setSelectedPersonaIds: (ids) => set({ selectedPersonaIds: ids }),
  setPlans: (plans) => set({ plans }),
  setIsGeneratingPlans: (loading) => set({ isGeneratingPlans: loading }),
  setEditingPlanId: (id) => set({ editingPlanId: id }),
  
  approvedPlans: () => get().plans.filter((p) => p.status === 'approved'),
  editingPlan: () => get().plans.find((p) => p.plan_id === get().editingPlanId),
  
  reset: () =>
    set({
      sourceUrl: '',
      objective: '',
      selectedPersonaIds: [],
      plans: [],
      isGeneratingPlans: false,
      editingPlanId: null,
    }),
}));
```

---

## 🎬 NEW FLOW - DETAILED STEP BY STEP

### Tab 1: Personas Management

**Layout:**
```
Left Panel:
├─ Personas List (searchable)
├─ [+ Build New Persona] button
└─ Each persona card:
   ├─ Avatar + name
   ├─ Status badge
   └─ Click to select

Right Panel (when persona selected):
├─ Persona Details:
│  ├─ Display Name
│  ├─ Language
│  ├─ Gender (NEW)
│  ├─ TTS Voice
│  └─ Avatar preview
│
├─ Channel Integration (NEW):
│  ├─ TikTok:
│  │  ├─ Username input
│  │  ├─ Bio input
│  │  └─ Posting preferences
│  ├─ YouTube: [similar]
│  ├─ Instagram: [similar]
│  └─ LinkedIn: [similar]
│
└─ Actions:
   ├─ [Edit Core]
   ├─ [Save]
   └─ [Generate Video] → Navigate to Video Editing Tab
```

**API Calls:**
```
GET /api/customer/personas?user_id={user_id}
  → List all personas with channels

PATCH /api/customer/personas/{persona_id}
  → Update persona fields + channel configs
```

---

### Tab 2: Video Editing (3-Step Flow)

#### **STEP 1: URL Validation + Persona Selection**

**UI:**
```
┌─ Source Input Panel
│  ├─ Text: "Enter product URL (App Store, web, etc)"
│  ├─ Input field: [https://..............................]
│  └─ [Validate] button
│
└─ After validation:
   ├─ Show extracted data:
   │  ├─ Page title
   │  ├─ Product summary
   │  └─ Visible features (list)
   │
   └─ Persona Selection:
      ├─ "Select personas (max 5):"
      ├─ [Alex     ] [Zhang    ] [Pablo    ] [+ Maria] [+ Others]
      │  (checkboxes for selection)
      └─ [Next: Generate Plans] button
```

**API Calls:**
```
1. POST /api/customer/review-engine/source/validate
   Body: { source_url: "https://..." }
   Return: { normalized_url, page_title, visible_features }

2. POST /api/customer/review-engine/jobs
   Body: { 
     source_url: "https://...",
     objective: "Product review",
     target_personas: ["alex_id", "zhang_id", "pablo_id"]
   }
   Return: { 
     status: "success",
     jobs: [
       { persona_id: "alex", script_contract: {...}, campaign_id: "..." },
       { persona_id: "zhang", script_contract: {...}, campaign_id: "..." },
       ...
     ]
   }

3. POST /api/customer/review-engine/plans
   Body: { 
     source_url: "https://...",
     objective: "...",
     generated_jobs: [...]
   }
   Return: {
     status: "stored",
     plans: [
       { plan_id: "plan-1", persona_id: "alex", campaign_id: "..." },
       ...
     ]
   }
```

**Store Update:**
```typescript
setSourceUrl(url);
setObjective("Product review");
setSelectedPersonaIds(["alex_id", "zhang_id"]);
setIsGeneratingPlans(true);
// After generation:
setPlans(generatedPlans);
setIsGeneratingPlans(false);
```

---

#### **STEP 2: Plan Review & Edit (NEW)**

**UI:**
```
┌─ Plan Review Panel
│  ├─ Title: "Review & Edit Plans" (N plans generated)
│  │
│  ├─ For each plan:
│  │  ┌─ PlanCard (collapsed by default)
│  │  │  ├─ Header (expandable):
│  │  │  │  ├─ Persona name: "Alex - US"
│  │  │  │  ├─ Duration: 45.2s
│  │  │  │  ├─ Scenes: 6
│  │  │  │  └─ Status: "GENERATED"
│  │  │  │
│  │  │  └─ When expanded:
│  │  │     ├─ Script preview: "Hey everyone, check out..."
│  │  │     ├─ Scenes list:
│  │  │     │  ├─ Scene 1: [0s-5s] "Trending feature" | "App UI showing..."
│  │  │     │  ├─ Scene 2: [5s-10s] "Key benefit" | "Developer using..."
│  │  │     │  └─ ...
│  │  │     │
│  │  │     └─ Action buttons:
│  │  │        ├─ [✏️ Edit Script]  → Open PlanEditModal
│  │  │        ├─ [✕ Reject]        → Delete plan
│  │  │        └─ [✓ Approve & Generate] → Start workflow
│  │  │
│  │  └─ [Next plan...]
│  │
│  └─ Note: "You can edit any plan before approving"
```

**Interactions:**
```
User clicks [✏️ Edit Script]:
  → Open PlanEditModal
  → Load: plan.script, plan.scenes
  → User edits:
     - Script text
     - Scene captions
     - Image prompts
     - Timestamps
     - Can add/remove scenes
  → [Save Changes]
     → PATCH /api/customer/review-engine/plans/{plan_id}
        Body: { script, scenes }
        Return: updated plan
     → Update in plans array
     → Close modal
     → Show "Updated" badge on PlanCard

User clicks [✓ Approve & Generate]:
  → POST /api/customer/review-engine/plans/{plan_id}/approve
     Body: { approved: true }
     Return: { workflow_id, status: "queued" }
  → Create video_render_job entry
  → Show progress indicator
  → Move to Step 3
```

**API Calls:**
```
# Get single plan (optional, for editing)
GET /api/customer/review-engine/plans/{plan_id}
  Return: { plan_id, persona_id, script, scenes, ... }

# Update plan after editing
PATCH /api/customer/review-engine/plans/{plan_id}
  Body: { script, scenes[] }
  Return: { status: "updated", plan_id, script, scenes }

# Delete/Reject plan
DELETE /api/customer/review-engine/plans/{plan_id}
  Return: { status: "deleted" }

# Approve & start workflow
POST /api/customer/review-engine/plans/{plan_id}/approve
  Body: { approved: true }
  Return: { workflow_id, status: "queued" }
```

---

#### **STEP 3: Video Rendering Progress**

**UI:**
```
┌─ Rendering Progress Panel
│  ├─ Title: "Video Generation in Progress..."
│  │
│  ├─ For each approved plan (showing progress):
│  │  ┌─ Progress Card
│  │  │  ├─ Persona: "Alex - US"
│  │  │  ├─ Status timeline:
│  │  │  │  ├─ ✓ Plan approved
│  │  │  │  ├─ ✓ Script generated
│  │  │  │  ├─ ⟳ Generating audio...     (current)
│  │  │  │  ├─ ○ Generating images
│  │  │  │  ├─ ○ Creating video
│  │  │  │  └─ ○ Quality check
│  │  │  │
│  │  │  ├─ Progress bar: 40% (audio generation)
│  │  │  │
│  │  │  └─ When complete:
│  │  │     ├─ ✓ Video ready!
│  │  │     ├─ Preview thumbnail/poster
│  │  │     └─ Status: "READY FOR PUBLISHING"
│  │  │
│  │  └─ [Next persona's progress...]
│  │
│  └─ Auto-refresh every 2-3 seconds
│     GET /api/customer/review-engine/plans/{plan_id}
│        Return: { status, progress, current_step, video_url, error }
```

**Real-time Updates:**
```
// In workflow, emit progress events
send_telegram_progress_update({
  workflow_id,
  plan_id,
  current_step: "generating_audio",
  progress: 40,
  details: "Processing with Google TTS..."
})

// Frontend polls or receives WebSocket
GET /api/customer/review-engine/plans/{plan_id}
  While status !== 'complete' and status !== 'failed':
    - Update progress bar
    - Update step indicator
    - Show error if failed
```

---

### Tab 3: Publishing (NEW TAB)

**Layout:**
```
┌─ Publishing Hub
│
├─ Section 1: Completed Videos
│  │  (Videos with status = 'complete')
│  │
│  ├─ Filter: [All Personas ▼] [Today ▼] [Search...]
│  │
│  ├─ For each video:
│  │  ┌─ Video Card
│  │  │  ├─ Left: Video thumbnail + play icon
│  │  │  ├─ Middle:
│  │  │  │  ├─ Persona: "Alex - US"
│  │  │  │  ├─ Product: "ZenFocus App"
│  │  │  │  ├─ Generated: "2 hours ago"
│  │  │  │  └─ Duration: 45s
│  │  │  │
│  │  │  └─ Right:
│  │  │     ├─ [Preview] → Video modal
│  │  │     └─ [Configure] → Open platform settings
│  │  │
│  │  └─ Platform Selection (when configured):
│  │     ├─ ☐ TikTok (default)
│  │     ├─ ☑ YouTube
│  │     ├─ ☐ Instagram
│  │     └─ ☐ LinkedIn
│  │
│  └─ [Batch Select All] [Clear]
│
├─ Section 2: Platform Settings (when a video selected)
│  │
│  ├─ For each platform:
│  │  ├─ Platform: "TikTok"
│  │  ├─ Account: [@persona_tiktok_handle ▼]
│  │  ├─ Custom title: [Title override text field]
│  │  ├─ Custom description: [Multi-line text]
│  │  ├─ Hashtags: [#tech #review #ai] (editable tags)
│  │  ├─ Schedule:
│  │  │  ├─ ○ Publish immediately
│  │  │  ├─ ◉ Schedule for: [Date picker] [Time picker]
│  │  │  └─ ○ Draft (save without publishing)
│  │  │
│  │  └─ [✓] [Save for TikTok]
│  │
│  └─ [Next platform...]
│
└─ Section 3: Publish Actions
   ├─ [Preview All] → Show video previews
   ├─ [Draft All]   → Save without publishing
   └─ [Publish Now] → Start publishing workflow
      └─ Shows: "Publishing 3 videos to TikTok, YouTube, Instagram..."
```

**API Calls:**
```
# Get completed videos
GET /api/customer/review-engine/plans?status=complete
  Return: { plans: [completed_plans] }

# Update platform settings for a video
PATCH /api/customer/review-engine/plans/{plan_id}/publish-settings
  Body: {
    platforms: [
      {
        platform: "tiktok",
        account_id: "...",
        title: "Custom title",
        description: "Custom description",
        hashtags: ["#tech", "#review"],
        scheduled_at: "2024-04-20T19:00:00Z"
      },
      ...
    ]
  }
  Return: { status: "updated", plan_id }

# Batch publish
POST /api/customer/review-engine/publish
  Body: {
    plan_ids: ["plan-1", "plan-2", "plan-3"],
    publish_mode: "immediate" | "scheduled" | "draft"
  }
  Return: { 
    status: "publishing",
    publish_job_id: "...",
    plans_count: 3
  }

# Get publish job status
GET /api/customer/review-engine/publish-jobs/{job_id}
  Return: { 
    status: "in_progress" | "complete",
    results: [
      { plan_id, platform, status, published_at, post_url }
    ]
  }
```

---

## 📊 DATABASE SCHEMA - COMPLETE

### new_video_render_plans
```sql
CREATE TABLE video_render_plans (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  campaign_id UUID,
  persona_id UUID NOT NULL,
  
  -- Input
  source_url TEXT NOT NULL,
  objective TEXT,
  
  -- Script & Scenes (editable)
  script_text TEXT NOT NULL,
  scenes_data JSONB NOT NULL,
  duration_estimate FLOAT,
  
  -- Status
  status TEXT DEFAULT 'generated',
  workflow_id TEXT,
  video_url TEXT,
  error_message TEXT,
  
  -- Publishing settings
  publish_settings JSONB DEFAULT '{}',  -- { platforms: [{ platform, account_id, title, description, scheduled_at }] }
  
  -- Timestamps
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  approved_at TIMESTAMP,
  completed_at TIMESTAMP,
  
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (persona_id) REFERENCES personas(id)
);
```

### Update: personas table
```sql
ALTER TABLE personas 
ADD COLUMN gender VARCHAR(20),
ADD COLUMN channel_configs JSONB;

-- Example channel_configs:
{
  "tiktok": {
    "username": "@alex_ai",
    "verified": true,
    "bio": "AI Influencer - Product Reviews",
    "posting_time": "19:00"
  },
  "youtube": {
    "channel_id": "UCXXX",
    "channel_url": "youtube.com/c/alex_ai"
  }
}
```

---

## 🔄 COMPLETE FLOW - SEQUENCE DIAGRAM

```
USER JOURNEY:

1. STEP 1: URL Input
   User: Enter product URL → [Validate]
   ↓
   Frontend: POST /api/customer/review-engine/source/validate
   Backend: Extract metadata
   Frontend: Show features
   ↓
   User: Select personas (e.g., Alex, Zhang, Pablo)
   User: [Next: Generate Plans]

2. STEP 2: Generate Plans
   ↓
   Frontend: POST /api/customer/review-engine/jobs
           { source_url, objective, target_personas }
   Backend: For each persona:
     - Generate script via ScriptService
     - Create campaign
     - Return script_contract
   Frontend: POST /api/customer/review-engine/plans (save to DB)
   ↓
   Store: setPlans(generated_plans)

3. STEP 2b: Review & Edit (NEW)
   ↓
   User sees: 3 plan cards (Alex, Zhang, Pablo)
   User: Click [✏️] on Alex's plan
   ↓
   Modal opens with editable:
     - Script (narration)
     - Scenes (prompts, captions, timestamps)
   ↓
   User: Edit script + scenes
   User: [Save Changes]
   ↓
   Frontend: PATCH /api/customer/review-engine/plans/{plan_id}
   Backend: Update in DB
   ↓
   PlanCard shows: "EDITED" badge
   ↓
   User: Repeat for other personas or approve

4. STEP 2c: Approve
   ↓
   User: Click [✓ Approve & Generate]
   ↓
   Frontend: POST /api/customer/review-engine/plans/{plan_id}/approve
   Backend: 
     - Mark plan as 'approved'
     - Call ShortVideoWorkflow.start({
       persona_id,
       script: plan.script,
       scenes: plan.scenes,
       media_assets: ...
     })
   ↓
   Return: { workflow_id, status: "queued" }

5. STEP 3: Video Generation (Background)
   ↓
   Workflow runs:
     ├─ AI generates script (already done)
     ├─ Generate audio (Google TTS)
     ├─ Generate scene images (fal.ai)
     ├─ Create talking head (HeyGen)
     ├─ Build final video
     └─ Quality check
   ↓
   Frontend polls: GET /api/customer/review-engine/plans/{plan_id}
   Updates progress bar in Step 3 UI
   ↓
   When complete:
     ├─ status = 'complete'
     ├─ video_url = 'https://storage/...'
     └─ Show ✓ Ready for Publishing

6. STEP 4: Publishing (NEW TAB)
   ↓
   User navigates to: "Publishing" tab
   ↓
   Shows: Completed videos
   ↓
   User selects: Video + platforms (TikTok, YouTube, Instagram)
   ↓
   User configures per-platform:
     - Custom title
     - Custom description
     - Hashtags
     - Schedule time
   ↓
   User: [Publish Now]
   ↓
   Frontend: POST /api/customer/review-engine/publish
            { plan_ids, platforms_settings, publish_mode }
   ↓
   Backend: For each plan/platform:
     - Get video URL
     - Get persona's social account token
     - Call platform API (TikTok API, YouTube API, etc.)
     - Save post_url to DB
   ↓
   Frontend: GET /api/customer/review-engine/publish-jobs/{job_id}
   Shows: Publishing status + post URLs
   
7. COMPLETE
   ✓ Videos published to all platforms
   User can see in "Activity Feed" tab
```

---

## 🛠️ IMPLEMENTATION ORDER (Priority)

### Phase 1: Database (1 day)
1. ✅ Create `video_render_plans` table
2. ✅ Add `gender` + `channel_configs` to personas
3. ✅ Add `publish_settings` column to content table

### Phase 2: Backend Endpoints (2-3 days)
1. POST `/api/customer/review-engine/plans` - Store generated plans
2. PATCH `/api/customer/review-engine/plans/{plan_id}` - Update plan
3. GET `/api/customer/review-engine/plans/{plan_id}` - Retrieve single plan
4. DELETE `/api/customer/review-engine/plans/{plan_id}` - Delete plan
5. POST `/api/customer/review-engine/plans/{plan_id}/approve` - Approve & start workflow
6. POST `/api/customer/review-engine/publish` - Batch publish
7. GET `/api/customer/review-engine/publish-jobs/{job_id}` - Check publish status

### Phase 3: Frontend Types & Store (1 day)
1. ✅ Define `ScriptPlan` interface
2. ✅ Define `VideoScene` interface
3. ✅ Create `useVideoPlanningStore`
4. ✅ Update Persona types with `gender` + `channels`

### Phase 4: Frontend Components (2-3 days)
1. ✅ `PlanReviewStep` - Review all plans
2. ✅ `PlanCard` - Expandable plan display
3. ✅ `PlanEditModal` - Edit script & scenes
4. ✅ Refactor `LiveFeedTab.tsx` - Remove mock, integrate real data
5. ✅ `PublishingTab.tsx` - New publishing interface

### Phase 5: Integration (1-2 days)
1. ✅ Wire Step 1 → Step 2 (generate plans)
2. ✅ Wire Step 2 → Edit → Step 3 (approve & render)
3. ✅ Wire Step 3 → Step 4 (publishing)
4. ✅ Poll/WebSocket for progress updates

### Phase 6: Testing & Refinement (1 day)
1. ✅ E2E test: URL → Plans → Edit → Approve → Video
2. ✅ Error handling
3. ✅ UX polish

---

## 📋 CHECKLIST FOR IMPLEMENTATION

**Backend:**
- [ ] Create migration: `video_render_plans` table
- [ ] Create migration: Add `gender`, `channel_configs` to personas
- [ ] POST `/api/customer/review-engine/plans` endpoint
- [ ] PATCH `/api/customer/review-engine/plans/{plan_id}` endpoint
- [ ] GET `/api/customer/review-engine/plans/{plan_id}` endpoint
- [ ] DELETE `/api/customer/review-engine/plans/{plan_id}` endpoint
- [ ] POST `/api/customer/review-engine/plans/{plan_id}/approve` endpoint
  - Calls: `ShortVideoWorkflow.start()` with edited script
  - Updates plan status to 'approved'
  - Returns workflow_id
- [ ] Modify `ShortVideoWorkflow` to accept pre-approved script (don't regenerate)
- [ ] Add progress tracking per-persona (emit workflow events)
- [ ] POST `/api/customer/review-engine/publish` endpoint
- [ ] GET `/api/customer/review-engine/publish-jobs/{job_id}` endpoint
- [ ] Add publish settings storage in DB

**Frontend:**
- [ ] Create types: `ScriptPlan`, `VideoScene`, `PersonaChannelConfig`
- [ ] Create Zustand store: `useVideoPlanningStore`
- [ ] Create component: `PlanReviewStep.tsx`
- [ ] Create component: `PlanCard.tsx`
- [ ] Create component: `PlanEditModal.tsx`
- [ ] Create component: `PublishingTab.tsx`
- [ ] Refactor `LiveFeedTab.tsx` - integrate real plans
- [ ] Update `PersonasTab.tsx` - add channel config UI
- [ ] Wire Step 1 → POST `/api/customer/review-engine/source/validate`
- [ ] Wire Step 2 → POST `/api/customer/review-engine/jobs`
- [ ] Wire Step 2b → PlanReviewStep (show generated plans)
- [ ] Wire Edit → PATCH plan endpoint
- [ ] Wire Approve → POST `/approve` endpoint + poll progress
- [ ] Wire Step 3 → GET plan status polling (show progress)
- [ ] Wire Publishing tab → POST `/publish` + GET job status

---

## 🎯 FINAL ARCHITECTURE

```
┌─ PERSONAS TAB ─────────────────────┐
│ • Manage personas                  │
│ • Edit name, voice, language       │
│ • Manage channel configs (NEW)     │
│ • [Generate Video] → Video Editing │
└────────────────────────────────────┘
           |
           v
┌─ VIDEO EDITING TAB ────────────────────────────────────────────┐
│                                                                 │
│ STEP 1: URL Input                                              │
│ • Enter product URL                                            │
│ • [Validate] → Extract metadata                               │
│ • Select personas (max 5)                                      │
│ • [Next: Generate Plans]                                       │
│                                                                 │
│ ↓ API: POST /api/customer/review-engine/jobs                  │
│                                                                 │
│ STEP 2: Plan Review & Edit (NEW)                              │
│ • Show N generated plans                                       │
│ • For each: Script + Scenes preview                           │
│ • [Edit] → PlanEditModal                                      │
│   ├─ Edit script text                                         │
│   ├─ Edit scenes (prompts, captions, timestamps)              │
│   └─ [Save Changes]                                           │
│ • [Approve & Generate] per plan                               │
│                                                                 │
│ ↓ API: PATCH plan → POST approve                              │
│                                                                 │
│ STEP 3: Video Rendering                                        │
│ • Show progress per persona                                    │
│ • Status timeline (audio → images → video → quality)          │
│ • Progress bar + current step                                  │
│ • When complete: Show ✓ Ready                                 │
│                                                                 │
│ ↓ Auto move to Publishing                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
           |
           v
┌─ PUBLISHING TAB (NEW) ──────────────────────────────────────┐
│                                                              │
│ Section 1: Completed Videos                                 │
│ • List videos with status 'complete'                        │
│ • Show thumbnail + persona + duration                       │
│ • [Preview] [Configure]                                     │
│                                                              │
│ Section 2: Platform Settings (when video selected)          │
│ • For each platform (TikTok, YouTube, Instagram, LinkedIn): │
│   ├─ Account: [dropdown]                                    │
│   ├─ Custom title: [text]                                   │
│   ├─ Description: [textarea]                                │
│   ├─ Hashtags: [editable tags]                              │
│   ├─ Schedule: [date/time picker]                           │
│   └─ [Save for {Platform}]                                  │
│                                                              │
│ Section 3: Actions                                           │
│ • [Preview All]                                             │
│ • [Draft All]                                               │
│ • [Publish Now]                                             │
│   → POST /api/customer/review-engine/publish                │
│   → Shows: Publishing progress                              │
│   → Returns: Post URLs                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘

BACKEND FLOW:

┌─ /api/customer/review-engine/source/validate
│  └─ WebsiteReviewService.review_url()
│
├─ /api/customer/review-engine/jobs (POST)
│  ├─ For each persona:
│  │  └─ ScriptService.generate_script_from_review_plan()
│  └─ Return: script_contract[] to frontend
│
├─ /api/customer/review-engine/plans (POST)
│  └─ Store in video_render_plans table
│
├─ /api/customer/review-engine/plans/{plan_id} (PATCH)
│  └─ Update script_text + scenes_data in DB
│
├─ /api/customer/review-engine/plans/{plan_id}/approve (POST)
│  ├─ Mark as 'approved' in DB
│  └─ Call ShortVideoWorkflow.start()
│     └─ Use edited script (don't regenerate)
│
├─ ShortVideoWorkflow (Temporal)
│  ├─ generate_audio()
│  ├─ generate_scene_images()
│  ├─ create_talking_head_video()
│  ├─ build_split_screen_video()
│  └─ quality_gate_check() → Set status to 'complete'
│
└─ /api/customer/review-engine/publish (POST)
   └─ For each platform:
      └─ Call platform API + store post_url
```

