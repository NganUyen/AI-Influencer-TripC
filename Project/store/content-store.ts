import { create } from "zustand";
import { devtools } from "zustand/middleware";

export interface ContentItem {
  id: string;
  title: string;
  content: string;
  platform: string[];
  status: "draft" | "scheduled" | "published" | "failed";
  scheduledAt?: Date;
  publishedAt?: Date;
  mediaUrls?: string[];
  createdAt: Date;
  updatedAt: Date;
}

interface ContentState {
  items: ContentItem[];
  isLoading: boolean;
  error: string | null;

  // Actions
  setItems: (items: ContentItem[]) => void;
  addItem: (item: ContentItem) => void;
  updateItem: (id: string, updates: Partial<ContentItem>) => void;
  deleteItem: (id: string) => void;
  fetchItems: () => Promise<void>;
}

export const useContentStore = create<ContentState>()(
  devtools((set, get) => ({
    items: [],
    isLoading: false,
    error: null,

    setItems: (items) => set({ items }),

    addItem: (item) => set((state) => ({ items: [item, ...state.items] })),

    updateItem: (id, updates) =>
      set((state) => ({
        items: state.items.map((item) =>
          item.id === id ? { ...item, ...updates } : item,
        ),
      })),

    deleteItem: (id) =>
      set((state) => ({
        items: state.items.filter((item) => item.id !== id),
      })),

    fetchItems: async () => {
      try {
        set({ isLoading: true, error: null });
        // TODO: Implement API call to fetch content
        // const response = await apiClient.get("/api/content");
        // set({ items: response.data });
        set({ isLoading: false });
      } catch (error) {
        set({ error: "Failed to fetch content", isLoading: false });
      }
    },
  })),
);
