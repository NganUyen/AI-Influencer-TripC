import { getSupabaseClient } from "@/lib/supabase";

export async function customerApiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const supabase = getSupabaseClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers = new Headers(init?.headers || {});
  headers.set("Content-Type", "application/json");
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }

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
    throw new Error("Customer API request failed");
  }

  return (await response.json()) as T;
}
