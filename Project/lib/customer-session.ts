export interface PersistedCustomerUser {
  id: string;
  email: string;
  name?: string;
  avatarUrl?: string;
}

export interface PersistedCustomerSession {
  accessToken: string;
  user: PersistedCustomerUser;
  expiresAt: number | null;
}

const CUSTOMER_SESSION_STORAGE_KEY = "ai-influencer.customer-session";

function hasBrowserStorage(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.localStorage !== "undefined"
  );
}

function decodeBase64Url(value: string): string | null {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(
    normalized.length + ((4 - (normalized.length % 4 || 4)) % 4),
    "=",
  );

  if (typeof globalThis.atob === "function") {
    return globalThis.atob(padded);
  }

  if (typeof Buffer !== "undefined") {
    return Buffer.from(padded, "base64").toString("utf-8");
  }

  return null;
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".");
  if (parts.length < 2) {
    return null;
  }

  try {
    const decoded = decodeBase64Url(parts[1]);
    if (!decoded) {
      return null;
    }
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function normalizeString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function normalizeUser(
  payload: Record<string, unknown> | null,
  user?: Partial<PersistedCustomerUser> & {
    avatar_url?: string | null;
  },
): PersistedCustomerUser | null {
  const userMetadata =
    payload && typeof payload.user_metadata === "object" && payload.user_metadata
      ? (payload.user_metadata as Record<string, unknown>)
      : null;

  const id =
    normalizeString(user?.id) || normalizeString(payload?.sub);
  const email =
    normalizeString(user?.email) || normalizeString(payload?.email);

  if (!id || !email) {
    return null;
  }

  const name =
    normalizeString(user?.name) ||
    normalizeString(userMetadata?.full_name) ||
    normalizeString(userMetadata?.name) ||
    email.split("@", 1)[0];
  const avatarUrl =
    normalizeString(user?.avatarUrl) ||
    normalizeString(user?.avatar_url) ||
    normalizeString(userMetadata?.avatar_url);

  return {
    id,
    email,
    ...(name ? { name } : {}),
    ...(avatarUrl ? { avatarUrl } : {}),
  };
}

function isExpired(expiresAt: number | null): boolean {
  return typeof expiresAt === "number" && Number.isFinite(expiresAt)
    ? Date.now() >= expiresAt
    : false;
}

export function buildPersistedCustomerSession(
  accessToken: string,
  user?: Partial<PersistedCustomerUser> & {
    avatar_url?: string | null;
  },
): PersistedCustomerSession | null {
  const normalizedAccessToken = accessToken.trim();
  if (!normalizedAccessToken) {
    return null;
  }

  const payload = decodeJwtPayload(normalizedAccessToken);
  const normalizedUser = normalizeUser(payload, user);
  if (!normalizedUser) {
    return null;
  }

  const exp =
    payload && typeof payload.exp === "number" && Number.isFinite(payload.exp)
      ? payload.exp * 1000
      : null;

  return {
    accessToken: normalizedAccessToken,
    user: normalizedUser,
    expiresAt: exp,
  };
}

export function persistCustomerSession(
  session: PersistedCustomerSession | null,
): void {
  if (!hasBrowserStorage()) {
    return;
  }

  if (!session) {
    window.localStorage.removeItem(CUSTOMER_SESSION_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(
    CUSTOMER_SESSION_STORAGE_KEY,
    JSON.stringify(session),
  );
}

export function readPersistedCustomerSession(): PersistedCustomerSession | null {
  if (!hasBrowserStorage()) {
    return null;
  }

  const raw = window.localStorage.getItem(CUSTOMER_SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as PersistedCustomerSession;
    const rebuilt = buildPersistedCustomerSession(parsed.accessToken, parsed.user);
    if (!rebuilt || isExpired(rebuilt.expiresAt)) {
      persistCustomerSession(null);
      return null;
    }
    return rebuilt;
  } catch {
    persistCustomerSession(null);
    return null;
  }
}

export function clearPersistedCustomerSession(): void {
  persistCustomerSession(null);
}
