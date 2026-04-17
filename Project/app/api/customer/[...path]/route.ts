import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

// ─── Dev Mock Data ────────────────────────────────────────────────────────────
const DEV_MOCK_DATA: Record<string, unknown> = {
  workspace: {
    customer: {
      user_id: "11111111-1111-1111-1111-111111111111",
      email: "founder@example.com",
      display_name: "Founder",
    },
    brand: {
      product_name: "My Brand",
      website_url: "https://example.com",
      audience: "Content creators",
      offer_summary: "AI-powered content tools",
      tone_voice: "clear",
      campaign_goals: ["launch"],
      asset_urls: [],
      timezone: "UTC",
      telegram_contact: "@tripc",
    },
    social_accounts: [],
    assistant_threads: [],
    campaigns: [],
    approvals: [],
    approval_requests: [],
    content: [],
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
    telegram_link: { linked: false, link: null },
    ai_backbone: {
      access_mode: "platform_managed",
      platform_managed: {
        api_url: "https://openclaw.example",
        has_api_key: true,
      },
      customer_api: {
        api_url: "",
        has_api_key: false,
      },
      chatgpt_oauth: {
        linked: false,
        session_ready: false,
        chatgpt_subject: null,
        session_expires_at: null,
      },
      effective_status: {
        ready: true,
        message: "AI active — Platform Managed",
      },
    },
    system_summary: {
      telegram_bot_url: "https://t.me/TripCInternBot",
      quota: [
        { name: "OpenAI gpt-4-turbo", used: 850000, total: 1000000, unit: "tokens" },
      ],
      services: [],
      recent_videos: [],
      status: "healthy",
    },
    workflow_summary: {
      workflows: [],
      status: "empty",
    },
  },
  "system/summary": {
    telegram_bot_url: "https://t.me/TripCInternBot",
    quota: [
      { name: "OpenAI gpt-4-turbo", used: 850000, total: 1000000, unit: "tokens" },
      { name: "Anthropic claude-3-5", used: 125000, total: 500000, unit: "tokens" },
      { name: "Google AI Gemini 1.5", used: 1850, total: 2000, unit: "req" },
      { name: "Google Cloud TTS", used: 97000, total: 100000, unit: "chars" },
      { name: "Fal.ai Media Gen", used: 45, total: 200, unit: "req" },
      { name: "HeyGen Avatar Video", used: 28, total: 30, unit: "jobs" },
    ],
    services: [],
    recent_videos: [],
    status: "healthy",
  },
  "system/workflows": {
    workflows: [
      { id: "wf-dev-1", workflow_id: "wf-dev-1", name: "Content Generation", status: "running", progress: 65 },
      { id: "wf-dev-2", workflow_id: "wf-dev-2", name: "Audience Analysis", status: "completed", progress: 100 }
    ]
  },
  "review-engine/setup": {
    steps: [
      { key: "enter_url", label: "Step 1: Enter URL" },
      { key: "choose_persona", label: "Step 2: Choose an available persona" },
      { key: "final_product", label: "Step 3: Final product" },
    ],
    supported_languages: ["English", "Chinese", "Spanish", "Arabic"],
    persona_options: [
      {
        persona_id: "basic-american-host",
        display_name: "Ava Brooks",
        language: "English",
        region_label: "American",
        selection_image_url:
          "https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=800&auto=format&fit=crop",
        tiktok_integration: {
          status: "active",
          active_channels: 1,
          inactive_channels: 0,
          channels: [{ display_name: "US Channel", handle: "@ava_us", status: "active" }],
        },
        demo: {
          available: true,
          label: "Ava demo",
          summary: "AI-generated English product review demo.",
        },
      },
    ],
    custom_personas: [],
    create_your_own: {
      available: true,
      label: "Create your own Persona",
    },
    publishing_requirements: {
      telegram_linked: false,
      tiktok_channels_active: true,
      tiktok_channels_total: 1,
    },
  },
  "review-engine/jobs": {
    jobs: [
      {
        job_id: "video-basic-american-host-demo",
        workflow_id: "video-basic-american-host-demo",
        type: "app_review_video",
        status: "running",
        current_step: "generating_talking_head",
        progress: 65,
        activity_feed: [
          { key: "enter_url", label: "Step 1: Enter URL", status: "completed" },
          { key: "choose_persona", label: "Step 2: Choose Persona", status: "completed" },
          { key: "final_product", label: "Step 3: Final Product", status: "in_progress" },
        ],
        source_url: "https://example.com/app",
        objective: "Generate a short English app review.",
        page_title: "Example App",
        persona: {
          persona_id: "basic-american-host",
          display_name: "Ava Brooks",
          language: "English",
          region_label: "American",
          image_url:
            "https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=800&auto=format&fit=crop",
        },
        content: {
          title: "Example App · Ava Brooks",
          body: "A quick English-first review ready for TikTok.",
          status: "draft",
          published: false,
        },
        production: {
          ready: false,
          publish_enabled: false,
        },
        publish: {
          requested: false,
          status: "not_requested",
        },
      },
    ],
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
    // Let plan management pass entirely through to the backend implementation
    if (!pathStr.startsWith("review-engine/plans") && !pathStr.startsWith("review-engine/jobs")) {
      const mockData = getMockResponse(pathStr);
      if (mockData !== null) {
        return NextResponse.json(mockData, { status: 200 });
      }
      // Unknown endpoint — return empty 200 so the UI doesn't crash
      return NextResponse.json({}, { status: 200 });
    }
  }

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : (() => request.arrayBuffer())();

  const headers = new Headers();
  if (authHeader) headers.set("Authorization", authHeader);
  const accept = request.headers.get("accept");
  if (accept) headers.set("Accept", accept);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const fileName = request.headers.get("x-filename");
  if (fileName) headers.set("x-filename", fileName);

  try {
    const resolvedBody = body === undefined ? undefined : await body;
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: resolvedBody,
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
