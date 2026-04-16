# UI Refactor Plan — Enhanced (Frontend First)

Last verified: 2026-04-16 (UTC)
Status: **Phase 1 — UI Shell Refactor**

---

## Overview

Refactor the customer dashboard UI around a cleaner video-creation experience. This document is a direct, implementation-ready enhancement of the original plan — same strategic direction, sharper execution guidance.

**Rule for this phase:** Touch only what improves clarity and structure. Do not fight the current architecture. Do not introduce new global state. Preserve all existing API call patterns.

---

## Why This Approach

The current codebase has useful building blocks. The problem is presentation and information architecture, not the underlying logic.

- `customer-dashboard.tsx` — good shell, owns customer state correctly, keep as-is
- `LiveFeedTab.tsx` — has a 3-step skeleton but it is single-script oriented and heavily placeholder-driven; needs a focused rewrite into `CreateVideoTab.tsx`
- `PersonasTab.tsx` — persona editing works; missing channel-facing operational UI for TikTok
- Review-engine generation works; plan persistence and UI-driven approval/edit workflows are deferred to Phase 3

---

## Scope For This Phase

**In scope:**
- Rename and restructure tabs for clarity
- Rewrite `LiveFeedTab` into a structured `CreateVideoTab` with a clear 3-step layout
- Add 3 video mode cards in Step 1 (Mode 1 active, Mode 2 and 3 as roadmap states)
- Upgrade `PersonasTab` with a TikTok Channel card per persona
- Define frontend view model types in `video-planning.ts`
- Add polished empty, loading, and error states throughout

**Not in scope:**
- Backend plan persistence or approval persistence
- Real TikTok OAuth connection flow
- AI remote-computer recording (Mode 2) or human phone recording (Mode 3)
- Publishing orchestration
- New global Zustand store

---

## Tab Rename Map

Update tab IDs and display labels in `customer-dashboard.tsx`. No routing changes required — these are display-layer renames only.

| Current ID | Current Label | New Label |
|---|---|---|
| `overview` | Overview | Overview |
| `ops` | Ops | AI Operations |
| `skills` | Skills | Personas |
| `memory` | Memory | Project & Memory |
| `live_feed` | Live Feed | Create Video |

**Implementation note:** Search for `live_feed` tab id in `customer-dashboard.tsx` and update the tab label string. The tab content component swap from `LiveFeedTab` to `CreateVideoTab` happens simultaneously.

---

## File Structure

```
Project/
  components/
    customer-dashboard.tsx          ← keep; update tab label + swap component ref
    dashboard/
      CreateVideoTab.tsx            ← new; replaces LiveFeedTab.tsx
      create-video/
        CreateVideoSetupStep.tsx    ← new; Step 1 layout
        CreateVideoModeCards.tsx    ← new; 3 mode option cards
        CreateVideoSummaryPanel.tsx ← new; live right-side summary
        CreateVideoReviewStep.tsx   ← new; Step 2 layout (demo-backed)
        CreateVideoRenderStep.tsx   ← new; Step 3 layout (adapter-backed)
      personas/
        TikTokChannelCard.tsx       ← new; per-persona TikTok status card
      PersonasTab.tsx               ← keep; extend incrementally
      LiveFeedTab.tsx               ← keep for now; deprecate after CreateVideoTab ships
  types/
    video-planning.ts               ← new; frontend view models only
```

---

## Frontend Types — `video-planning.ts`

These are **view model types only** — not assumed backend contracts. They exist so components have typed interfaces now, and can be wired to real API responses in Phase 3 without restructuring the components.

