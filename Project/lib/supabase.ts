import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";

import { getClientPublicEnv } from "@/lib/public-env";

const fallbackUrl = "https://example.supabase.local";
const fallbackAnonKey = "public-anon-placeholder";

let cachedClient: SupabaseClient | null = null;
let cachedClientKey = "";

function getSupabasePublicConfig() {
  const env = getClientPublicEnv();
  const supabaseUrl = env.NEXT_PUBLIC_SUPABASE_URL.trim();
  const supabaseAnonKey = (
    env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
    env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ).trim();

  return {
    supabaseUrl,
    supabaseAnonKey,
    hasConfig: Boolean(supabaseUrl && supabaseAnonKey),
  };
}

export function hasSupabaseConfig(): boolean {
  return getSupabasePublicConfig().hasConfig;
}

export function getSupabaseClient(): SupabaseClient {
  const { hasConfig, supabaseUrl, supabaseAnonKey } = getSupabasePublicConfig();
  const url = hasConfig ? supabaseUrl : fallbackUrl;
  const key = hasConfig ? supabaseAnonKey : fallbackAnonKey;
  const clientKey = `${url}|${key}`;

  if (!cachedClient || cachedClientKey !== clientKey) {
    cachedClient = createClient(url, key);
    cachedClientKey = clientKey;
  }

  return cachedClient;
}

export type SupabaseSession = Session;
