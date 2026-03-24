import { create } from "zustand";
import { devtools } from "zustand/middleware";

import { hasSupabaseConfig, supabase } from "@/lib/supabase";

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
  login: (email: string, password: string) => Promise<void>;
  signup: (payload: {
    email: string;
    password: string;
    name?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
}

let authSubscriptionBound = false;

function mapUser(session: Awaited<
  ReturnType<typeof supabase.auth.getSession>
>["data"]["session"]): Pick<CustomerAuthState, "user" | "accessToken" | "isAuthenticated"> {
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

export const useCustomerAuthStore = create<CustomerAuthState>()(
  devtools((set, get) => ({
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: true,
    initialized: false,
    error: null,

    initialize: async () => {
      if (!hasSupabaseConfig) {
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
          isLoading: false,
          initialized: true,
          error: "Supabase public environment variables are missing.",
        });
        return;
      }

      if (!authSubscriptionBound) {
        supabase.auth.onAuthStateChange((_event, session) => {
          set({
            ...mapUser(session),
            isLoading: false,
            initialized: true,
            error: null,
          });
        });
        authSubscriptionBound = true;
      }

      const { data, error } = await supabase.auth.getSession();
      if (error) {
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
          isLoading: false,
          initialized: true,
          error: error.message,
        });
        return;
      }

      set({
        ...mapUser(data.session),
        isLoading: false,
        initialized: true,
        error: null,
      });
    },

    login: async (email: string, password: string) => {
      set({ isLoading: true, error: null });
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) {
        set({ isLoading: false, error: error.message });
        throw error;
      }
      set({
        ...mapUser(data.session),
        isLoading: false,
        initialized: true,
        error: null,
      });
    },

    signup: async ({ email, password, name }) => {
      set({ isLoading: true, error: null });
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
      set({
        ...mapUser(data.session || null),
        isLoading: false,
        initialized: true,
        error: null,
      });
    },

    logout: async () => {
      if (hasSupabaseConfig) {
        await supabase.auth.signOut();
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
