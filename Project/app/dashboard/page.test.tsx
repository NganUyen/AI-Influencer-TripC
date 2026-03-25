import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import DashboardPage from "@/app/dashboard/page";
import { customerApiRequest } from "@/lib/customer-api";

jest.mock("@/lib/customer-api", () => ({
  customerApiRequest: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
  }),
  useSearchParams: () => ({
    get: jest.fn(() => null),
  }),
}));

jest.mock("@/store/customer-auth-store", () => ({
  useCustomerAuthStore: (selector: (state: unknown) => unknown) =>
    selector({
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
      logout: jest.fn(() => Promise.resolve()),
    }),
}));

describe("Customer dashboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    (customerApiRequest as jest.Mock).mockImplementation((path: string, init?: RequestInit) => {
      if (path === "/api/customer/brand") {
        return Promise.resolve({
          brand_profile: {
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
        });
      }
      if (path === "/api/customer/social-accounts") {
        return Promise.resolve({
          accounts: [
            {
              id: "account-1",
              platform: "linkedin",
              display_name: "TripC Company",
              account_handle: "tripc",
              connection_status: "connected",
            },
          ],
        });
      }
      if (path === "/api/customer/ai-backbone") {
        if (init?.method === "PUT") {
          return Promise.resolve({
            settings: {
              access_mode: "customer_api_key",
              workspace_default: {
                api_url: "https://openclaw.example",
                has_api_key: true,
              },
              customer_api: {
                api_url: "https://customer-openclaw.example",
                has_api_key: true,
              },
              chatgpt_oauth: {
                linked: false,
                session_ready: false,
              },
              effective_status: {
                ready: true,
                message: "Using the customer-provided OpenClaw API key.",
              },
            },
          });
        }
        return Promise.resolve({
          settings: {
            access_mode: "platform_managed",
            workspace_default: {
              api_url: "https://openclaw.example",
              has_api_key: true,
            },
            customer_api: {
              api_url: "https://customer-openclaw.example",
              has_api_key: true,
            },
            chatgpt_oauth: {
              linked: false,
              session_ready: false,
              chatgpt_subject: "",
              display_name: "",
              subscription_tier: "plus",
            },
            effective_status: {
              ready: true,
              message: "Using workspace-managed OpenClaw access.",
            },
          },
        });
      }
      if (path === "/api/customer/assistant/threads") {
        if (init?.method === "POST") {
          return Promise.resolve({
            thread: {
              id: "thread-2",
              title: "Campaign Planning",
              last_message_preview: "",
            },
          });
        }
        return Promise.resolve({
          threads: [
            {
              id: "thread-1",
              title: "Launch Plan",
              last_message_preview: "Plan the launch",
            },
          ],
        });
      }
      if (path === "/api/customer/assistant/threads/thread-1/messages") {
        return Promise.resolve({
          messages: [
            { id: "m1", role: "user", content: "Plan a launch week." },
            { id: "m2", role: "assistant", content: "Use a review-first weekly plan." },
          ],
          artifacts: [
            {
              id: "a1",
              title: "OpenClaw strategy result",
              payload: { target_platforms: ["linkedin", "facebook"] },
            },
          ],
        });
      }
      if (path === "/api/customer/campaigns") {
        if (init?.method === "POST") {
          return Promise.resolve({
            campaign: {
              id: "campaign-2",
              name: "Launch Week",
              status: "draft",
              approval_status: "pending",
              target_platforms: ["linkedin", "facebook"],
            },
          });
        }
        return Promise.resolve({
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
        });
      }
      if (path === "/api/customer/approvals") {
        return Promise.resolve({
          approvals: [
            {
              id: "campaign-3",
              name: "Pending Launch",
              status: "draft",
              approval_status: "pending",
              target_platforms: ["twitter"],
            },
          ],
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

  it("renders the customer workspace", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Customer Workspace")).toBeInTheDocument();
      expect(screen.getByText("Brand Onboarding")).toBeInTheDocument();
      expect(screen.getByDisplayValue("TripC")).toBeInTheDocument();
      expect(screen.getByText("Connected Accounts")).toBeInTheDocument();
      expect(screen.getByText("In-App OpenClaw Assistant")).toBeInTheDocument();
      expect(screen.getByText("AI Backbone Access")).toBeInTheDocument();
      expect(screen.getByText("Campaign Control")).toBeInTheDocument();
      expect(screen.getByText("Q2 Launch")).toBeInTheDocument();
      expect(screen.getByText("Launch teaser")).toBeInTheDocument();
    });
  });

  it("saves customer-provided AI backbone settings", async () => {
    render(<DashboardPage />);

    fireEvent.click(
      await screen.findByRole("radio", { name: /Bring Your API/i }),
    );
    fireEvent.change(screen.getByLabelText("Customer OpenClaw URL"), {
      target: { value: "https://customer-openclaw.example" },
    });
    fireEvent.change(screen.getByLabelText("Customer OpenClaw API Key"), {
      target: { value: "oc_customer_key" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save AI Backbone" }));

    await waitFor(() => {
      expect(customerApiRequest).toHaveBeenCalledWith(
        "/api/customer/ai-backbone",
        expect.objectContaining({
          method: "PUT",
        }),
      );
    });
  });

  it("creates a campaign draft from the dashboard", async () => {
    render(<DashboardPage />);

    const nameInput = await screen.findByLabelText("Campaign Name");
    fireEvent.change(nameInput, { target: { value: "Launch Week" } });

    const description = screen.getByLabelText("Description");
    fireEvent.change(description, { target: { value: "A launch sprint." } });

    fireEvent.click(screen.getByRole("button", { name: "Create Draft" }));

    await waitFor(() => {
      expect(customerApiRequest).toHaveBeenCalledWith(
        "/api/customer/campaigns",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
  });
});
