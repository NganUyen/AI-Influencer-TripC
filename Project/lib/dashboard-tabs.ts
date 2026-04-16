export type DashboardTabId = "overview" | "ops" | "skills" | "memory" | "create_video" | "publishing";

export const DEFAULT_DASHBOARD_TAB: DashboardTabId = "overview";

const DASHBOARD_TAB_SEGMENTS: Record<Exclude<DashboardTabId, "overview">, string> = {
  ops: "operations",
  skills: "personas",
  memory: "memory",
  create_video: "create-video",
  publishing: "publishing",
};

const DASHBOARD_SEGMENT_TO_TAB: Record<string, DashboardTabId> = {
  operations: "ops",
  personas: "skills",
  memory: "memory",
  "create-video": "create_video",
  publishing: "publishing",
};

export function getDashboardTabHref(tabId: DashboardTabId): string {
  if (tabId === DEFAULT_DASHBOARD_TAB) {
    return "/dashboard";
  }

  const segment = DASHBOARD_TAB_SEGMENTS[tabId as Exclude<DashboardTabId, "overview">];

  return `/dashboard/${segment}`;
}

export function getDashboardTabIdFromSegments(segments?: string[]): DashboardTabId | null {
  if (!segments || segments.length === 0) {
    return DEFAULT_DASHBOARD_TAB;
  }

  if (segments.length !== 1) {
    return null;
  }

  return DASHBOARD_SEGMENT_TO_TAB[segments[0]] ?? null;
}
