// Application-wide constants

export const APP_NAME = "AI Influencer Factory";
export const APP_VERSION = "0.1.0";
export const APP_DESCRIPTION = "AI-driven marketing orchestration platform";

// API Configuration
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:3000";
export const PYTHON_API_URL =
  process.env.PYTHON_BACKEND_URL || "http://localhost:8000";

// Supabase Configuration
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
export const SUPABASE_ANON_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

// Pagination
export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

// Content Generation
export const MAX_CONTENT_LENGTH = 5000;
export const MIN_CONTENT_LENGTH = 10;
export const MAX_TITLE_LENGTH = 200;

// Media
export const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB
export const ALLOWED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
];
export const ALLOWED_VIDEO_TYPES = [
  "video/mp4",
  "video/webm",
  "video/quicktime",
];

// Workflows
export const WORKFLOW_POLL_INTERVAL = 5000; // 5 seconds
export const MAX_WORKFLOW_RETRIES = 3;

// Engagement
export const MIN_ENGAGEMENT_DELAY = 60000; // 1 minute
export const MAX_ENGAGEMENT_DELAY = 3600000; // 1 hour

// Rate Limits
export const RATE_LIMIT_REQUESTS_PER_MINUTE = 60;
export const RATE_LIMIT_WINDOW_MS = 60000;

// Date Formats
export const DATE_FORMAT = "MMM dd, yyyy";
export const DATETIME_FORMAT = "MMM dd, yyyy HH:mm";
export const TIME_FORMAT = "HH:mm";

// Status Colors
export const STATUS_COLORS = {
  draft: "gray",
  pending_approval: "yellow",
  approved: "blue",
  scheduled: "purple",
  publishing: "orange",
  published: "green",
  failed: "red",
} as const;

// Temporal Configuration
export const TEMPORAL_NAMESPACE = "default";
export const TEMPORAL_TASK_QUEUE = "ai-influencer-tasks";
