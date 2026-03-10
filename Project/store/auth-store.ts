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
          try {
            // TODO: Implement actual authentication
            console.log("Login attempt:", email);

            // Mock user for now
            const mockUser: User = {
              id: "1",
              email,
              name: "Demo User",
            };

            set({ user: mockUser, isAuthenticated: true });
          } catch (error) {
            console.error("Login failed:", error);
            throw error;
          }
        },

        logout: () => {
          set({ user: null, isAuthenticated: false });
          localStorage.removeItem("access_token");
        },

        checkAuth: async () => {
          try {
            set({ isLoading: true });
            // TODO: Implement auth check with Supabase
            const token = localStorage.getItem("access_token");

            if (token) {
              // Mock check for now
              set({ isAuthenticated: true });
            }
          } catch (error) {
            console.error("Auth check failed:", error);
            set({ user: null, isAuthenticated: false });
          } finally {
            set({ isLoading: false });
          }
        },
      }),
      {
        name: "auth-storage",
      },
    ),
  ),
);
