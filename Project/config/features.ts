// Feature flags for gradual rollout and testing
import { getClientPublicEnvValue } from "@/lib/public-env";

export interface FeatureFlags {
  enableWorkflows: boolean;
  enableMediaGeneration: boolean;
  enableEngagementNetwork: boolean;
  enableTelegramApprovals: boolean;
  enableAnalytics: boolean;
  enableDarkMode: boolean;
}

export const features: FeatureFlags = {
  // Core features
  enableWorkflows: getClientPublicEnvValue("NEXT_PUBLIC_ENABLE_WORKFLOWS") === "true",
  enableMediaGeneration: getClientPublicEnvValue("NEXT_PUBLIC_ENABLE_MEDIA_GEN") === "true",

  // Advanced features
  enableEngagementNetwork:
    getClientPublicEnvValue("NEXT_PUBLIC_ENABLE_ENGAGEMENT") === "true",
  enableTelegramApprovals:
    getClientPublicEnvValue("NEXT_PUBLIC_ENABLE_TELEGRAM") === "true",
  enableAnalytics:
    getClientPublicEnvValue("NEXT_PUBLIC_ENABLE_ANALYTICS") === "true",

  // UI features
  enableDarkMode: true, // Always enabled
};

export const isFeatureEnabled = (feature: keyof FeatureFlags): boolean => {
  return features[feature] ?? false;
};