```typescript
// Video creation modes
export type VideoCreationMode = 'ai_auto' | 'ai_remote' | 'human_phone'

export type ModeReadiness = 'ready' | 'coming_later'

export interface CreateVideoModeViewModel {
  id: VideoCreationMode
  title: string
  description: string
  badge: string
  readiness: ModeReadiness
  note?: string
}

// Step 1 setup form state
export interface CreateVideoSetupState {
  sourceUrl: string
  urlValidationStatus: 'idle' | 'validating' | 'valid' | 'invalid'
  urlValidationMessage?: string
  selectedPersonaIds: string[]
  objective: string
  brief?: string
  selectedMode: VideoCreationMode
}

// Step 2 persona review card
export type PlanCardStatus = 'loading' | 'demo' | 'ready' | 'approved' | 'rejected' | 'pending_backend'

export interface PersonaPlanCardViewModel {
  personaId: string
  personaName: string
  personaAvatarUrl?: string
  scriptPreview: string
  scenes: ScenePreviewItem[]
  status: PlanCardStatus
}

export interface ScenePreviewItem {
  index: number
  description: string
  durationSeconds?: number
}

// Step 3 render progress
export type RenderStatus = 'queued' | 'in_progress' | 'completed' | 'failed' | 'pending_backend'

export interface CreateVideoProgressViewModel {
  personaId: string
  personaName: string
  status: RenderStatus
  progressPercent?: number
  outputPreviewUrl?: string
  timelineEvents: RenderTimelineEvent[]
}

export interface RenderTimelineEvent {
  label: string
  timestamp?: string
  status: 'done' | 'active' | 'pending'
}

// Personas tab — TikTok channel
export type TikTokChannelActive = 'active' | 'inactive'
export type TikTokConnectionState = 'connected_demo' | 'not_connected' | 'needs_reconnect'

export interface TikTokChannelStatusViewModel {
  personaId: string
  activeState: TikTokChannelActive
  connectionState: TikTokConnectionState
  channelHandle?: string
  displayName?: string
  lastSyncLabel?: string
}
```

---

## Demo Adapter Layer

Introduce a small adapter file per feature area. These adapters convert current API responses (or hardcoded demo fixtures) into the view model types above. In Phase 3, replace the adapter internals — the component interfaces stay the same.

```
Project/
  adapters/
    create-video-adapter.ts   ← maps /jobs response → PersonaPlanCardViewModel[]
    tiktok-adapter.ts         ← maps persona data → TikTokChannelStatusViewModel
```

**Adapter pattern example:**

```typescript
// create-video-adapter.ts
import type { PersonaPlanCardViewModel } from '@/types/video-planning'

// Phase 1: demo fixtures
// Phase 3: replace body with real API response mapping
export function toPersonaPlanCards(
  rawJobs: unknown[]
): PersonaPlanCardViewModel[] {
  return DEMO_PLAN_CARDS // swap with real mapping in Phase 3
}

const DEMO_PLAN_CARDS: PersonaPlanCardViewModel[] = [
  {
    personaId: 'demo-1',
    personaName: 'Persona A',
    scriptPreview: 'Script preview text goes here...',
    scenes: [
      { index: 1, description: 'Opening hook', durationSeconds: 5 },
      { index: 2, description: 'Product feature', durationSeconds: 12 },
      { index: 3, description: 'Call to action', durationSeconds: 4 },
    ],
    status: 'demo',
  },
]
```

---

## Create Video Tab — Component Specs

### `CreateVideoTab.tsx`

Owns step state and navigation. No other component manages step transitions.

```typescript
type Step = 1 | 2 | 3

const [currentStep, setCurrentStep] = useState<Step>(1)
const [setupState, setSetupState] = useState<CreateVideoSetupState>(defaultSetupState)
const [planCards, setPlanCards] = useState<PersonaPlanCardViewModel[]>([])
const [progressItems, setProgressItems] = useState<CreateVideoProgressViewModel[]>([])
```

Renders:
- Step indicator (3 steps, current step highlighted)
- Conditional render: `<CreateVideoSetupStep>` | `<CreateVideoReviewStep>` | `<CreateVideoRenderStep>`

Step progression rules:
- Step 1 → Step 2: requires `urlValidationStatus === 'valid'` and `selectedPersonaIds.length > 0`
- Step 2 → Step 3: requires at least one plan card approved
- Back navigation: always allowed, state is preserved

