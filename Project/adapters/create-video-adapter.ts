import {
  getReviewJobStatusLabel,
  getReviewJobTone,
  type ReviewEngineJob,
} from '@/lib/review-engine';
import type {
  BackendInputMode,
  CreateVideoProgressViewModel,
  CreateVideoSetupState,
  PersonaPlanCardViewModel,
  RenderStatus,
  RenderTimelineEvent,
  VideoCreationMode,
  ViewTone,
} from '@/types/video-planning';
import { resolveCountryCode } from '@/lib/country-mapping';
import {
  getGestureStyleOption,
  getMusicMoodOption,
} from '@/components/dashboard/create-video/setup-options';

export const CREATE_VIDEO_UI_TO_BACKEND_MODE: Record<
  VideoCreationMode,
  BackendInputMode | null
> = {
  ai_auto: 'ai_autonomous',
  ai_remote: null,
  human_phone: 'user_upload',
};

const INPUT_MODE_LABELS: Record<BackendInputMode, string> = {
  ai_autonomous: 'AI Auto-Record',
  user_upload: 'Human Phone Recording',
};

function normalizeInputMode(value: unknown): BackendInputMode | null {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'ai_autonomous' || normalized === 'user_upload') {
    return normalized;
  }
  return null;
}

function toInputModeLabel(value: BackendInputMode | null): string {
  if (!value) {
    return 'Unknown mode';
  }
  return INPUT_MODE_LABELS[value];
}

function toViewTone(value: ReturnType<typeof getReviewJobTone>): ViewTone {
  if (value === 'success') {
    return 'success';
  }
  if (value === 'warning') {
    return 'warning';
  }
  return 'default';
}

function extractSceneDescription(scene: unknown, index: number): string {
  if (!scene || typeof scene !== 'object') {
    return `Scene ${index + 1}`;
  }
  const payload = scene as Record<string, unknown>;
  return String(
    payload.description ||
      payload.caption ||
      payload.scene_description ||
      payload.voiceover ||
      payload.script ||
      payload.text ||
      payload.prompt ||
      `Scene ${index + 1}`,
  ).trim();
}

function extractSceneDuration(scene: unknown): number | undefined {
  if (!scene || typeof scene !== 'object') {
    return undefined;
  }
  const payload = scene as Record<string, unknown>;
  const directDuration = Number(
    payload.durationSeconds ?? payload.duration_seconds ?? payload.duration,
  );
  if (Number.isFinite(directDuration) && directDuration > 0) {
    return directDuration;
  }
  const start = Number(payload.timestamp_start ?? payload.start_time ?? payload.start);
  const end = Number(payload.timestamp_end ?? payload.end_time ?? payload.end);
  if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
    return end - start;
  }
  return undefined;
}

function buildScenePreviewItems(job: ReviewEngineJob) {
  const scenes = Array.isArray(job.script?.scenes) ? job.script?.scenes : [];
  return scenes.map((scene, index) => ({
    index: index + 1,
    description: extractSceneDescription(scene, index),
    durationSeconds: extractSceneDuration(scene),
  }));
}

function mapTimelineStatus(value: string | undefined): RenderTimelineEvent['status'] {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'completed' || normalized === 'done') {
    return 'done';
  }
  if (
    normalized === 'active' ||
    normalized === 'in_progress' ||
    normalized === 'running' ||
    normalized === 'current'
  ) {
    return 'active';
  }
  return 'pending';
}

function buildTimelineEvents(job: ReviewEngineJob): RenderTimelineEvent[] {
  const steps = Array.isArray(job.activity_feed) ? job.activity_feed : [];
  if (steps.length > 0) {
    return steps.map((step) => ({
      label: step.label,
      status: mapTimelineStatus(step.status),
    }));
  }

  const fallbackLabel = getReviewJobStatusLabel(job);
  return [
    {
      label: fallbackLabel || 'Waiting for backend update',
      status: job.production?.ready ? 'done' : 'active',
    },
  ];
}

function getJobFailureMessage(job: ReviewEngineJob): string | null {
  return (
    String(job.status_message || '').trim() ||
    String(job.failure_details?.message || '').trim() ||
    String(job.error_detail || '').trim() ||
    null
  );
}

function toRenderStatus(job: ReviewEngineJob): RenderStatus {
  const normalizedStatus = String(job.status || '').trim().toLowerCase();
  if (normalizedStatus === 'upload_required') {
    return 'upload_required';
  }
  if (normalizedStatus === 'failed' || job.publish?.status === 'failed') {
    return 'failed';
  }
  if (job.production?.ready) {
    return 'completed';
  }
  if (
    normalizedStatus === 'approved' ||
    normalizedStatus === 'running' ||
    normalizedStatus === 'in_progress' ||
    Boolean(job.workflow_id) ||
    Boolean(job.current_step)
  ) {
    return 'in_progress';
  }
  return 'queued';
}

export function isCreateVideoModeSupportedForSubmit(
  mode: VideoCreationMode,
): boolean {
  return CREATE_VIDEO_UI_TO_BACKEND_MODE[mode] !== null;
}

