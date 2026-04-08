import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

async function proxyTelegramAuthRequest(
  request: NextRequest,
  params: { path: string[] },
) {
  const pathSegments = params.path || [];
  const query = request.nextUrl.search || "";
  const targetUrl = `${getBackendBaseUrl()}/api/auth/telegram/${pathSegments.join("/")}${query}`;
  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.text();

  const headers = new Headers();
  const authorization = request.headers.get("authorization");
  const accept = request.headers.get("accept");
  if (authorization) {
    headers.set("Authorization", authorization);
  }
  if (accept) {
    headers.set("Accept", accept);
  }
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const isTelegramLoginRequest =
    request.method === "POST" &&
    pathSegments.length === 1 &&
    pathSegments[0] === "login";

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
    });

    const proxiedHeaders = new Headers();
    const contentType = response.headers.get("content-type");
    const location = response.headers.get("location");
    if (contentType) {
      proxiedHeaders.set("content-type", contentType);
    }
    if (location) {
      proxiedHeaders.set("location", location);
    }

    const responseBody =
      request.method === "HEAD" ? null : await response.text();

    return new NextResponse(responseBody, {
      status: response.status,
      headers: proxiedHeaders,
    });
  } catch (error) {
    if (isTelegramLoginRequest && isLocalDevMockLogin(body)) {
      return NextResponse.json({
        access_token: "dev-local-token",
        refresh_token: null,
        user: {
          id: "dev-local-user",
          email: "dev-tester@local.test",
          name: "Dev Tester",
          avatar_url: null,
        },
      });
    }

    const message =
      error instanceof Error
        ? error.message
        : "Telegram auth backend is unreachable";
    return NextResponse.json(
      {
        detail: `Telegram auth service is unavailable: ${message}`,
      },
      { status: 503 },
    );
  }
}

function isLocalDevMockLogin(body: string | undefined): boolean {
  if (process.env.NODE_ENV === "production") {
    return false;
  }

  if (!body) {
    return false;
  }

  try {
    const payload = JSON.parse(body) as { hash?: string };
    return payload.hash === "__MOCK_DEV_LOGIN__";
  } catch {
    return false;
  }
}

type Params = {
  params: Promise<{
    path: string[];
  }>;
};

export async function GET(request: NextRequest, { params }: Params) {
  return proxyTelegramAuthRequest(request, await params);
}

export async function POST(request: NextRequest, { params }: Params) {
  return proxyTelegramAuthRequest(request, await params);
}