---

### `CreateVideoSetupStep.tsx` — Step 1

**Layout (desktop):** Two-column. Left: form. Right: live summary panel.
**Layout (mobile 375px+):** Single column. Summary panel below form.

**Left form — field order:**

1. **Source URL** — text input, full width, real-time validation on blur
   - Calls existing `/api/customer/review-engine/source/validate`
   - Shows inline validation result (valid domain summary or error message)
   - Status indicator: idle / validating spinner / green check / red error

2. **Personas** — multi-select component, pulls from existing persona data in dashboard state
   - Shows persona avatar + name per option
   - Empty state: "No personas available — create one in the Personas tab"

3. **Video Objective** — textarea, required, max 200 chars, character counter

4. **Brief** — textarea, optional, max 500 chars, character counter, collapsible

5. **Mode** — `<CreateVideoModeCards>` (see below)

6. **Continue CTA** — primary button, full width on mobile
   - Label: "Review Plan"
   - Disabled state: url not valid OR no personas selected
   - Disabled reason shown below button as inline text (not tooltip)

**Right summary panel:**

```
┌─────────────────────────────────┐
│  Summary                        │
│                                 │
│  Source      [domain or —]      │
│  Validation  [status label]     │
│  Personas    [count or —]       │
│  Mode        [mode label or —]  │
│                                 │
│  Next step: Review your plan    │
└─────────────────────────────────┘
```

Summary updates live as the form changes. No submit needed to see summary.

---

### `CreateVideoModeCards.tsx` — Mode Selector

Render 3 cards horizontally on desktop, stacked on mobile.

**Mode definitions (hardcoded in component for Phase 1):**

```typescript
const MODES: CreateVideoModeViewModel[] = [
  {
    id: 'ai_auto',
    title: 'AI tự quay',
    description: 'AI handles the full recording and assembly process automatically.',
    badge: 'Default',
    readiness: 'ready',
  },
  {
    id: 'ai_remote',
    title: 'AI quay từ máy tính',
    description: 'AI operates a remote computer session to record content.',
    badge: 'Coming later',
    readiness: 'coming_later',
    note: 'Requires website login and remote recording handoff.',
  },
  {
    id: 'human_phone',
    title: 'Người quay từ điện thoại',
    description: 'Human captures footage on a phone, then AI assembles the final video.',
    badge: 'Coming later',
    readiness: 'coming_later',
    note: 'Human-captured footage from phone, then AI assembles the final video.',
  },
]
```

**Card visual spec:**

- Selected: `border: 2px solid var(--color-border-info)` — same as other elevated cards
- Unselected: `border: 0.5px solid var(--color-border-tertiary)`
- `readiness === 'coming_later'`: reduced opacity (0.6), cursor pointer disabled, click does nothing
- `readiness === 'coming_later'` badge: amber/warning pill
- `readiness === 'ready'` badge: success/green pill
- Mode 1 is default selected on mount
- Mode 2 and 3 are visually present but non-interactive for Phase 1

**Card content layout:**

```
┌──────────────────────────────────┐
│  [Badge pill]                    │
│                                  │
│  [Mode title — 500 weight]       │
│  [One-line description — muted]  │
│                                  │
│  [Note text if present — 12px]   │
└──────────────────────────────────┘
```

No icons. No emoji. Consistent padding 16px.

---

### `CreateVideoReviewStep.tsx` — Step 2

Renders one `PersonaPlanCard` per selected persona.

**Phase 1 data source:** `toPersonaPlanCards()` from `create-video-adapter.ts` (demo fixtures)

**PersonaPlanCard layout:**

```
┌──────────────────────────────────────────────────┐
│  [Avatar] [Persona Name]         [Status badge]  │
│  ─────────────────────────────────────────────   │
│  Script preview                                  │
│  [Truncated script text, 3 lines, expand toggle] │
│                                                  │
│  Scenes                                          │
│  1. Opening hook               (5s)              │
│  2. Product feature            (12s)             │
│  3. Call to action             (4s)              │
│                                                  │
│  [Reject]           [Edit]           [Approve]   │
└──────────────────────────────────────────────────┘
```

