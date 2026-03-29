/** @jest-environment node */

import { NextRequest } from "next/server";

import { GET as getAnalyticsSummary } from "@/app/api/analytics/summary/route";
import { POST as postTelegramAuthProxy } from "@/app/api/auth/telegram/[...path]/route";
import { GET as getContentList } from "@/app/api/content/list/route";
import { GET as getCustomerProxy, POST as postCustomerProxy } from "@/app/api/customer/[...path]/route";
import { POST as postContentRetry } from "@/app/api/content/retry/[contentId]/route";
import { GET as getContentStats } from "@/app/api/content/stats/route";
import { GET as getQuotaSummary } from "@/app/api/quota/summary/route";
import { POST as postApproveWorkflow } from "@/app/api/workflows/approve/[workflowId]/route";
import { GET as getWorkflowList } from "@/app/api/workflows/list/route";
import { POST as postStartWeekly } from "@/app/api/workflows/start-weekly/route";
import { GET as getWorkflowStatus } from "@/app/api/workflows/status/[workflowId]/route";

jest.mock("@/app/api/_helpers/backend", () => {
  const actual = jest.requireActual("@/app/api/_helpers/backend");
  return {
    ...actual,
    getBackendBaseUrl: jest.fn(() => "http://backend.test"),
  };
});

