/**
 * video-planning.ts
 * Create-video view models for canonical web flow.
 */

// ---------------------------------------------------------------------------
// Video creation modes
// ---------------------------------------------------------------------------

export type VideoCreationMode = 'ai_auto' | 'ai_remote' | 'human_phone';
export type BackendInputMode = 'ai_autonomous' | 'user_upload';

export type ModeReadiness = 'ready' | 'coming_later';

export interface CreateVideoModeViewModel {
  id: VideoCreationMode;
  title: string;
  description: string;
  badge: string;
  readiness: ModeReadiness;
  note?: string;
}

export interface ValidationFeatureViewModel {
  label: string;
  summary?: string;
  sourceUrl?: string;
  evidence?: string[];
}

export interface PageReviewPayload {
  target_url?: string;
  normalized_url: string;
  page_title?: string | null;
  product_summary?: string;
  page_fetch_method?: string;
  access_level?: string;
  login_required?: boolean;
  visible_features?: Array<{
    label: string;
    summary: string;
    source_url?: string | null;
    evidence?: string[];
  }>;
  visible_flows?: Array<{
    label: string;
    summary: string;
    source_url?: string | null;
    evidence?: string[];
  }>;
  recording_candidates?: string[];
  risks?: string[];
  assumptions?: string[];
  suggested_objective?: string | null;
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
    visibleFeatures?: ValidationFeatureViewModel[];
    pageReviewData?: PageReviewPayload;
  };
  selectedPersonaIds: string[];
  objective: string;
  brief?: string;
  selectedMode: VideoCreationMode;
  selectedMovementStyle: string;
  gestureIntensity: number;
  selectedMusicMood: string;
  musicVolume: number;
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
  selectedMovementStyle: 'Natural',
  gestureIntensity: 50,
  selectedMusicMood: 'None',
  musicVolume: 70,
};

// ---------------------------------------------------------------------------
// Step 2 — Persona plan review cards
// ---------------------------------------------------------------------------

export type PlanReviewDecision = 'pending' | 'approved' | 'rejected';
export type ViewTone = 'default' | 'success' | 'warning';

export interface ScenePreviewItem {
  index: number;
  description: string;
  durationSeconds?: number;
}

export interface SharedContractDraft {
  scriptText: string;
  scenesText: string;
}

export interface PersonaPlanCardViewModel {
  jobId: string;
  planId?: string | null;
  workflowId?: string | null;
  personaId: string;
  personaName: string;
  personaLanguage?: string | null;
  personaAvatarUrl?: string;
  sourceUrl?: string | null;
  objective?: string | null;
  inputMode?: BackendInputMode | null;
  inputModeLabel: string;
  backendStatus: string;
  backendStatusLabel: string;
  statusTone: ViewTone;
  reviewDecision: PlanReviewDecision;
  requiresUpload: boolean;
  outputReady: boolean;
  scriptPreview: string;
  scenes: ScenePreviewItem[];
}

// ---------------------------------------------------------------------------
// Step 3 — Render progress
// ---------------------------------------------------------------------------

export type RenderStatus =
  | 'queued'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'upload_required';

export interface RenderTimelineEvent {
  label: string;
  timestamp?: string;
  status: 'done' | 'active' | 'pending';
}

export interface CreateVideoProgressViewModel {
  jobId: string;
  planId?: string | null;
  workflowId?: string | null;
  personaId: string;
  personaName: string;
  personaAvatarUrl?: string;
  status: RenderStatus;
  statusLabel: string;
  statusTone: ViewTone;
  progressPercent?: number;
  playableVideoUrl?: string | null;
  downloadUrl?: string | null;
  readyToPublish: boolean;
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