**Status badge values:**

| `status` value | Badge label | Color |
|---|---|---|
| `loading` | Loading... | gray |
| `demo` | Demo | amber |
| `ready` | Ready to review | blue |
| `approved` | Approved | green |
| `rejected` | Rejected | red |
| `pending_backend` | Pending backend | gray |

**Action buttons:**

- Reject → sets card status to `rejected`; card collapses but stays visible
- Edit → opens inline edit panel (Phase 1: text edit of script preview only)
- Approve → sets card status to `approved`

Continue to Step 3 CTA appears at the bottom when at least one card is approved. Label: "Start Render".

---

### `CreateVideoRenderStep.tsx` — Step 3

Renders one progress card per approved persona plan.

**Phase 1 data source:** Simulated progress via `setTimeout` chain in the adapter. No real render API call.

**Progress card layout:**

```
┌──────────────────────────────────────────────────┐
│  [Avatar] [Persona Name]         [Status badge]  │
│                                                  │
│  Timeline                                        │
│  ● Plan submitted        12:04 PM     [done]     │
│  ● Render queued         12:04 PM     [done]     │
│  ◌ Processing...                      [active]   │
│  ○ Output ready                       [pending]  │
│                                                  │
│  [Output preview area or placeholder]            │
│                                                  │
│  Ready for backend integration                   │
└──────────────────────────────────────────────────┘
```

Timeline dot states:
- `done` — filled dot, muted label
- `active` — animated pulse dot, primary text
- `pending` — empty dot, hint text

Output preview: `<img>` if `outputPreviewUrl` is set, otherwise a placeholder card with label "Preview available after render".

Final state label: "Ready for backend integration" — shown when status is `completed` or `pending_backend`. This communicates clearly to both users and the dev team that this state is a handoff point.

---

## Personas Tab — TikTok Channel Card

### `TikTokChannelCard.tsx`

Add this card to `PersonasTab.tsx` inside each persona detail view. Do not replace any existing persona editing UI — append below it.

**Card layout:**

```
┌───────────────────────────────────────────────────┐
│  TikTok Channel                                   │
│                                                   │
│  Status        [Active pill] or [Inactive pill]   │
│  Connection    [Connected (demo)] or [Not conn.]  │
│  Handle        @channelhandle                     │
│  Display name  Channel Display Name               │
│  Last check    —                                  │
│                                                   │
│  [Primary action button]                          │
└───────────────────────────────────────────────────┘
```

**Status pill values:**

| `activeState` | Pill label | Color |
|---|---|---|
| `active` | Active | green |
| `inactive` | Inactive | gray |

**Connection pill values:**

| `connectionState` | Pill label | Color |
|---|---|---|
| `connected_demo` | Connected (demo) | amber |
| `not_connected` | Not connected | gray |
| `needs_reconnect` | Needs reconnect | red |

**Primary action button logic (Phase 1 — all actions are demo/no-op):**

| `activeState` | `connectionState` | Button label |
|---|---|---|
| `inactive` | any | Activate channel |
| `active` | `not_connected` | Connect TikTok |
| `active` | `needs_reconnect` | Reconnect TikTok |
| `active` | `connected_demo` | View connection details |

All button clicks in Phase 1 should show a non-blocking inline message: "This action will be available once the backend integration is complete." — use a dismissible inline banner, not a modal.

**Data source (Phase 1):** `toTikTokChannelStatus(persona)` from `tiktok-adapter.ts` — returns demo fixture keyed by persona ID.

---

## Empty, Loading, and Error States

Every major surface must define these explicitly. No raw blank areas.

