import {
  buildPersistedCustomerSession,
  clearPersistedCustomerSession,
  persistCustomerSession,
  readPersistedCustomerSession,
} from "@/lib/customer-session";

function createToken(payload: Record<string, unknown>): string {
  const encode = (value: Record<string, unknown>) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(payload)}.signature`;
}

describe("customer-session helpers", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("builds and persists a customer session from a JWT payload", () => {
    const token = createToken({
      sub: "user-1",
      email: "founder@example.com",
      exp: 4102444800,
      user_metadata: {
        full_name: "Founder",
        avatar_url: "https://example.com/avatar.png",
      },
    });

    const session = buildPersistedCustomerSession(token);
    expect(session).toEqual({
      accessToken: token,
      expiresAt: 4102444800 * 1000,
      user: {
        id: "user-1",
        email: "founder@example.com",
        name: "Founder",
        avatarUrl: "https://example.com/avatar.png",
      },
    });

    persistCustomerSession(session);
    expect(readPersistedCustomerSession()).toEqual(session);
  });

  it("drops expired persisted sessions", () => {
    const token = createToken({
      sub: "user-2",
      email: "expired@example.com",
      exp: 1,
      user_metadata: {
        name: "Expired",
      },
    });

    persistCustomerSession(buildPersistedCustomerSession(token));
    expect(readPersistedCustomerSession()).toBeNull();

    clearPersistedCustomerSession();
    expect(window.localStorage.getItem("ai-influencer.customer-session")).toBeNull();
  });
});
