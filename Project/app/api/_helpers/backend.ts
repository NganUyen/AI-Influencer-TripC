import { NextRequest, NextResponse } from "next/server";
import { getInternalApiHeaders } from "@/app/api/_helpers/auth";

export function getBackendBaseUrl(): string {
  return process.env.PYTHON_BACKEND_URL || "http://127.0.0.1:8000";
}

type FallbackReason =
  | "backend_unreachable"
  | "backend_error"
  | "invalid_response";

type FallbackMeta = {
  backend_available: false;
  reason: FallbackReason;
  message: string;
  backend_status?: number;
};

type FallbackPayload<T extends Record<string, unknown>> = T & {
  _meta: FallbackMeta;
};

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
    headers: getInternalApiHeaders({
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    }),
    body,
    cache: "no-store",
    ...init,
  });
}

export async function proxyReadOnlyJson<T extends Record<string, unknown>>(
  targetUrl: string,
  fallbackData: T,
  errorMessage: string,
): Promise<NextResponse<T | FallbackPayload<T>>> {
  try {
    const response = await fetch(targetUrl, {
      method: "GET",
      headers: getInternalApiHeaders(),
      cache: "no-store",
    });

    const isOk =
      typeof response.ok === "boolean"
        ? response.ok
        : response.status >= 200 && response.status < 300;

    if (!isOk) {
      const backendMessage = await extractBackendMessage(response);
      return fallbackJson(fallbackData, {
        reason: "backend_error",
        message: backendMessage || errorMessage,
        backendStatus: response.status,
      });
    }

    const data = await parseJsonBody<T>(response);
    if (data === null) {
      return fallbackJson(fallbackData, {
        reason: "invalid_response",
        message: errorMessage,
      });
    }

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return fallbackJson(fallbackData, {
      reason: "backend_unreachable",
      message: error instanceof Error ? error.message : errorMessage,
    });
  }
}

async function extractBackendMessage(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) {
    return "";
  }

  try {
    const parsed = JSON.parse(text) as Record<string, unknown>;
    if (typeof parsed.error === "string" && parsed.error.trim() !== "") {
      return parsed.error;
    }
    if (typeof parsed.detail === "string" && parsed.detail.trim() !== "") {
      return parsed.detail;
    }
  } catch {
    return text;
  }

  return text;
}

async function parseJsonBody<T>(response: Response): Promise<T | null> {
  try {
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function fallbackJson<T extends Record<string, unknown>>(
  fallbackData: T,
  details: {
    reason: FallbackReason;
    message: string;
    backendStatus?: number;
  },
): NextResponse<FallbackPayload<T>> {
  return NextResponse.json(
    {
      ...fallbackData,
      _meta: {
        backend_available: false,
        reason: details.reason,
        message: details.message,
        ...(details.backendStatus !== undefined
          ? { backend_status: details.backendStatus }
          : {}),
      },
    },
    { status: 200 },
  );
}