export function buildCreativePreferences(
  setupState: CreateVideoSetupState,
): Record<string, unknown> {
  const gestureOption = getGestureStyleOption(setupState.selectedMovementStyle);
  const musicMoodOption = getMusicMoodOption(setupState.selectedMusicMood);
  const payload: Record<string, unknown> = {
    movement_style: setupState.selectedMovementStyle,
    gesture_intensity: setupState.gestureIntensity,
    music_mood: setupState.selectedMusicMood,
    music_volume: setupState.musicVolume,
    movement_profile: gestureOption?.movementProfile || 'natural',
    bgm_profile: musicMoodOption?.bgmProfile || 'product_explainer',
  };
  const brief = String(setupState.brief || '').trim();
  if (brief) {
    payload.brief = brief;
  }
  return payload;
}

export function buildCreateJobPayload(
  setupState: CreateVideoSetupState,
): {
  source_url: string;
  objective: string;
  target_personas: string[];
  input_mode: BackendInputMode;
  publish_to_tiktok: boolean;
  creative_preferences: Record<string, unknown>;
  page_review_data?: Record<string, unknown>;
} {
  const inputMode = CREATE_VIDEO_UI_TO_BACKEND_MODE[setupState.selectedMode];
  if (!inputMode) {
    throw new Error('Selected mode is not supported yet.');
  }
  const sourceUrl =
    setupState.urlValidationDetails?.normalizedUrl?.trim() ||
    setupState.sourceUrl.trim();
  const objective =
    setupState.objective.trim() ||
    setupState.urlValidationDetails?.suggestedObjective?.trim() ||
    'Product review';
  const pageReviewData = setupState.urlValidationDetails?.pageReviewData as
    | Record<string, unknown>
    | undefined;
  return {
    source_url: sourceUrl,
    objective,
    target_personas: setupState.selectedPersonaIds,
    input_mode: inputMode,
    publish_to_tiktok: false,
    creative_preferences: buildCreativePreferences(setupState),
    ...(pageReviewData ? { page_review_data: pageReviewData } : {}),
  };
}

export function toPersonaPlanCards(
  jobs: ReviewEngineJob[],
): PersonaPlanCardViewModel[] {
  return jobs.map((job) => {
    const inputMode = normalizeInputMode(
      job.input_mode || job.publish_settings?.input_mode,
    );
    const backendStatus = String(job.status || '').trim().toLowerCase() || 'generated';
    return {
      jobId: job.job_id,
      planId: job.plan_id,
      workflowId: job.workflow_id,
      personaId: String(job.persona?.persona_id || job.persona_id || job.job_id),
      personaName: String(
        job.persona?.display_name || job.persona?.persona_id || job.persona_id || 'Persona',
      ),
      personaLanguage: job.persona?.language || null,
      personaRegionLabel: job.persona?.region_label || null,
      personaMarketDefault: job.persona?.market_default || null,
      personaCountryCode: resolveCountryCode(
        job.persona?.country_code || job.persona?.region_label || job.persona?.market_default,
      ),
      personaAvatarUrl:
        job.persona?.selection_image_url || job.persona?.image_url || undefined,
      sourceUrl: job.source_url,
      objective: job.objective,
      inputMode,
      inputModeLabel: toInputModeLabel(inputMode),
      backendStatus,
      backendStatusLabel: getReviewJobStatusLabel(job),
      statusTone: toViewTone(getReviewJobTone(job)),
      reviewDecision:
        backendStatus === 'approved' ||
        backendStatus === 'completed' ||
        backendStatus === 'in_progress' ||
        Boolean(job.workflow_id)
          ? 'approved'
          : 'pending',
      requiresUpload: inputMode === 'user_upload' && !Boolean(job.production?.ready),
      outputReady: Boolean(job.production?.ready),
      scriptPreview:
        String(job.script?.script || job.editable_content || job.content?.body || '').trim(),
      scenes: buildScenePreviewItems(job),
      lastErrorMessage: getJobFailureMessage(job),
    };
  });
}

export function toRenderProgressItems(
  jobs: ReviewEngineJob[],
): CreateVideoProgressViewModel[] {
  return jobs.map((job) => ({
    jobId: job.job_id,
    planId: job.plan_id,
    workflowId: job.workflow_id,
    personaId: String(job.persona?.persona_id || job.persona_id || job.job_id),
    personaName: String(
      job.persona?.display_name || job.persona?.persona_id || job.persona_id || 'Persona',
    ),
    personaAvatarUrl:
      job.persona?.selection_image_url || job.persona?.image_url || undefined,
    status: toRenderStatus(job),
    statusLabel: getReviewJobStatusLabel(job),
    statusTone: toViewTone(getReviewJobTone(job)),
    progressPercent: job.progress,
    playableVideoUrl: job.production?.playable_video_url || null,
    downloadUrl: job.production?.download_url || null,
    readyToPublish: Boolean(
      job.production?.ready && job.production?.publish_enabled,
    ),
    timelineEvents: buildTimelineEvents(job),
    statusMessage: getJobFailureMessage(job),
  }));
}