| Surface | Empty state | Loading state | Error state |
|---|---|---|---|
| Persona multi-select | "No personas yet — create one in the Personas tab." | Skeleton rows | "Failed to load personas. Refresh to retry." |
| URL validation | — | Spinner + "Validating source..." | Inline red message with error text |
| Review step plan cards | "No personas selected. Go back to Step 1." | Skeleton cards (same shape as real cards) | "Could not load plan. Using demo data." |
| Render progress | "No approved plans yet." | Progress card with active pulse | "Render status unavailable — check back later." |
| TikTok channel card | "No channel configured." | Skeleton card | "Could not load channel info." |

Error copy rules:
- No raw API exception strings in primary UI
- Include one recovery action when possible (retry, go back, refresh)
- Errors are inline — no full-page error states in this phase

---

## Implementation Phases

### Phase 1: UI Shell Refactor ← current

Checklist:
- [ ] Rename tab labels in `customer-dashboard.tsx`
- [ ] Swap `LiveFeedTab` ref to `CreateVideoTab` in dashboard shell
- [ ] Create `CreateVideoTab.tsx` with step state + step indicator
- [ ] Create `CreateVideoSetupStep.tsx` with form layout
- [ ] Create `CreateVideoModeCards.tsx` with 3 mode cards
- [ ] Create `CreateVideoSummaryPanel.tsx` (right panel)
- [ ] Validate URL input calls existing `/validate` endpoint
- [ ] Create `video-planning.ts` with all view model types
- [ ] Create demo adapter files

### Phase 2: Demo-State Completion

Checklist:
- [ ] Wire `CreateVideoReviewStep.tsx` to demo adapter data
- [ ] Wire `CreateVideoRenderStep.tsx` to simulated progress states
- [ ] Add `PersonaPlanCard` with approve/reject/edit interactions
- [ ] Add `TikTokChannelCard.tsx` to `PersonasTab`
- [ ] Add `tiktok-adapter.ts` with demo fixtures
- [ ] Complete all empty, loading, and error states
- [ ] Responsive QA at 375px, 768px, 1280px
- [ ] Accessibility audit: labels, focus rings, touch targets

### Phase 3: Backend Integration (deferred)

Wire list (each item replaces adapter internals — components stay unchanged):
- [ ] Replace `toPersonaPlanCards()` with real `/api/customer/review-engine/jobs` mapping
- [ ] Add plan persistence: save approved plan state to backend
- [ ] Add real render progress polling
- [ ] Add real TikTok OAuth connection + channel status fetch
- [ ] Integrate Mode 2 (AI remote) and Mode 3 (human phone) flows
- [ ] Add publishing orchestration step after render completes

---

## Definition of Done — This Phase

The UI refactor for Phase 1 and Phase 2 is complete when:

- [ ] The dashboard shows "Create Video" as the tab label — no "Live Feed" label visible
- [ ] Step 1 clearly communicates all 3 modes; Mode 1 is default selected; Mode 2 and Mode 3 are visible but non-interactive with clear "Coming later" labels
- [ ] Step 2 renders persona plan cards with demo data; approve, reject, and edit interactions work
- [ ] Step 3 renders simulated progress with a timeline per persona
- [ ] The Personas tab shows a TikTok Channel card per persona with correct active/inactive and connection state labels
- [ ] No blank or unstyled empty states anywhere
- [ ] All interactive targets are 44px minimum height
- [ ] Focus rings visible on keyboard navigation
- [ ] No hardcoded hex color values in component files
- [ ] Components are typed using `video-planning.ts` view models
- [ ] Adapters are isolated — no component imports raw API response types directly

---

## Next Document

After this UI phase is signed off, the next document should define the **backend integration contract** that maps to the frontend view models above:

- `PersonaPlanCardViewModel` ← real `video_render_plans` response shape
- `CreateVideoProgressViewModel` ← real render job status shape
- `TikTokChannelStatusViewModel` ← real channel connection state from OAuth layer
- Approval action → backend endpoint + optimistic UI pattern
- Publish action → backend endpoint + final state model

The backend contract must adapt to the frontend types defined here — not the other way around.