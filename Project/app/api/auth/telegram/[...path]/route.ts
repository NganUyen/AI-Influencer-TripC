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
