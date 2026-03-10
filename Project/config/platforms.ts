import { Platform } from "@/types";

export interface PlatformConfig {
  id: Platform;
  name: string;
  icon: string;
  color: string;
  maxLength: number;
  supportsImages: boolean;
  supportsVideos: boolean;
  supportsThreads: boolean;
  apiEndpoint?: string;
}

export const platformConfigs: Record<Platform, PlatformConfig> = {
  twitter: {
    id: "twitter",
    name: "Twitter / X",
    icon: "𝕏",
    color: "#000000",
    maxLength: 280,
    supportsImages: true,
    supportsVideos: true,
    supportsThreads: true,
  },
  linkedin: {
    id: "linkedin",
    name: "LinkedIn",
    icon: "in",
    color: "#0A66C2",
    maxLength: 3000,
    supportsImages: true,
    supportsVideos: true,
    supportsThreads: false,
  },
  facebook: {
    id: "facebook",
    name: "Facebook",
    icon: "f",
    color: "#1877F2",
    maxLength: 63206,
    supportsImages: true,
    supportsVideos: true,
    supportsThreads: false,
  },
  instagram: {
    id: "instagram",
    name: "Instagram",
    icon: "📷",
    color: "#E4405F",
    maxLength: 2200,
    supportsImages: true,
    supportsVideos: true,
    supportsThreads: false,
  },
  tiktok: {
    id: "tiktok",
    name: "TikTok",
    icon: "♪",
    color: "#000000",
    maxLength: 2200,
    supportsImages: false,
    supportsVideos: true,
    supportsThreads: false,
  },
  youtube: {
    id: "youtube",
    name: "YouTube",
    icon: "▶",
    color: "#FF0000",
    maxLength: 5000,
    supportsImages: false,
    supportsVideos: true,
    supportsThreads: false,
  },
};

export const getPlatformConfig = (platform: Platform): PlatformConfig => {
  return platformConfigs[platform];
};

export const getAllPlatforms = (): PlatformConfig[] => {
  return Object.values(platformConfigs);
};
