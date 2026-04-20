export type ReviewEngineStep = {
  key: string;
  label: string;
  status?: string;
};

export type ReviewEngineChannel = {
  id?: string | null;
  display_name?: string | null;
  handle?: string | null;
  status?: string | null;
};

export type ReviewEngineTikTokIntegration = {
  status?: string | null;
  active_channels?: number;
  inactive_channels?: number;
  channels?: ReviewEngineChannel[];
};

export type ReviewEngineDemo = {
  available?: boolean;
  label?: string | null;
  summary?: string | null;
};

export type ReviewEnginePersonaOption = {
  persona_id: string;
  display_name: string;
  language?: string | null;
  region_label?: string | null;
  market_default?: string | null;
  tone_default?: string | null;
  description?: string | null;
  image_url?: string | null;
  selection_image_url?: string | null;
  is_preset?: boolean;
  is_preset_catalog?: boolean;
  demo?: ReviewEngineDemo | null;
  tiktok_integration?: ReviewEngineTikTokIntegration | null;
};

export type ReviewEngineSetup = {
  steps: ReviewEngineStep[];
  supported_languages: string[];
  persona_options: ReviewEnginePersonaOption[];
  custom_personas: ReviewEnginePersonaOption[];
  create_your_own?: {
    available?: boolean;
    label?: string | null;
  } | null;
  publishing_requirements?: {
    telegram_linked?: boolean;
    tiktok_channels_active?: boolean;
    tiktok_channels_total?: number;
  } | null;
};

export type ReviewEngineJob = {
  job_id: string;
  plan_id?: string | null;
  workflow_id?: string | null;
  run_id?: string | null;
  type?: string | null;
  status: string;
  current_step?: string | null;
  progress: number;
  input_mode?: string | null;
  activity_feed: ReviewEngineStep[];
  source_url?: string | null;
  objective?: string | null;
  page_title?: string | null;
  persona: {
    persona_id?: string | null;
    display_name?: string | null;
    language?: string | null;
    region_label?: string | null;
    image_url?: string | null;
    selection_image_url?: string | null;
    tiktok_integration?: ReviewEngineTikTokIntegration | null;
  };
  content: {
    title?: string | null;
    body?: string | null;
    content_id?: string | null;
    status?: string | null;
    published?: boolean;
  };
  production: {
    ready?: boolean;
    playable_video_url?: string | null;
    download_url?: string | null;
    media_asset_id?: string | null;
    publish_enabled?: boolean;
  };
  publish: {
    requested?: boolean;
    status?: string | null;
    published_at?: string | null;
    post_url?: string | null;
    publish_error?: string | null;
  };
  publish_settings?: {
    content_title?: string | null;
    caption_draft?: string | null;
    tiktok_channel_id?: string | null;
    input_mode?: string | null;
    uploaded_media_asset_id?: string | null;
  } | null;
  creative_preferences?: Record<string, unknown> | null;
  recording_script?: unknown;
  script?: {
    script?: string | null;
    scenes?: any[] | null;
  } | null;
  editable_content?: string | null;
  review_plan?: unknown;
  campaign_id?: string | null;
  persona_id?: string | null;
  target_platform?: string | null;
  created_at?: string | null;
  approved_at?: string | null;
  published_at?: string | null;
  scheduled_at?: string | null;
  updated_at?: string | null;
  started_at?: string | null;
};

export type ReviewEngineJobResponse = {
  jobs: ReviewEngineJob[];
};

export type ReviewEnginePlan = {
  plan_id: string;
  persona_id?: string | null;
  source_url?: string | null;
  objective?: string | null;
  script_text?: string | null;
  scenes_data?: any[] | null;
  status?: string | null;
  publish_settings?: Record<string, unknown> | null;
  creative_preferences?: Record<string, unknown> | null;
  workflow_id?: string | null;
  approved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ReviewEnginePlanListResponse = {
  plans: ReviewEnginePlan[];
};

export type ReviewEngineSourceValidateResponse = {
  normalized_url: string;
  page_title: string;
  suggested_objective?: string | null;
  visible_features: any[];
  page_review_data?: Record<string, unknown>;
};

export function getReviewJobTone(
  job: Pick<ReviewEngineJob, "status" | "publish" | "production">,
): "default" | "success" | "warning" {
  if (job.publish?.status === "published") {
    return "success";
  }
  if (job.status === "failed" || job.publish?.status === "failed") {
    return "warning";
  }
  if (job.production?.ready) {
    return "success";
  }
  return "default";
}

export function getReviewJobStatusLabel(job: ReviewEngineJob): string {
  if (job.publish?.status === "published") {
    return "Published";
  }
  if (job.production?.ready) {
    return "Ready";
  }
  if (job.status === "failed") {
    return "Failed";
  }
  if (job.current_step) {
    return job.current_step.replace(/_/g, " ");
  }
  return job.status.replace(/_/g, " ");
}

export function getReviewJobPersonaImage(job: ReviewEngineJob): string | null {
  return job.persona?.selection_image_url || job.persona?.image_url || null;
}
