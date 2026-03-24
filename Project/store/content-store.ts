import { create } from "zustand";
import { devtools } from "zustand/middleware";
import apiClient from "@/lib/api-client";

export interface ContentItem {
  id: string;
  workflowId?: string;
  logicalPostId?: string;
  workflowStatus?: string;
  currentStep?: string;
  approvalFeedback?: string;
  title: string;
  content: string;
  platform: string[];
  status: "draft" | "pending_approval" | "scheduled" | "published" | "failed";
  platformPostId?: string;
  providerPostId?: string;
  postUrl?: string;
  publishMethod?: string;
  publishError?: string;
  engagementMetrics?: Record<string, unknown>;
  lastEngagementCheckedAt?: Date;
  syndicateTriggered?: boolean;
  syndicateJobId?: string;
  scheduledAt?: Date;
  publishedAt?: Date;
  mediaUrls?: string[];
  createdAt: Date;
  updatedAt: Date;
}

interface WorkflowListItem {
  id: string;
  workflowId?: string;
  logicalPostId?: string;
  workflowStatus?: string;
  currentStep?: string;
  approvalFeedback?: string;
  title: string;
  content: string;
  platform: string[];
  status: ContentItem["status"];
  platformPostId?: string;
  providerPostId?: string;
  postUrl?: string;
  publishMethod?: string;
  publishError?: string;
  engagementMetrics?: Record<string, unknown>;
  lastEngagementCheckedAt?: string | null;
  syndicateTriggered?: boolean;
  syndicateJobId?: string;
  scheduledAt?: string | null;
  publishedAt?: string | null;
  mediaUrls?: string[];
  createdAt?: string | null;
  updatedAt?: string | null;
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
  devtools((set) => ({
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
        const response = await apiClient.get<{ items: WorkflowListItem[] }>(
          "/api/content/list",
          {
            params: { limit: 50 },
          },
        );

        const items = (response.data.items || []).map((item) => {
          const createdAt = item.createdAt
            ? new Date(item.createdAt)
            : new Date();
          const updatedAt = item.updatedAt
            ? new Date(item.updatedAt)
            : createdAt;
          const lastEngagementCheckedAt = item.lastEngagementCheckedAt
            ? new Date(item.lastEngagementCheckedAt)
            : undefined;

          return {
            id: item.id,
            workflowId: item.workflowId,
            logicalPostId: item.logicalPostId,
            workflowStatus: item.workflowStatus,
            currentStep: item.currentStep,
            approvalFeedback: item.approvalFeedback,
            title: item.title,
            content: item.content,
            platform: item.platform || [],
            status: item.status,
            platformPostId: item.platformPostId,
            providerPostId: item.providerPostId,
            postUrl: item.postUrl,
            publishMethod: item.publishMethod,
            publishError: item.publishError,
            engagementMetrics: item.engagementMetrics,
            lastEngagementCheckedAt,
            syndicateTriggered: item.syndicateTriggered,
            syndicateJobId: item.syndicateJobId,
            scheduledAt: item.scheduledAt
              ? new Date(item.scheduledAt)
              : undefined,
            publishedAt: item.publishedAt
              ? new Date(item.publishedAt)
              : undefined,
            mediaUrls: item.mediaUrls || [],
            createdAt,
            updatedAt,
          } satisfies ContentItem;
        });

        set({ items, isLoading: false });
      } catch {
        set({ error: "Failed to fetch content", isLoading: false });
      }
    },
  })),
);
