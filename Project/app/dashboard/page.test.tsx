import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import DashboardPage from "@/app/dashboard/[[...tab]]/page";
import { customerApiRequest } from "@/lib/customer-api";

const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockPrefetch = jest.fn();
const mockLogout = jest.fn(() => Promise.resolve());

jest.mock("@/lib/customer-api", () => ({
  customerApiRequest: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    prefetch: mockPrefetch,
  }),
  useSearchParams: () => ({
    get: jest.fn(() => null),
  }),
}));

jest.mock("@/store/customer-auth-store", () => ({
  useCustomerAuthStore: (selector?: (state: unknown) => unknown) => {
    const state = {
      user: {
        id: "user-1",
        email: "founder@example.com",
        name: "Founder",
      },
      isAuthenticated: true,
      isLoading: false,
      initialized: true,
      error: null,
      initialize: jest.fn(),
      logout: mockLogout,
    };
    return selector ? selector(state) : state;
  },
}));

describe("Customer dashboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (customerApiRequest as jest.Mock).mockImplementation((path: string) => {
      if (path === "/api/customer/system/summary") {
        return Promise.resolve({ services: [], quota: [] });
      }
      if (path === "/api/customer/system/workflows") {
        return Promise.resolve({ workflows: [] });
      }
      if (path === "/api/customer/workspace") {
        return Promise.resolve({
          customer: {
            user_id: "user-1",
            email: "founder@example.com",
            display_name: "Founder",
          },
          brand: {
            product_name: "TripC",
            website_url: "https://tripc.ai",
            audience: "Travel operators",
            offer_summary: "AI media production",
            tone_voice: "clear",
            campaign_goals: ["launch", "signups"],
            asset_urls: ["https://cdn.example/logo.png"],
            timezone: "UTC",
            telegram_contact: "@tripc",
          },
          social_accounts: [
            {
              id: "account-1",
              platform: "linkedin",
              display_name: "TripC Company",
              account_handle: "tripc",
              connection_status: "connected",
            },
          ],
          assistant_threads: [
            {
              id: "thread-1",
              title: "Launch Plan",
              last_message_preview: "Plan the launch",
            },
          ],
          campaigns: [
            {
              id: "campaign-1",
              name: "Q2 Launch",
              status: "active",
              approval_status: "approved",
              target_platforms: ["linkedin", "facebook"],
              active_workflow_id: "wf-1",
            },
          ],
          approvals: [
            {
              id: "campaign-3",
              name: "Pending Launch",
              status: "draft",
              approval_status: "pending",
              target_platforms: ["twitter"],
            },
          ],
          content: [
            {
              id: "content-1",
              title: "Launch teaser",
              status: "scheduled",
              platform: ["linkedin"],
              scheduled_at: "2026-03-25T10:00:00Z",
            },
          ],
          ai_backbone: {
            access_mode: "platform_managed",
            platform_managed: {
              api_url: "https://openclaw.example",
            },
            customer_api: {
              api_url: "https://customer-openclaw.example",
              has_api_key: true,
            },
            chatgpt_oauth: {
              linked: false,
              session_ready: false,
              chatgpt_subject: "",
              session_expires_at: null,
            },
            effective_status: {
              ready: true,
              message: "Using workspace-managed OpenClaw access.",
            },
          },
          personas: [],
          telegram_link: { linked: false },
          system_summary: { services: [], quota: [] },
          workflow_summary: { workflows: [] },
        });
      }
      if (path === "/api/customer/assistant/threads/thread-1/messages") {
        return Promise.resolve({
          messages: [
            { id: "m1", role: "user", content: "Plan a launch week." },
            { id: "m2", role: "assistant", content: "Use a review-first weekly plan." },
          ],
          artifacts: [],
        });
      }
      if (path === "/api/customer/content") {
        return Promise.resolve({
          items: [
            {
              id: "content-1",
              title: "Launch teaser",
              status: "scheduled",
              platform: ["linkedin"],
              scheduled_at: "2026-03-25T10:00:00Z",
            },
          ],
        });
      }
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  it("renders the current dashboard shell", async () => {
    render(await DashboardPage({ params: Promise.resolve({}) }));

    await waitFor(() => {
      expect(screen.getByText("Production Queue")).toBeInTheDocument();
      expect(screen.getByText("Final Products")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("renders a URL-backed dashboard tab", async () => {
    render(
      await DashboardPage({
        params: Promise.resolve({ tab: ["memory"] }),
      }),
    );

    expect(
      await screen.findByRole("link", { name: "Agent & Instrument" }),
    ).toHaveAttribute("aria-current", "page");
    expect(await screen.findByText("Connected Accounts")).toBeInTheDocument();
  });

  it("signs out the current customer from the dashboard shell", async () => {
    render(await DashboardPage({ params: Promise.resolve({}) }));

    fireEvent.click(await screen.findByRole("menuitem", { name: "Sign out" }));

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
      expect(mockReplace).toHaveBeenCalledWith("/auth");
    });
  });
});
