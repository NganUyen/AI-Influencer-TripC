/** @jest-environment node */

import { NextRequest } from "next/server";

import { GET as getContentList } from "@/app/api/content/list/route";
import { GET as getContentStats } from "@/app/api/content/stats/route";
import { POST as postApproveWorkflow } from "@/app/api/workflows/approve/[workflowId]/route";
import { GET as getWorkflowList } from "@/app/api/workflows/list/route";
import { POST as postStartWeekly } from "@/app/api/workflows/start-weekly/route";
import { GET as getWorkflowStatus } from "@/app/api/workflows/status/[workflowId]/route";

jest.mock("@/app/api/_helpers/backend", () => ({
  getBackendBaseUrl: jest.fn(() => "http://backend.test"),
}));

describe("API proxy routes", () => {
  beforeEach(() => {
    jest.clearAllMocks();
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

    const response = await getContentStats();

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/content/stats",
      expect.objectContaining({ method: "GET" }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ total_content: 3 });
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

  it("proxies workflow status by id", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({ status: { status: "running" } }),
    } as Response);

    const request = new NextRequest(
      "http://localhost/api/workflows/status/wf-1",
    );
    const response = await getWorkflowStatus(request, {
      params: { workflowId: "wf-1" },
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://backend.test/api/workflows/status/wf-1",
      expect.objectContaining({ method: "GET" }),
    );
    expect(response.status).toBe(200);
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
      params: { workflowId: "wf-1" },
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
});
