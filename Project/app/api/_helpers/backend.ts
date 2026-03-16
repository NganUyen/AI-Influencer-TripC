import { NextRequest } from "next/server";

export function getBackendBaseUrl(): string {
  return process.env.PYTHON_BACKEND_URL || "http://localhost:8000";
}

export async function proxyJson(
  request: NextRequest,
  targetUrl: string,
  init?: RequestInit,
): Promise<Response> {
  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.text();

  return fetch(targetUrl, {
    method: request.method,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    body,
    cache: "no-store",
    ...init,
  });
}
