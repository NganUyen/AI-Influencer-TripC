// Common types
export type Platform =
  | "twitter"
  | "linkedin"
  | "facebook"
  | "instagram"
  | "tiktok"
  | "youtube";

export type ContentStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "scheduled"
  | "publishing"
  | "published"
  | "failed";

export type MediaType = "image" | "video" | "audio" | "document";

export interface User {
  id: string;
  email: string;
  name?: string;
  avatar?: string;
  createdAt: Date;
}

export interface ContentItem {
  id: string;
  userId: string;
  title: string;
  content: string;
  platforms: Platform[];
  status: ContentStatus;
  mediaUrls?: string[];
  scheduledAt?: Date;
  publishedAt?: Date;
  createdAt: Date;
  updatedAt: Date;
}

export interface Campaign {
  id: string;
  userId: string;
  name: string;
  description?: string;
  status: "active" | "paused" | "completed";
  startDate: Date;
  endDate?: Date;
  createdAt: Date;
  updatedAt: Date;
}

export interface MediaAsset {
  id: string;
  url: string;
  type: MediaType;
  filename: string;
  size: number;
  mimeType: string;
  createdAt: Date;
}

export interface InfluencerPersona {
  id: string;
  name: string;
  description: string;
  voice: string;
  platforms: Platform[];
  isActive: boolean;
  avatarUrl?: string;
  proxyConfig?: {
    host: string;
    port: number;
    username: string;
  };
  createdAt: Date;
  updatedAt: Date;
}

export interface WorkflowStatus {
  id: string;
  workflowId: string;
  type: "weekly_marketing" | "content_generation" | "distribution";
  status: "running" | "waiting_approval" | "completed" | "failed";
  currentStep: string;
  progress: number;
  startedAt: Date;
  completedAt?: Date;
  error?: string;
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}
