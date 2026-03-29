import { create } from "zustand";
import { devtools } from "zustand/middleware";

import {
  buildPersistedCustomerSession,
  clearPersistedCustomerSession,
  persistCustomerSession,
  readPersistedCustomerSession,
  type PersistedCustomerSession,
} from "@/lib/customer-session";
import {
  getSupabaseClient,
  hasSupabaseConfig,
  type SupabaseSession,
} from "@/lib/supabase";

interface CustomerUser {
  id: string;
  email: string;
  name?: string;
  avatarUrl?: string;
}

interface CustomerAuthState {
  user: CustomerUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  initialized: boolean;
  error: string | null;
  initialize: () => Promise<void>;
  establishSessionFromAccessToken: (
    accessToken: string,
    user?: {
      id: string;
      email: string;
      name?: string | null;
      avatar_url?: string | null;
    } | null,
  ) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  loginWithTelegram: (telegramData: any) => Promise<void>;
  signup: (payload: {
    email: string;
    password: string;
    name?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
}

let authSubscriptionBound = false;

function mapUser(
  session: SupabaseSession | null,
): Pick<CustomerAuthState, "user" | "accessToken" | "isAuthenticated"> {
  const user = session?.user;
  return {
    user: user
      ? {
          id: user.id,
          email: user.email || "",
          name:
            (user.user_metadata?.full_name as string | undefined) ||
            (user.user_metadata?.name as string | undefined) ||
            user.email?.split("@", 1)[0],
          avatarUrl: user.user_metadata?.avatar_url as string | undefined,
        }
      : null,
    accessToken: session?.access_token || null,
    isAuthenticated: Boolean(session?.access_token && user),
  };
}

async function establishSupabaseSession(
  accessToken: string,
): Promise<SupabaseSession | null> {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase.auth.setSession({
    access_token: accessToken,
    refresh_token: "",
  });

  if (error) {
    if (error.message === "Auth session missing!") {
      return null;
    }
    throw error;
  }

  return data.session;
}

function mapPersistedSession(
  persistedSession: PersistedCustomerSession | null,
): Pick<CustomerAuthState, "user" | "accessToken" | "isAuthenticated"> {
  return {
    user: persistedSession?.user || null,
    accessToken: persistedSession?.accessToken || null,
    isAuthenticated: Boolean(
      persistedSession?.accessToken && persistedSession?.user,
    ),
  };
}

function persistMappedSession(
  state: Pick<CustomerAuthState, "user" | "accessToken">,
): void {
  if (!state.user || !state.accessToken) {
    clearPersistedCustomerSession();
    return;
  }

  persistCustomerSession(
    buildPersistedCustomerSession(state.accessToken, {
      id: state.user.id,
      email: state.user.email,
      name: state.user.name,
      avatarUrl: state.user.avatarUrl,
    }),
  );
}

export const useCustomerAuthStore = create<CustomerAuthState>()(
  devtools((set, get) => ({
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: true,
    initialized: false,
    error: null,

    initialize: async () => {
      const persistedSession = readPersistedCustomerSession();

      if (!hasSupabaseConfig()) {
        set({
          ...mapPersistedSession(persistedSession),
          isLoading: false,
          initialized: true,
          error: persistedSession
            ? null
            : "Supabase public environment variables are missing.",
        });
        return;
      }

      const supabase = getSupabaseClient();

      if (!authSubscriptionBound) {
        supabase.auth.onAuthStateChange((_event, session) => {
          if (session) {
            const mapped = mapUser(session);
            persistMappedSession(mapped);
            set({
              ...mapped,
              isLoading: false,
              initialized: true,
              error: null,
            });
            return;
          }

          const storedSession = readPersistedCustomerSession();
          set({
            ...mapPersistedSession(storedSession),
            isLoading: false,
            initialized: true,
            error: null,
          });
        });
        authSubscriptionBound = true;
      }

      const { data, error } = await supabase.auth.getSession();
      if (error) {
        const storedSession = readPersistedCustomerSession();
        set({
          ...mapPersistedSession(storedSession),
          isLoading: false,
          initialized: true,
          error: storedSession ? null : error.message,
        });
        return;
      }

      const mapped = data.session
        ? mapUser(data.session)
        : mapPersistedSession(persistedSession);
      persistMappedSession(mapped);
      set({
        ...mapped,
        isLoading: false,
        initialized: true,
        error: null,
      });
    },

    establishSessionFromAccessToken: async (accessToken: string, user) => {
      set({ isLoading: true, error: null });
      try {
        const session = await establishSupabaseSession(accessToken);
        if (!session) {
          const persistedSession = buildPersistedCustomerSession(accessToken, {
            id: user?.id,
            email: user?.email,
            name: user?.name || undefined,
            avatar_url: user?.avatar_url || undefined,
          });
          if (!persistedSession) {
            throw new Error("Unable to establish customer session");
          }

          persistCustomerSession(persistedSession);
          set({
            ...mapPersistedSession(persistedSession),
            isLoading: false,
            initialized: true,
            error: null,
          });
          return;
        }

        const mapped = mapUser(session);
        persistMappedSession(mapped);
        set({
          ...mapped,
          isLoading: false,
          initialized: true,
          error: null,
        });
      } catch (err) {
        set({
          isLoading: false,
          error:
            err instanceof Error
              ? err.message
              : "Unable to establish customer session",
        });
        throw err;
      }
    },

    login: async (email: string, password: string) => {
      set({ isLoading: true, error: null });
      const supabase = getSupabaseClient();
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) {
        set({ isLoading: false, error: error.message });
        throw error;
      }
      persistMappedSession(mapUser(data.session));
      set({
        ...mapUser(data.session),
        isLoading: false,
        initialized: true,
        error: null,
      });
    },

    signup: async ({ email, password, name }) => {
      set({ isLoading: true, error: null });
      const supabase = getSupabaseClient();
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: name,
          },
        },
      });
      if (error) {
        set({ isLoading: false, error: error.message });
        throw error;
      }
      persistMappedSession(mapUser(data.session || null));
      set({
        ...mapUser(data.session || null),
        isLoading: false,
        initialized: true,
        error: null,
      });
    },

    loginWithTelegram: async (telegramData: any) => {
      set({ isLoading: true, error: null });
      try {
        const response = await fetch("/api/auth/telegram/login", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(telegramData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Telegram login failed");
        }

        const payload = await response.json();
        await get().establishSessionFromAccessToken(
          payload.access_token,
          payload.user || null,
        );
      } catch (err) {
        set({
          isLoading: false,
          error: err instanceof Error ? err.message : "Telegram login failed",
        });
        throw err;
      }
    },

    logout: async () => {
      clearPersistedCustomerSession();
      if (hasSupabaseConfig()) {
        await getSupabaseClient().auth.signOut();
      }
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        isLoading: false,
        initialized: true,
        error: null,
      });
    },
  })),
);
