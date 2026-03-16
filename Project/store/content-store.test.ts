import apiClient from "@/lib/api-client";
import { useContentStore } from "@/store/content-store";

jest.mock("@/lib/api-client", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

describe("useContentStore", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useContentStore.setState({
      items: [],
      isLoading: false,
      error: null,
    });
  });

  it("fetches and maps content items", async () => {
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: {
        items: [
          {
            id: "wf-1",
            title: "Workflow wf-1",
            content: "Status: running",
            platform: ["twitter"],
            status: "draft",
            scheduledAt: "2026-03-16T10:00:00.000Z",
            publishedAt: null,
            mediaUrls: ["https://cdn.example/1.jpg"],
            createdAt: "2026-03-16T09:00:00.000Z",
            updatedAt: "2026-03-16T09:30:00.000Z",
          },
        ],
      },
    });

    await useContentStore.getState().fetchItems();

    const state = useContentStore.getState();
    expect(state.error).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.items).toHaveLength(1);
    expect(state.items[0].id).toBe("wf-1");
    expect(state.items[0].scheduledAt).toBeInstanceOf(Date);
    expect(state.items[0].createdAt).toBeInstanceOf(Date);
  });

  it("sets fallback error on fetch failure", async () => {
    (apiClient.get as jest.Mock).mockRejectedValue(new Error("request failed"));

    await useContentStore.getState().fetchItems();

    const state = useContentStore.getState();
    expect(state.error).toBe("Failed to fetch content");
    expect(state.isLoading).toBe(false);
    expect(state.items).toHaveLength(0);
  });
});
