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

function normalizeTelegramUsername(value?: string | null): string {
  return value?.trim().replace(/^@/, "") || "";
}

export function deriveTelegramBotUsername(value?: string | null): string {
  const normalized = value?.trim();
  if (!normalized) {
    return "";
  }

  if (normalized.startsWith("tg://")) {
    const params = new URLSearchParams(normalized.split("?", 2)[1] || "");
    return normalizeTelegramUsername(params.get("domain"));
  }

  try {
    const url =
      normalized.startsWith("http") ||
      normalized.startsWith("tg://") ||
      normalized.startsWith("t.me/") ||
      normalized.startsWith("telegram.me/") ||
      normalized.startsWith("telegram.dog/")
        ? normalized
        : `https://${normalized}`;
    const pathname = new URL(url).pathname.replace(/^\/+/, "");
    return pathname.split("/", 1)[0]?.replace(/^@/, "") || "";
  } catch {
    return normalized
      .replace(/^https?:\/\//, "")
      .replace(/^tg:\/\/resolve\?domain=/, "")
      .replace(/^t\.me\//, "")
      .replace(/^telegram\.me\//, "")
      .replace(/^telegram\.dog\//, "")
      .replace(/^@/, "")
      .split(/[/?#&]/, 1)[0]
      ?.trim() || "";
  }
}

export function normalizeTelegramBotUrl(value?: string | null): string {
  const normalized = value?.trim();
  if (!normalized) {
    return "";
  }

  const username = deriveTelegramBotUsername(normalized);
  if (!username) {
    return "";
  }

  const browserUrl = new URL(`https://t.me/${username}`);

  if (normalized.startsWith("tg://")) {
    const params = new URLSearchParams(normalized.split("?", 2)[1] || "");
    params.delete("domain");
    for (const [key, entryValue] of params.entries()) {
      browserUrl.searchParams.set(key, entryValue);
    }
    return browserUrl.toString();
  }

  if (
    normalized.startsWith("http") ||
    normalized.startsWith("t.me/") ||
    normalized.startsWith("telegram.me/") ||
    normalized.startsWith("telegram.dog/")
  ) {
    try {
      const source = new URL(
        normalized.startsWith("http") ? normalized : `https://${normalized}`,
      );
      for (const [key, entryValue] of source.searchParams.entries()) {
        browserUrl.searchParams.set(key, entryValue);
      }
    } catch {
      return browserUrl.toString();
    }
  }

  return browserUrl.toString();
}

export function buildTelegramBotLaunchUrl({
  botUrl,
  botUsername,
  fallbackBotUsername,
  startToken,
}: {
  botUrl?: string | null;
  botUsername?: string | null;
  fallbackBotUsername?: string | null;
  startToken?: string | null;
} = {}): string | null {
  const normalizedBotUrl = normalizeTelegramBotUrl(botUrl);
  const normalizedBotUsername = normalizeTelegramUsername(botUsername);
  const normalizedFallbackBotUsername = normalizeTelegramUsername(fallbackBotUsername);
  const baseUrl =
    normalizedBotUrl ||
    (normalizedBotUsername ? `https://t.me/${normalizedBotUsername}` : "") ||
    (normalizedFallbackBotUsername
      ? `https://t.me/${normalizedFallbackBotUsername}`
      : "");

  if (!baseUrl) {
    return null;
  }

  const launchUrl = new URL(baseUrl);
  const normalizedStartToken = startToken?.trim();
  if (normalizedStartToken) {
    launchUrl.searchParams.set("start", normalizedStartToken);
  }

  return launchUrl.toString();
}

export function getClientTelegramBotLaunchUrl(
  startToken?: string | null,
  fallbackBotUsername?: string | null,
): string | null {
  return buildTelegramBotLaunchUrl({
    botUrl: getClientPublicEnvValue("NEXT_PUBLIC_TELEGRAM_BOT_URL"),
    botUsername: getClientPublicEnvValue("NEXT_PUBLIC_TELEGRAM_BOT_USERNAME"),
    fallbackBotUsername,
    startToken,
  });
}
