// Feature flags for gradual rollout and testing

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
  enableWorkflows: process.env.NEXT_PUBLIC_ENABLE_WORKFLOWS === "true",
  enableMediaGeneration: process.env.NEXT_PUBLIC_ENABLE_MEDIA_GEN === "true",

  // Advanced features
  enableEngagementNetwork: process.env.NEXT_PUBLIC_ENABLE_ENGAGEMENT === "true",
  enableTelegramApprovals: process.env.NEXT_PUBLIC_ENABLE_TELEGRAM === "true",
  enableAnalytics: process.env.NEXT_PUBLIC_ENABLE_ANALYTICS === "true",

  // UI features
  enableDarkMode: true, // Always enabled
};

export const isFeatureEnabled = (feature: keyof FeatureFlags): boolean => {
  return features[feature] ?? false;
};
