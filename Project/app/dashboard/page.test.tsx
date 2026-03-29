import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ButtonHTMLAttributes } from "react";

import DashboardPage from "@/app/dashboard/page";
import { customerApiRequest } from "@/lib/customer-api";

jest.mock("@/lib/customer-api", () => ({
  customerApiRequest: jest.fn(),
}));

jest.mock("framer-motion", () => ({
  motion: {
    button: ({
      children,
      ...props
    }: ButtonHTMLAttributes<HTMLButtonElement>) => (
      <button {...props}>{children}</button>
    ),
  },
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
    jest.useFakeTimers();

    let telegramLinkStatusCalls = 0;

    (customerApiRequest as jest.Mock).mockImplementation((path: string, init?: RequestInit) => {
      if (path === "/api/customer/system/summary") {
        return Promise.resolve({ services: [], quota: [] });
      }
      if (path === "/api/customer/system/workflows") {
        return Promise.resolve({ workflows: [] });
      }
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
      if (path === "/api/customer/assistant/threads") {
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
          artifacts: [],
        });
      }
      if (path === "/api/customer/campaigns") {
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
      if (path === "/api/customer/ai-backbone") {
        return Promise.resolve({
          settings: {
            access_mode: "workspace_default",
            workspace_default: {
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
        });
      }
      if (path === "/api/customer/personas") {
        return Promise.resolve({ personas: [] });
      }
      if (path === "/api/customer/telegram/link") {
        telegramLinkStatusCalls += 1;
        if (telegramLinkStatusCalls >= 3) {
          return Promise.resolve({
            linked: true,
            link: {
              telegram_username: "tripc",
              chat_id: "123456789",
            },
          });
        }
        return Promise.resolve({ linked: false });
      }
      if (path === "/api/customer/telegram/link/start") {
        return Promise.resolve({
          start_token: "secure-link-token",
          expires_at: "2099-03-29T12:00:00Z",
        });
      }
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("renders the current dashboard shell", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("SkyNet")).toBeInTheDocument();
      expect(screen.getByText("Quick Stats")).toBeInTheDocument();
      expect(screen.getByText("Tổng quan")).toBeInTheDocument();
    });
  });

  it("refreshes telegram link status in place after connect", async () => {
    render(<DashboardPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Dự án & Memory" }));
    fireEvent.click(await screen.findByRole("button", { name: "Connect Telegram" }));

    await waitFor(() => {
      expect(customerApiRequest).toHaveBeenCalledWith(
        "/api/customer/telegram/link/start",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    expect(
      await screen.findByText(
        "Waiting for Telegram confirmation. This card updates automatically.",
      ),
    ).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(2500);
    });

    await waitFor(() => {
      expect(screen.getByText("@tripc")).toBeInTheDocument();
      expect(screen.getByText("Linked")).toBeInTheDocument();
    });

    expect(
      (customerApiRequest as jest.Mock).mock.calls.filter(
        ([path]) => path === "/api/customer/brand",
      ),
    ).toHaveLength(1);
  });
});
