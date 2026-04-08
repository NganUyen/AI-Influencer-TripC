import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

// ─── Dev Mock Data ────────────────────────────────────────────────────────────
const DEV_MOCK_DATA: Record<string, unknown> = {
  "system/summary": {
    personas: [
      {
        persona_id: "persona-001",
        display_name: "Linh Anh",
        status: "active",
        video_count: 24,
        avatar_image_url: null,
      },
      {
        persona_id: "persona-002",
        display_name: "Minh Tú",
        status: "draft",
        video_count: 7,
        avatar_image_url: null,
      },
    ],
    campaigns: [],
    social_accounts: [],
    telegram_link: { linked: false, link: null },
    telegram_bot_url: "https://t.me/TripCInternBot",
    ai_backbone: {
      access_mode: "platform_managed",
      effective_status: { ready: true, message: "AI active — Platform Managed" },
    },
    brand_context: {
      product_name: "My Brand",
      audience: "Content creators",
      offer_summary: "AI-powered content tools",
    },
    quota: [
      { name: "OpenAI gpt-4-turbo", used: 850000, total: 1000000, unit: "tokens" },
      { name: "Anthropic claude-3-5", used: 125000, total: 500000, unit: "tokens" },
      { name: "Google AI Gemini 1.5", used: 1850, total: 2000, unit: "req" },
      { name: "Google Cloud TTS", used: 97000, total: 100000, unit: "chars" },
      { name: "Fal.ai Media Gen", used: 45, total: 200, unit: "req" },
      { name: "HeyGen Avatar Video", used: 28, total: 30, unit: "jobs" },
    ],
    system_workflows: [],
    activity: [],
  },
  "system/workflows": {
    workflows: [
      { id: "wf-dev-1", name: "Content Generation", status: "running", progress: 65 },
      { id: "wf-dev-2", name: "Audience Analysis", status: "completed", progress: 100 }
    ]
  },
  "brand/context": {
    product_name: "My Brand",
    audience: "Content creators",
    offer_summary: "AI-powered content tools",
  },
};

function getMockResponse(pathStr: string): unknown | null {
  // exact match
  if (DEV_MOCK_DATA[pathStr]) return DEV_MOCK_DATA[pathStr];
  // prefix match (e.g. "system/summary?foo=bar")
  for (const key of Object.keys(DEV_MOCK_DATA)) {
    if (pathStr.startsWith(key)) return DEV_MOCK_DATA[key];
  }
  return null;
}

function isDevMockToken(authHeader: string | null): boolean {
  if (!authHeader) return false;
  return authHeader.includes("mock_dev_signature");
}

async function proxyCustomerRequest(
  request: NextRequest,
  params: { path: string[] },
) {
  const pathSegments = params.path || [];
  const pathStr = pathSegments.join("/");
  const query = request.nextUrl.search || "";
  const targetUrl = `${getBackendBaseUrl()}/api/customer/${pathStr}${query}`;
  const authHeader = request.headers.get("authorization");

  // ── Dev mock bypass ──────────────────────────────────────────────────────
  if (process.env.NODE_ENV === "development" && isDevMockToken(authHeader)) {
    const mockData = getMockResponse(pathStr);
    if (mockData !== null) {
      return NextResponse.json(mockData, { status: 200 });
    }
    // Unknown endpoint — return empty 200 so the UI doesn't crash
    return NextResponse.json({}, { status: 200 });
  }

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.text();

  const headers = new Headers();
  if (authHeader) headers.set("Authorization", authHeader);
  const accept = request.headers.get("accept");
  if (accept) headers.set("Accept", accept);
  if (body !== undefined) headers.set("Content-Type", "application/json");

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
    if (contentType) proxiedHeaders.set("content-type", contentType);
    if (location) proxiedHeaders.set("location", location);

    const responseBody =
      request.method === "HEAD" ? null : await response.text();

    return new NextResponse(responseBody, {
      status: response.status,
      headers: proxiedHeaders,
    });
  } catch (error) {
    // ── Dev fallback when backend is completely unreachable ──────────────
    if (process.env.NODE_ENV === "development") {
      const mockData = getMockResponse(pathStr);
      return NextResponse.json(
        mockData ?? { detail: "Backend unavailable in dev mode" },
        { status: mockData !== null ? 200 : 503 },
      );
    }
    const message =
      error instanceof Error ? error.message : "Backend unreachable";
    return NextResponse.json({ detail: message }, { status: 503 });
  }
}

type Params = {
  params: Promise<{
    path: string[];
  }>;
};

export async function GET(request: NextRequest, { params }: Params) {
  return proxyCustomerRequest(request, await params);
}

export async function POST(request: NextRequest, { params }: Params) {
  return proxyCustomerRequest(request, await params);
}

export async function PUT(request: NextRequest, { params }: Params) {
  return proxyCustomerRequest(request, await params);
}

export async function PATCH(request: NextRequest, { params }: Params) {
  return proxyCustomerRequest(request, await params);
}
