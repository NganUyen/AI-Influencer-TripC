import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import AuthPage from "@/app/auth/page";

const replace = jest.fn();
const initialize = jest.fn(() => Promise.resolve());
const establishSessionFromAccessToken = jest.fn(() => Promise.resolve());
const loginWithTelegram = jest.fn(() => Promise.resolve());
const mockSearchParamsGet = jest.fn(() => null);

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    replace,
  }),
  useSearchParams: () => ({
    get: mockSearchParamsGet,
  }),
}));

jest.mock("@/store/customer-auth-store", () => ({
  useCustomerAuthStore: (selector: (state: unknown) => unknown) =>
    selector({
      establishSessionFromAccessToken,
      loginWithTelegram,
      error: null,
      initialized: true,
      initialize,
      isAuthenticated: false,
    }),
}));

describe("Auth page", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    global.fetch = jest.fn();
    window.__AI_INFLUENCER_PUBLIC_ENV__ = {};
    mockSearchParamsGet.mockReturnValue(null);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("polls telegram link completion and redirects after establishing a session", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          start_token: "secure-token",
          expires_at: "2099-03-29T12:00:00Z",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "pending",
          expires_at: "2099-03-29T12:00:00Z",
          authenticated_at: null,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "authenticated",
          expires_at: "2099-03-29T12:00:00Z",
          authenticated_at: "2099-03-29T11:59:00Z",
          access_token: "telegram-access-token",
          refresh_token: "telegram-refresh-token",
          token_type: "bearer",
          expires_in: 3600,
          user: {
            id: "user-1",
            email: "founder@example.com",
            name: "Founder",
          },
        }),
      });

    render(<AuthPage />);

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "Continue with Telegram" }),
      );
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        1,
        "/api/auth/telegram/link/start",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        2,
        "/api/auth/telegram/link/complete",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    await act(async () => {
      jest.advanceTimersByTime(2500);
    });

    await waitFor(() => {
      expect(establishSessionFromAccessToken).toHaveBeenCalledWith(
        "telegram-access-token",
        expect.objectContaining({
          id: "user-1",
          email: "founder@example.com",
          name: "Founder",
        }),
        "telegram-refresh-token",
      );
    });
    expect(replace).toHaveBeenCalledWith("/dashboard");
    expect(screen.queryByText("Generate new link")).not.toBeInTheDocument();
  });

  it("redirects to safe next path after authentication", async () => {
    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "next" ? "/capture-handoff?token=abc" : null,
    );
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          start_token: "secure-token",
          expires_at: "2099-03-29T12:00:00Z",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "authenticated",
          expires_at: "2099-03-29T12:00:00Z",
          authenticated_at: "2099-03-29T11:59:00Z",
          access_token: "telegram-access-token",
          refresh_token: "telegram-refresh-token",
          user: {
            id: "user-1",
            email: "founder@example.com",
          },
        }),
      });

    render(<AuthPage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Continue with Telegram" }));
    });

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/capture-handoff?token=abc");
    });
  });
});
