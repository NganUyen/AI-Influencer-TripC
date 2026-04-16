import {
  buildPersistedCustomerSession,
  persistCustomerSession,
} from "@/lib/customer-session";
import { customerApiRequest } from "@/lib/customer-api";

const getSession = jest.fn();

jest.mock("@/lib/supabase", () => ({
  getSupabaseClient: () => ({
    auth: {
      getSession,
    },
  }),
}));

function createToken(payload: Record<string, unknown>): string {
  const encode = (value: Record<string, unknown>) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(payload)}.signature`;
}

describe("customerApiRequest", () => {
  beforeEach(() => {
    window.localStorage.clear();
    jest.clearAllMocks();
    getSession.mockResolvedValue({
      data: { session: null },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
  });

  it("falls back to the persisted customer session token when Supabase has no session", async () => {
    const token = createToken({
      sub: "user-1",
      email: "founder@example.com",
      exp: 4102444800,
      user_metadata: {
        full_name: "Founder",
      },
    });

    persistCustomerSession(buildPersistedCustomerSession(token));

    await customerApiRequest("/api/customer/example");

    const [, init] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit,
    ];
    const headers = new Headers(init.headers);

    expect(headers.get("Authorization")).toBe(`Bearer ${token}`);
  });

  it("replaces raw HTML error pages with a status-based message", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 502,
      headers: new Headers({ "content-type": "text/html" }),
      text: async () =>
        "<html><body><center>openresty</center></body></html>",
    });

    await expect(
      customerApiRequest("/api/customer/example"),
    ).rejects.toThrow("Customer API request failed with status 502");
  });

  it("preserves explicit non-json content types for binary uploads", async () => {
    const payload = new Blob(["video-bytes"], { type: "video/mp4" });

    await customerApiRequest("/api/customer/review-engine/jobs/job-1/upload", {
      method: "POST",
      headers: {
        "Content-Type": "video/mp4",
        "x-filename": "review.mp4",
      },
      body: payload,
    });

    const [, init] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit,
    ];
    const headers = new Headers(init.headers);

    expect(headers.get("Content-Type")).toBe("video/mp4");
    expect(headers.get("x-filename")).toBe("review.mp4");
  });
});
