import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

interface User {
  id: string;
  email: string;
  name?: string;
  avatar?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  // Actions
  setUser: (user: User | null) => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    persist(
      (set) => ({
        user: null,
        isAuthenticated: false,
        isLoading: true,

        setUser: (user) => set({ user, isAuthenticated: !!user }),

        login: async (email: string, password: string) => {
          const accessToken = password.trim();
          if (!accessToken) {
            throw new Error("Admin access token is required");
          }

          const normalizedEmail = email.trim() || "admin@local";
          const user: User = {
            id: "admin",
            email: normalizedEmail,
            name: "Admin",
          };

          localStorage.setItem("access_token", accessToken);
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        },

        logout: () => {
          set({ user: null, isAuthenticated: false });
          localStorage.removeItem("access_token");
        },

        checkAuth: async () => {
          set({ isLoading: true });

          try {
            const token = localStorage.getItem("access_token");
            if (!token) {
              set({ user: null, isAuthenticated: false, isLoading: false });
              return;
            }

            set({
              user: {
                id: "admin",
                email: "admin@local",
                name: "Admin",
              },
              isAuthenticated: true,
              isLoading: false,
            });
          } catch {
            localStorage.removeItem("access_token");
            set({ user: null, isAuthenticated: false, isLoading: false });
          }
        },
      }),
      {
        name: "auth-storage",
      },
    ),
  ),
);
