export interface PublicEnv {
  NEXT_PUBLIC_API_URL: string;
  NEXT_PUBLIC_SUPABASE_URL: string;
  NEXT_PUBLIC_SUPABASE_ANON_KEY: string;
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: string;
  NEXT_PUBLIC_TELEGRAM_BOT_URL: string;
  NEXT_PUBLIC_TELEGRAM_BOT_USERNAME: string;
  NEXT_PUBLIC_ENABLE_WORKFLOWS: string;
  NEXT_PUBLIC_ENABLE_MEDIA_GEN: string;
  NEXT_PUBLIC_ENABLE_ENGAGEMENT: string;
  NEXT_PUBLIC_ENABLE_TELEGRAM: string;
  NEXT_PUBLIC_ENABLE_ANALYTICS: string;
}

export const DEFAULT_PUBLIC_ENV: PublicEnv = {
  NEXT_PUBLIC_API_URL: "http://localhost:3000",
  NEXT_PUBLIC_SUPABASE_URL: "",
  NEXT_PUBLIC_SUPABASE_ANON_KEY: "",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "",
  NEXT_PUBLIC_TELEGRAM_BOT_URL: "",
  NEXT_PUBLIC_TELEGRAM_BOT_USERNAME: "",
  NEXT_PUBLIC_ENABLE_WORKFLOWS: "false",
  NEXT_PUBLIC_ENABLE_MEDIA_GEN: "false",
  NEXT_PUBLIC_ENABLE_ENGAGEMENT: "false",
  NEXT_PUBLIC_ENABLE_TELEGRAM: "false",
  NEXT_PUBLIC_ENABLE_ANALYTICS: "false",
};

declare global {
  interface Window {
    __AI_INFLUENCER_PUBLIC_ENV__?: Partial<PublicEnv>;
  }
}

function getRuntimePublicEnvSource(): Partial<PublicEnv> {
  if (typeof globalThis !== "object") {
    return {};
  }

  const runtimeScope = globalThis as typeof globalThis & {
    __AI_INFLUENCER_PUBLIC_ENV__?: Partial<PublicEnv>;
  };
  const runtimeEnv = runtimeScope.__AI_INFLUENCER_PUBLIC_ENV__;

  if (!runtimeEnv || typeof runtimeEnv !== "object") {
    return {};
  }

  return runtimeEnv;
}

export function getClientPublicEnv(): PublicEnv {
  return {
    ...DEFAULT_PUBLIC_ENV,
    ...getRuntimePublicEnvSource(),
  };
}

export function getClientPublicEnvValue(key: keyof PublicEnv): string {
  return getClientPublicEnv()[key];
}

export function deriveTelegramBotUsername(value?: string | null): string {
  const normalized = value?.trim();
  if (!normalized) {
    return "";
  }

  try {
    const url = normalized.startsWith("http") ? normalized : `https://${normalized}`;
    const pathname = new URL(url).pathname.replace(/^\/+/, "");
    return pathname.split("/", 1)[0]?.replace(/^@/, "") || "";
  } catch {
    return normalized
      .replace(/^https?:\/\//, "")
      .replace(/^t\.me\//, "")
      .replace(/^@/, "")
      .split("/", 1)[0]
      ?.trim() || "";
  }
}