describe("API proxy routes", () => {
  const originalAdminToken = process.env.APP_ADMIN_TOKEN;
  const originalInternalApiToken = process.env.INTERNAL_API_TOKEN;

  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.APP_ADMIN_TOKEN;
    delete process.env.INTERNAL_API_TOKEN;
  });

  afterAll(() => {
    if (originalAdminToken === undefined) {
      delete process.env.APP_ADMIN_TOKEN;
    } else {
      process.env.APP_ADMIN_TOKEN = originalAdminToken;
    }

    if (originalInternalApiToken === undefined) {
      delete process.env.INTERNAL_API_TOKEN;
    } else {
      process.env.INTERNAL_API_TOKEN = originalInternalApiToken;
    }
  });

  it("proxies content list with query limit", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ items: [{ id: "wf-1" }] }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/content/list?limit=12",
    );
    const response = await getContentList(request);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/content/list?limit=12",
      expect.objectContaining({ method: "GET" }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ items: [{ id: "wf-1" }] });
  });

  it("proxies content stats", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ total_content: 3 }),
    } as Response);

    const request = new NextRequest("http://localhost/api/content/stats");
    const response = await getContentStats(request);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/content/stats",
      expect.objectContaining({ method: "GET" }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ total_content: 3 });
  });

  it("falls back to empty content stats when backend is unreachable", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("connect ECONNREFUSED"));

    const request = new NextRequest("http://localhost/api/content/stats");
    const response = await getContentStats(request);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      total_content: 0,
      active_campaigns: 0,
      published: 0,
      _meta: {
        backend_available: false,
        reason: "backend_unreachable",
        message: "connect ECONNREFUSED",
      },
    });
  });

  it("proxies content retry", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ status: "retry_started" }),
    } as Response);

    const request = new NextRequest("http://localhost/api/content/retry/content-1", {
      method: "POST",
    });
    const response = await postContentRetry(request, {
      params: Promise.resolve({ contentId: "content-1" }),
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/content/retry/content-1",
      expect.objectContaining({ method: "POST" }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "retry_started" });
  });

  it("proxies analytics summary", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ average_engagement_rate: 3.4 }),
    } as Response);

    const request = new NextRequest("http://localhost/api/analytics/summary");
    const response = await getAnalyticsSummary(request);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/analytics/summary",
      expect.objectContaining({ method: "GET" }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ average_engagement_rate: 3.4 });
  });

  it("falls back to empty analytics summary when backend returns an error", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      text: async () => JSON.stringify({ error: "backend unavailable" }),
    } as Response);

    const request = new NextRequest("http://localhost/api/analytics/summary");
    const response = await getAnalyticsSummary(request);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      average_engagement_rate: null,
      _meta: {
        backend_available: false,
        reason: "backend_error",
        message: "backend unavailable",
        backend_status: 503,
      },
    });
  });

  it("proxies quota summary", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({
        total_cost_usd: 2.5,
        providers: [{ provider: "openai", status: "warning" }],
      }),
    } as Response);

    const request = new NextRequest("http://localhost/api/quota/summary");
    const response = await getQuotaSummary(request);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/quota/summary",
      expect.objectContaining({ method: "GET" }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      total_cost_usd: 2.5,
      providers: [{ provider: "openai", status: "warning" }],
    });
  });

  it("falls back to empty quota summary when backend is unreachable", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("fetch failed"));

    const request = new NextRequest("http://localhost/api/quota/summary");
    const response = await getQuotaSummary(request);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      total_cost_usd: 0,
      providers: [],
      time_period: "30_days",
      _meta: {
        backend_available: false,
        reason: "backend_unreachable",
        message: "fetch failed",
      },
    });
  });

  it("proxies workflow list", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ workflows: [] }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/workflows/list?limit=5",
    );
    const response = await getWorkflowList(request);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/workflows/list?limit=5",
      expect.objectContaining({ method: "GET" }),
    );
    expect(response.status).toBe(200);
  });

  it("falls back to an empty workflow list when backend is unreachable", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("backend offline"));

    const request = new NextRequest(
      "http://localhost/api/workflows/list?limit=5",
    );
    const response = await getWorkflowList(request);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      workflows: [],
      _meta: {
        backend_available: false,
        reason: "backend_unreachable",
        message: "backend offline",
      },
    });
  });

  it("proxies workflow status by id", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ status: { status: "running" } }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/workflows/status/wf-1",
    );
    const response = await getWorkflowStatus(request, {
      params: Promise.resolve({ workflowId: "wf-1" }),
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/workflows/status/wf-1",
      expect.objectContaining({ method: "GET" }),
    );
    expect(response.status).toBe(200);
  });

  it("proxies customer GET routes with bearer auth", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({ brand_profile: { product_name: "TripC" } }),
    } as Response);

    const request = new NextRequest("http://localhost/api/customer/brand", {
      headers: { Authorization: "Bearer customer-token" },
    });
    const response = await getCustomerProxy(request, {
      params: { path: ["brand"] },
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/customer/brand",
      expect.objectContaining({
        method: "GET",
        headers: expect.any(Headers),
      }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      brand_profile: { product_name: "TripC" },
    });
  });

  it("proxies customer POST routes with body and bearer auth", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({ status: "launched" }),
    } as Response);

    const request = new NextRequest("http://localhost/api/customer/campaigns/campaign-1/launch", {
      method: "POST",
      headers: { Authorization: "Bearer customer-token" },
      body: JSON.stringify({}),
    });
    const response = await postCustomerProxy(request, {
      params: { path: ["campaigns", "campaign-1", "launch"] },
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/customer/campaigns/campaign-1/launch",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "launched" });
  });

  it("proxies telegram auth POST routes", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({ start_token: "abc123" }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/auth/telegram/link/start",
      {
        method: "POST",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
        },
        body: JSON.stringify({ expires_in_minutes: 15 }),
      },
    );
    const response = await postTelegramAuthProxy(request, {
      params: Promise.resolve({ path: ["link", "start"] }),
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/auth/telegram/link/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expires_in_minutes: 15 }),
        headers: expect.any(Headers),
      }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ start_token: "abc123" });
  });

  it("proxies telegram auth completion polling routes", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      text: async () =>
        JSON.stringify({
          status: "pending",
          expires_at: "2026-03-29T12:00:00Z",
          authenticated_at: null,
        }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/auth/telegram/link/complete",
      {
        method: "POST",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
        },
        body: JSON.stringify({ start_token: "abc123" }),
      },
    );
    const response = await postTelegramAuthProxy(request, {
      params: Promise.resolve({ path: ["link", "complete"] }),
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/auth/telegram/link/complete",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ start_token: "abc123" }),
        headers: expect.any(Headers),
      }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      status: "pending",
      expires_at: "2026-03-29T12:00:00Z",
      authenticated_at: null,
    });
  });

  it("proxies workflow approval payload", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ status: "signal_sent" }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/workflows/approve/wf-1",
      {
        method: "POST",
        body: JSON.stringify({ approved: true, feedback: "ok" }),
        headers: { "Content-Type": "application/json" },
      },
    );

    const response = await postApproveWorkflow(request, {
      params: Promise.resolve({ workflowId: "wf-1" }),
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/workflows/approve/wf-1?approved=true&feedback=ok",
      expect.objectContaining({ method: "POST" }),
    );
    expect(response.status).toBe(200);
  });

  it("returns 400 when user_id missing for start-weekly", async () => {
    const request = new NextRequest(
      "http://localhost/api/workflows/start-weekly",
      {
        method: "POST",
        body: JSON.stringify({ brand_config: {} }),
        headers: { "Content-Type": "application/json" },
      },
    );

    const response = await postStartWeekly(request);
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "user_id is required" });
  });

  it("proxies start-weekly request", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ workflow_id: "weekly-marketing-user-1" }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/workflows/start-weekly",
      {
        method: "POST",
        body: JSON.stringify({
          user_id: "user-1",
          brand_config: { niche: "ai" },
        }),
        headers: { "Content-Type": "application/json" },
      },
    );

    const response = await postStartWeekly(request);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/workflows/start-weekly?user_id=user-1",
      expect.objectContaining({ method: "POST" }),
    );
    expect(response.status).toBe(200);
  });

  it("rejects requests without an admin token when auth is configured", async () => {
    process.env.APP_ADMIN_TOKEN = "admin-token";

    const request = new NextRequest("http://localhost/api/content/stats");
    const response = await getContentStats(request);

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ error: "Unauthorized" });
  });

  it("forwards the internal API token to the backend", async () => {
    process.env.APP_ADMIN_TOKEN = "admin-token";
    process.env.INTERNAL_API_TOKEN = "internal-token";
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ workflows: [] }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/workflows/list?limit=5",
      {
        headers: { Authorization: "Bearer admin-token" },
      },
    );
    const response = await getWorkflowList(request);

    expect(response.status).toBe(200);
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect((init.headers as Headers).get("x-internal-api-token")).toBe(
      "internal-token",
    );
  });
});
