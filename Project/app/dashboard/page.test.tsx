import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import DashboardPage from "@/app/dashboard/page";
import apiClient from "@/lib/api-client";

const fetchItemsMock = jest.fn();

jest.mock("@/lib/api-client", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

jest.mock("@/store/content-store", () => ({
  useContentStore: () => ({
    items: [
      {
        id: "wf-1",
        workflowId: "wf-1",
        title: "Workflow wf-1",
        content: "Status: waiting_approval",
        platform: [],
        status: "pending_approval",
        workflowStatus: "waiting_approval",
        currentStep: "wait_for_approval",
        createdAt: new Date("2026-03-16T09:00:00.000Z"),
        updatedAt: new Date("2026-03-16T09:00:00.000Z"),
      },
      {
        id: "content-2",
        workflowId: "wf-2",
        title: "Twitter published post",
        content: "Launch teaser",
        platform: ["twitter"],
        status: "published",
        postUrl: "https://twitter.com/post/2",
        publishMethod: "postiz_oauth",
        engagementMetrics: {
          likes: 10,
          comments: 2,
          engagement_rate: 3.4,
        },
        lastEngagementCheckedAt: new Date("2026-03-17T08:30:00.000Z"),
        syndicateTriggered: true,
        syndicateJobId: "job-2",
        publishedAt: new Date("2026-03-17T08:00:00.000Z"),
        createdAt: new Date("2026-03-16T11:00:00.000Z"),
        updatedAt: new Date("2026-03-17T08:30:00.000Z"),
      },
      {
        id: "content-1",
        workflowId: "wf-2",
        title: "Twitter scheduled post",
        content: "Launch teaser",
        platform: ["twitter"],
        status: "scheduled",
        scheduledAt: new Date("2026-03-17T10:00:00.000Z"),
        createdAt: new Date("2026-03-16T10:00:00.000Z"),
        updatedAt: new Date("2026-03-16T10:00:00.000Z"),
      },
      {
        id: "content-3",
        workflowId: "wf-3",
        title: "TikTok failed post",
        content: "Promo clip",
        platform: ["tiktok"],
        status: "failed",
        publishError: "publish failed",
        createdAt: new Date("2026-03-16T12:00:00.000Z"),
        updatedAt: new Date("2026-03-16T12:15:00.000Z"),
      },
    ],
    fetchItems: fetchItemsMock,
  }),
}));

describe("DashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    fetchItemsMock.mockResolvedValue(undefined);

    (apiClient.get as jest.Mock).mockImplementation((url: string) => {
      if (url === "/api/workflows/list") {
        return Promise.resolve({
          data: {
            workflows: [
              {
                workflow_id: "wf-1",
                run_id: "run-1",
                status: "waiting_approval",
              },
            ],
          },
        });
      }

      if (url === "/api/content/stats") {
        return Promise.resolve({
          data: {
            total_content: 1,
            active_campaigns: 1,
            published: 0,
          },
        });
      }

      if (url === "/api/analytics/summary") {
        return Promise.resolve({
          data: {
            average_engagement_rate: 3.4,
          },
        });
      }

      if (url === "/api/quota/summary") {
        return Promise.resolve({
          data: {
            total_cost_usd: 6.25,
            time_period: "30_days",
            providers: [
              {
                provider: "openai",
                label: "OpenAI",
                status: "warning",
                usage_unit: "tokens",
                monthly_limit: 10000,
                usage: { tokens: 9200 },
                usage_value: 9200,
                remaining_value: 800,
                remaining_limit: 10000,
                remaining_unit: "tokens",
                remaining_exact: true,
                remaining_source: "provider_response_headers",
                remaining_message:
                  "Exact remaining quota captured from the latest provider API response handled by this app.",
                remaining_requests: 12,
                remaining_requests_limit: 60,
                remaining_requests_reset_after: "1m0s",
                cost_usd: 6.25,
                snapshot_count: 3,
              },
            ],
          },
        });
      }

      if (url === "/api/workflows/status/wf-1") {
        return Promise.resolve({
          data: {
            workflow_id: "wf-1",
            status: {
              status: "waiting_approval",
              current_step: "wait_for_approval",
            },
          },
        });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
  });

  it("renders fetched dashboard data", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Total Content")).toBeInTheDocument();
      expect(
        screen.getByText("Content Status: Pending Approval"),
      ).toBeInTheDocument();
      expect(screen.getByText("3.4%")).toBeInTheDocument();
      expect(screen.getByText("Open post")).toBeInTheDocument();
      expect(
        screen.getByText("Engagement: Likes 10 | Comments 2 | Rate 3.4%"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Publish error: publish failed"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Retry Publish" }),
      ).toBeInTheDocument();
      expect(screen.getAllByText("Twitter scheduled post")).toHaveLength(2);
      expect(
        screen.getAllByText("Scheduled: 2026-03-17 10:00 UTC"),
      ).toHaveLength(2);
      expect(
        screen.getByText("1 workflow(s) waiting for approval."),
      ).toBeInTheDocument();
      expect(screen.getByText("API Usage")).toBeInTheDocument();
      expect(screen.getByText("OpenAI")).toBeInTheDocument();
      expect(
        screen.getByText("Remaining: 800 / 10,000 tokens left"),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "Exact remaining quota captured from the latest provider API response handled by this app.",
        ),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Requests left: 12 / 60 (resets in 1m0s)"),
      ).toBeInTheDocument();
      expect(screen.getByText("Used: 9,200 / 10,000 tokens")).toBeInTheDocument();
      expect(screen.getByText("Warning")).toBeInTheDocument();
      expect(screen.getByText("Total cost tracked: $6.25")).toBeInTheDocument();
    });

    expect(fetchItemsMock).toHaveBeenCalled();
  });

  it("starts a retry publish action when retry is clicked", async () => {
    (apiClient.post as jest.Mock).mockResolvedValue({
      data: { status: "retry_started" },
    });

    render(<DashboardPage />);

    const retryButton = await screen.findByRole("button", {
      name: "Retry Publish",
    });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/content/retry/content-3",
      );
    });
  });

  it("sends approval action when approve is clicked", async () => {
    (apiClient.post as jest.Mock).mockResolvedValue({
      data: { status: "signal_sent" },
    });

    render(<DashboardPage />);

    const approveButton = await screen.findByRole("button", {
      name: "Approve",
    });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/workflows/approve/wf-1",
        {
          approved: true,
          feedback: "Approved from dashboard",
        },
      );
    });
  });
});
