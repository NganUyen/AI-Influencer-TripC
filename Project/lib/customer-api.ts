import { readPersistedCustomerSession } from "@/lib/customer-session";
import { getSupabaseClient } from "@/lib/supabase";

export async function customerApiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const supabase = getSupabaseClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const persistedSession = readPersistedCustomerSession();
  const accessToken = session?.access_token || persistedSession?.accessToken;

  const headers = new Headers(init?.headers || {});
  headers.set("Content-Type", "application/json");
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  // Diagnostic logging for debugging "Failed to fetch"
  const isBrowser = typeof window !== "undefined";
  const baseUrl = isBrowser ? window.location.origin : "";
  const fullUrl = path.startsWith("http") ? path : `${baseUrl}${path}`;

  try {
    const response = await fetch(path, {
      ...init,
      headers,
      cache: "no-store",
    });

    if (!response.ok) {
      const errorText = await response.text();
      if (errorText) {
        let message = errorText;
        try {
          const payload = JSON.parse(errorText) as { detail?: string };
          message = payload.detail || errorText;
        } catch {}
        throw new Error(message);
      }
      throw new Error(`Customer API request failed with status ${response.status}`);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof TypeError && error.message === "Failed to fetch") {
      console.error(`[customerApiRequest] Network error: Failed to fetch "${fullUrl}". ` +
        `Check if the dev server is running and the URL is reachable from this context.`);
    }
    throw error;
  }
}
