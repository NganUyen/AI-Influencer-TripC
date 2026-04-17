/**
 * video-planning.ts
 * Frontend view model types for the Create Video workflow.
 * These are presentation-layer types ONLY — not assumed backend contracts.
 * In Phase 3, replace adapter internals to map real API shapes to these types.
 */

// ---------------------------------------------------------------------------
// Video creation modes
// ---------------------------------------------------------------------------

export type VideoCreationMode = 'ai_auto' | 'ai_remote' | 'human_phone';

export type ModeReadiness = 'ready' | 'coming_later';

export interface CreateVideoModeViewModel {
  id: VideoCreationMode;
  title: string;
  description: string;
  badge: string;
  readiness: ModeReadiness;
  note?: string;
}

// ---------------------------------------------------------------------------
// Step 1 — Setup form state
// ---------------------------------------------------------------------------

export interface CreateVideoSetupState {
  sourceUrl: string;
  urlValidationStatus: 'idle' | 'validating' | 'valid' | 'invalid';
  urlValidationMessage?: string;
  urlValidationDetails?: {
    normalizedUrl?: string;
    pageTitle?: string;
    suggestedObjective?: string | null;
    visibleFeatureCount?: number;
  };
  selectedPersonaIds: string[];
  objective: string;
  brief?: string;
  selectedMode: VideoCreationMode;
  selectedBackground: string;
  selectedMovementStyle: string;
  selectedMusicMood: string;
}

export const DEFAULT_SETUP_STATE: CreateVideoSetupState = {
  sourceUrl: '',
  urlValidationStatus: 'idle',
  urlValidationMessage: undefined,
  urlValidationDetails: undefined,
  selectedPersonaIds: [],
  objective: '',
  brief: '',
  selectedMode: 'ai_auto',
  selectedBackground: 'studio-soft',
  selectedMovementStyle: 'Natural',
  selectedMusicMood: 'None',
};

// ---------------------------------------------------------------------------
// Step 2 — Persona plan review cards
// ---------------------------------------------------------------------------

export type PlanCardStatus =
  | 'loading'
  | 'demo'
  | 'ready'
  | 'approved'
  | 'rejected'
  | 'pending_backend';

export interface ScenePreviewItem {
  index: number;
  description: string;
  durationSeconds?: number;
}

export interface PersonaPlanCardViewModel {
  personaId: string;
  personaName: string;
  personaAvatarUrl?: string;
  scriptPreview: string;
  scenes: ScenePreviewItem[];
  status: PlanCardStatus;
}

// ---------------------------------------------------------------------------
// Step 3 — Render progress
// ---------------------------------------------------------------------------

export type RenderStatus =
  | 'queued'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'pending_backend';

export interface RenderTimelineEvent {
  label: string;
  timestamp?: string;
  status: 'done' | 'active' | 'pending';
}

export interface CreateVideoProgressViewModel {
  personaId: string;
  personaName: string;
  personaAvatarUrl?: string;
  status: RenderStatus;
  progressPercent?: number;
  outputPreviewUrl?: string;
  timelineEvents: RenderTimelineEvent[];
}

// ---------------------------------------------------------------------------
// Personas tab — TikTok channel
// ---------------------------------------------------------------------------

export type TikTokChannelActive = 'active' | 'inactive';
export type TikTokConnectionState =
  | 'connected_demo'
  | 'not_connected'
  | 'needs_reconnect';

export interface TikTokChannelStatusViewModel {
  personaId: string;
  activeState: TikTokChannelActive;
  connectionState: TikTokConnectionState;
  channelHandle?: string;
  displayName?: string;
  lastSyncLabel?: string;
}
