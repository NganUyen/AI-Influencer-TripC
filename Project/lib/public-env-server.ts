import {
  DEFAULT_PUBLIC_ENV,
  deriveTelegramBotUsername,
  type PublicEnv,
} from "@/lib/public-env";

export const RUNTIME_PUBLIC_ENV_ROUTE = "/api/runtime-config";

function readProcessEnvValue(key: string): string {
  const value = process.env?.[key];
  return typeof value === "string" ? value : "";
}

export function getServerPublicEnv(): PublicEnv {
  const telegramBotUrl = readProcessEnvValue("NEXT_PUBLIC_TELEGRAM_BOT_URL");
  const telegramBotUsername =
    readProcessEnvValue("NEXT_PUBLIC_TELEGRAM_BOT_USERNAME") ||
    deriveTelegramBotUsername(telegramBotUrl);

  return {
    NEXT_PUBLIC_API_URL:
      readProcessEnvValue("NEXT_PUBLIC_API_URL") ||
      readProcessEnvValue("FRONTEND_PUBLIC_URL") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_SUPABASE_URL:
      readProcessEnvValue("NEXT_PUBLIC_SUPABASE_URL") ||
      readProcessEnvValue("SUPABASE_URL") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY:
      readProcessEnvValue("NEXT_PUBLIC_SUPABASE_ANON_KEY") ||
      readProcessEnvValue("SUPABASE_KEY") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:
      readProcessEnvValue("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") ||
      readProcessEnvValue("SUPABASE_PUBLISHABLE_KEY") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    NEXT_PUBLIC_TELEGRAM_BOT_URL:
      telegramBotUrl || DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_TELEGRAM_BOT_URL,
    NEXT_PUBLIC_TELEGRAM_BOT_USERNAME:
      telegramBotUsername || DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME,
    NEXT_PUBLIC_ENABLE_WORKFLOWS:
      readProcessEnvValue("NEXT_PUBLIC_ENABLE_WORKFLOWS") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_ENABLE_WORKFLOWS,
    NEXT_PUBLIC_ENABLE_MEDIA_GEN:
      readProcessEnvValue("NEXT_PUBLIC_ENABLE_MEDIA_GEN") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_ENABLE_MEDIA_GEN,
    NEXT_PUBLIC_ENABLE_ENGAGEMENT:
      readProcessEnvValue("NEXT_PUBLIC_ENABLE_ENGAGEMENT") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_ENABLE_ENGAGEMENT,
    NEXT_PUBLIC_ENABLE_TELEGRAM:
      readProcessEnvValue("NEXT_PUBLIC_ENABLE_TELEGRAM") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_ENABLE_TELEGRAM,
    NEXT_PUBLIC_ENABLE_ANALYTICS:
      readProcessEnvValue("NEXT_PUBLIC_ENABLE_ANALYTICS") ||
      DEFAULT_PUBLIC_ENV.NEXT_PUBLIC_ENABLE_ANALYTICS,
  };
}
