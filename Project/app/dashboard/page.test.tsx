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
        title: "Workflow wf-1",
        content: "Status: waiting_approval",
        platform: [],
        status: "pending_approval",
        createdAt: new Date("2026-03-16T09:00:00.000Z"),
        updatedAt: new Date("2026-03-16T09:00:00.000Z"),
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
      expect(screen.getByText("Status: waiting_approval")).toBeInTheDocument();
      expect(
        screen.getByText("1 workflow(s) waiting for approval."),
      ).toBeInTheDocument();
    });

    expect(fetchItemsMock).toHaveBeenCalled();
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
