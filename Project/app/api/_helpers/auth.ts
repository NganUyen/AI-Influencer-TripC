import { NextRequest, NextResponse } from "next/server";

const PLACEHOLDER_TOKENS = new Set([
  "change-this-admin-token",
  "change-this-internal-api-token",
]);

function normalizeToken(value: string | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function isPlaceholderToken(value: string | null): boolean {
  return value !== null && PLACEHOLDER_TOKENS.has(value);
}

function getConfiguredAdminToken(): string | null {
  return normalizeToken(process.env.APP_ADMIN_TOKEN);
}

function getConfiguredInternalToken(): string | null {
  return normalizeToken(process.env.INTERNAL_API_TOKEN);
}

function extractBearerToken(request: NextRequest): string | null {
  const authorization = request.headers.get("authorization");
  if (!authorization) {
    return null;
  }

  if (authorization.toLowerCase().startsWith("bearer ")) {
    const token = authorization.slice("bearer ".length).trim();
    return token || null;
  }

  const token = authorization.trim();
  return token || null;
}

function isProductionRuntime(): boolean {
  return process.env.NODE_ENV === "production";
}

export function requireAdminApiAuth(
  request: NextRequest,
): NextResponse | null {
  const configuredToken = getConfiguredAdminToken();

  if (!configuredToken) {
    if (isProductionRuntime()) {
      return NextResponse.json(
        { error: "Admin API authentication is not configured" },
        { status: 503 },
      );
    }
    return null;
  }

  if (isPlaceholderToken(configuredToken)) {
    return NextResponse.json(
      { error: "Admin API authentication is misconfigured" },
      { status: 503 },
    );
  }

  const presentedToken = extractBearerToken(request);
  if (!presentedToken || presentedToken !== configuredToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  return null;
}

export function getInternalApiHeaders(
  headers?: HeadersInit,
): Headers {
  const mergedHeaders = new Headers(headers);
  const configuredToken = getConfiguredInternalToken();

  if (configuredToken && !isPlaceholderToken(configuredToken)) {
    mergedHeaders.set("x-internal-api-token", configuredToken);
  }

  return mergedHeaders;
}
