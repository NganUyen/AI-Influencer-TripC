"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FileText, Rocket, BarChart3, Users } from "lucide-react";
import apiClient from "@/lib/api-client";
import { WORKFLOW_POLL_INTERVAL } from "@/config/constants";
import { useContentStore, type ContentItem } from "@/store/content-store";

interface WorkflowListItem {
  workflow_id: string;
  run_id: string;
  status: string;
  start_time?: string;
}

interface WorkflowStatusPayload {
  status: string;
  current_step?: string;
  approval_received?: boolean;
  approval_feedback?: string;
  workflow_id: string;
}

interface DashboardWorkflow extends WorkflowListItem {
  details?: WorkflowStatusPayload;
}

interface ContentStats {
  total_content: number;
  active_campaigns: number;
  published: number;
}

interface AnalyticsSummary {
  average_engagement_rate: number | null;
}

interface QuotaProviderSummary {
  provider: string;
  label: string;
  status: string;
  usage_unit: string;
  monthly_limit: number | null;
  cost_usd: number;
  usage: Record<string, number>;
  usage_value?: number | null;
  snapshot_count: number;
  remaining_value?: number | null;
  remaining_limit?: number | null;
  remaining_unit?: string | null;
  remaining_exact?: boolean;
  remaining_source?: string;
  remaining_message?: string;
  remaining_reset_at?: string | null;
  remaining_reset_after?: string | null;
  remaining_requests?: number | null;
  remaining_requests_limit?: number | null;
  remaining_requests_reset_at?: string | null;
  remaining_requests_reset_after?: string | null;
}

interface QuotaSummary {
  total_cost_usd: number;
  providers: QuotaProviderSummary[];
  time_period: string;
}

export default function DashboardPage() {
  const [workflows, setWorkflows] = useState<DashboardWorkflow[]>([]);
  const [stats, setStats] = useState<ContentStats>({
    total_content: 0,
    active_campaigns: 0,
    published: 0,
  });
  const [analytics, setAnalytics] = useState<AnalyticsSummary>({
    average_engagement_rate: null,
  });
  const [quota, setQuota] = useState<QuotaSummary>({
    total_cost_usd: 0,
    providers: [],
    time_period: "30_days",
  });
  const [retryingContentIds, setRetryingContentIds] = useState<string[]>([]);
  const [retryStartedContentIds, setRetryStartedContentIds] = useState<string[]>(
    [],
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { items: contentItems, fetchItems } = useContentStore();

  const loadDashboardData = useCallback(async () => {
    try {
      const [listResponse, statsResponse, analyticsResponse, quotaResponse] = await Promise.all([
        apiClient.get<{
          workflows: WorkflowListItem[];
        }>("/api/workflows/list", { params: { limit: 10 } }),
        apiClient.get<ContentStats>("/api/content/stats"),
        apiClient
          .get<AnalyticsSummary>("/api/analytics/summary")
          .catch(() => ({ data: { average_engagement_rate: null } })),
        apiClient
          .get<QuotaSummary>("/api/quota/summary")
          .catch(() => ({ data: { total_cost_usd: 0, providers: [], time_period: "30_days" } })),
      ]);
      setStats(statsResponse.data);
      setAnalytics(analyticsResponse.data);
      setQuota(quotaResponse.data);
      await fetchItems();

      const baseWorkflows = listResponse.data.workflows || [];

      const detailedStatuses = await Promise.all(
        baseWorkflows.map(async (item) => {
          try {
            const statusResponse = await apiClient.get<{
              workflow_id: string;
              status: WorkflowStatusPayload;
            }>(`/api/workflows/status/${item.workflow_id}`);
            return {
              ...item,
              details: statusResponse.data.status,
            };
          } catch {
            return item;
          }
        }),
      );

      setWorkflows(detailedStatuses);
      setError(null);
    } catch {
      setError("Failed to load dashboard data");
    } finally {
      setIsLoading(false);
    }
  }, [fetchItems]);

  useEffect(() => {
    loadDashboardData();
    const poller = setInterval(loadDashboardData, WORKFLOW_POLL_INTERVAL);
    return () => clearInterval(poller);
  }, [loadDashboardData]);

  const runningCount = useMemo(
    () =>
      workflows.filter((workflow) => {
        const status = workflow.details?.status || workflow.status;
        return status === "running" || status === "waiting_approval";
      }).length,
    [workflows],
  );

  const completedCount = useMemo(() => stats.published, [stats]);
  const engagementRateValue = useMemo(() => {
    const rate = analytics.average_engagement_rate;
    return typeof rate === "number" && Number.isFinite(rate)
      ? `${rate.toFixed(1)}%`
      : "N/A";
  }, [analytics.average_engagement_rate]);

  const upcomingPosts = useMemo(
    () =>
      contentItems
        .filter((item) => item.status === "scheduled" && item.scheduledAt)
        .sort((a, b) => {
          const aTime = a.scheduledAt?.getTime() || 0;
          const bTime = b.scheduledAt?.getTime() || 0;
          return aTime - bTime;
        })
        .slice(0, 5),
    [contentItems],
  );
  const quotaProviders = useMemo(
    () => quota.providers.slice(0, 6),
    [quota.providers],
  );

  const waitingApproval = useMemo(
    () =>
      workflows.filter((workflow) => {
        const status = workflow.details?.status || workflow.status;
        return status === "waiting_approval";
      }),
    [workflows],
  );

  const handleApproval = useCallback(
    async (workflowId: string, approved: boolean) => {
      await apiClient.post(`/api/workflows/approve/${workflowId}`, {
        approved,
        feedback: approved
          ? "Approved from dashboard"
          : "Rejected from dashboard",
      });
      await loadDashboardData();
    },
    [loadDashboardData],
  );

  const handleRetryPublish = useCallback(
    async (contentId: string) => {
      setRetryingContentIds((current) =>
        current.includes(contentId) ? current : [...current, contentId],
      );
      try {
        await apiClient.post(`/api/content/retry/${contentId}`);
        setRetryStartedContentIds((current) =>
          current.includes(contentId) ? current : [...current, contentId],
        );
        await loadDashboardData();
      } catch {
        setError("Failed to retry publish");
      } finally {
        setRetryingContentIds((current) =>
          current.filter((itemId) => itemId !== contentId),
        );
      }
    },
    [loadDashboardData],
  );

  return (
    <div className="min-h-screen bg-zinc-950">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white mb-8">
          Dashboard
        </h1>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Content"
            value={String(stats.total_content)}
            icon={<FileText className="h-5 w-5 text-emerald-400" strokeWidth={2} />}
          />
          <StatCard
            title="Active Campaigns"
            value={String(Math.max(runningCount, stats.active_campaigns))}
            icon={<Rocket className="h-5 w-5 text-emerald-400" strokeWidth={2} />}
          />
          <StatCard 
            title="Engagement Rate" 
            value={engagementRateValue} 
            icon={<BarChart3 className="h-5 w-5 text-emerald-400" strokeWidth={2} />} 
          />
          <StatCard 
            title="AI Personas" 
            value="0" 
            icon={<Users className="h-5 w-5 text-emerald-400" strokeWidth={2} />} 
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-[32px] border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl p-6">
            <h2 className="text-xl font-semibold tracking-tight mb-4 text-white">
              Recent Content
            </h2>
            {isLoading && (
              <p className="text-zinc-400">
                Loading workflows...
              </p>
            )}

            {!isLoading && error && (
              <p className="text-rose-400">{error}</p>
            )}

            {!isLoading && !error && contentItems.length === 0 && (
              <p className="text-zinc-400">
                No content generated yet. Start your first campaign!
              </p>
            )}

            {!isLoading && !error && contentItems.length > 0 && (
              <div className="space-y-3">
                {contentItems.slice(0, 5).map((item) => {
                  const workflowLinkId = item.workflowId || item.id;
                  const linkedWorkflow = workflows.find(
                    (workflow) => workflow.workflow_id === workflowLinkId,
                  );
                  const workflowStatus =
                    item.workflowStatus ||
                    linkedWorkflow?.details?.status ||
                    linkedWorkflow?.status;
                  const currentStep =
                    item.currentStep || linkedWorkflow?.details?.current_step;
                  const approvalWorkflowId =
                    item.workflowId || linkedWorkflow?.workflow_id;
                  const canRetryPublish =
                    item.status === "failed" && item.platform.length > 0;
                  const isRetrying = retryingContentIds.includes(item.id);
                  const retryStarted = retryStartedContentIds.includes(item.id);
                  const engagementSummary = formatEngagementSummary(
                    item.engagementMetrics,
                  );

                  return (
                    <div
                      key={item.id}
                      className="border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl rounded-[16px] p-3"
                    >
                      <p className="text-sm font-medium text-white break-all">
                        {item.title}
                      </p>
                      <p className="text-xs text-zinc-400 mt-1">
                        Content Status: {humanizeValue(item.status)}
                      </p>
                      {workflowStatus && (
                        <p className="text-xs text-zinc-400">
                          Workflow Status: {humanizeValue(workflowStatus)}
                        </p>
                      )}
                      {item.workflowId && (
                        <p className="text-xs text-zinc-400 break-all">
                          Workflow: {item.workflowId}
                        </p>
                      )}
                      {currentStep && (
                        <p className="text-xs text-zinc-400">
                          Step: {humanizeValue(currentStep)}
                        </p>
                      )}
                      {item.platform.length > 0 && (
                        <p className="text-xs text-zinc-400">
                          Platform: {item.platform.join(", ")}
                        </p>
                      )}
                      {item.scheduledAt && (
                        <p className="text-xs text-zinc-400">
                          Scheduled: {formatDateTime(item.scheduledAt)}
                        </p>
                      )}
                      {item.publishedAt && (
                        <p className="text-xs text-zinc-400">
                          Published: {formatDateTime(item.publishedAt)}
                        </p>
                      )}
                      {item.publishMethod && (
                        <p className="text-xs text-zinc-400">
                          Method: {humanizeValue(item.publishMethod)}
                        </p>
                      )}
                      {item.postUrl && (
                        <a
                          href={item.postUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex mt-2 text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-200"
                        >
                          Open post
                        </a>
                      )}
                      {engagementSummary && (
                        <p className="text-xs text-zinc-400 mt-2">
                          Engagement: {engagementSummary}
                        </p>
                      )}
                      {item.lastEngagementCheckedAt && (
                        <p className="text-xs text-zinc-400">
                          Last check: {formatDateTime(item.lastEngagementCheckedAt)}
                        </p>
                      )}
                      {item.syndicateTriggered && item.syndicateJobId && (
                        <p className="text-xs text-zinc-400">
                          Syndicate job: {item.syndicateJobId}
                        </p>
                      )}
                      {item.syndicateTriggered && !item.syndicateJobId && (
                        <p className="text-xs text-zinc-400">
                          Syndicate triggered
                        </p>
                      )}
                      {!item.syndicateTriggered && item.lastEngagementCheckedAt && (
                        <p className="text-xs text-zinc-400">
                          Syndicate not triggered
                        </p>
                      )}
                      {item.publishError && (
                        <p className="text-xs text-rose-400 mt-2">
                          Publish error: {item.publishError}
                        </p>
                      )}
                      {retryStarted && (
                        <p className="text-xs text-emerald-400 mt-2">
                          Retry workflow started.
                        </p>
                      )}
                      {item.status === "pending_approval" && approvalWorkflowId && (
                        <div className="flex gap-2 mt-3">
                          <button
                            type="button"
                            onClick={() => handleApproval(approvalWorkflowId, true)}
                            className="px-4 py-2 text-xs font-semibold bg-emerald-500 text-white rounded-[14px] shadow-lg shadow-emerald-500/20 transition-all duration-200 ease-out hover:bg-emerald-400 hover:shadow-emerald-500/30 active:scale-[0.98]"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => handleApproval(approvalWorkflowId, false)}
                            className="px-4 py-2 text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded-[14px] transition-all duration-200 ease-out hover:bg-rose-500/20 active:scale-[0.98]"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                      {canRetryPublish && (
                        <div className="flex gap-2 mt-3">
                          <button
                            type="button"
                            onClick={() => handleRetryPublish(item.id)}
                            disabled={isRetrying}
                            className="px-4 py-2 text-xs font-semibold bg-amber-500 text-zinc-950 rounded-[14px] shadow-lg shadow-amber-500/20 transition-all duration-200 ease-out hover:bg-amber-400 hover:shadow-amber-500/30 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {isRetrying ? "Retrying..." : "Retry Publish"}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="rounded-[32px] border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl p-6">
            <h2 className="text-xl font-semibold tracking-tight mb-4 text-white">
              Upcoming Posts
            </h2>
            {upcomingPosts.length > 0 ? (
              <div className="space-y-3">
                {upcomingPosts.map((item) => (
                  <div
                    key={item.id}
                    className="border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl rounded-[16px] p-3"
                  >
                    <p className="text-sm font-medium text-white break-all">
                      {item.title}
                    </p>
                    <p className="text-xs text-zinc-400 mt-1">
                      Scheduled: {formatDateTime(item.scheduledAt!)}
                    </p>
                    {item.platform.length > 0 && (
                      <p className="text-xs text-zinc-400 mt-1">
                        Platform: {item.platform.join(", ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : completedCount > 0 ? (
              <p className="text-zinc-400">
                No upcoming scheduled posts. Recent workflows may already be
                published.
              </p>
            ) : (
              <p className="text-zinc-400">
                No scheduled posts. Create a content calendar!
              </p>
            )}

            {waitingApproval.length > 0 && (
              <p className="text-sm text-amber-400 mt-3">
                {waitingApproval.length} workflow(s) waiting for approval.
              </p>
            )}
          </div>
        </div>

        <div className="rounded-[32px] border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl p-6 mt-6">
          <div className="flex items-center justify-between gap-4 mb-4">
            <h2 className="text-xl font-semibold tracking-tight text-white">
              API Usage
            </h2>
            <p className="text-sm text-zinc-400">
              Total cost tracked: {formatCurrency(quota.total_cost_usd)}
            </p>
          </div>
          {quotaProviders.length > 0 ? (
            <div className="space-y-3">
              {quotaProviders.map((provider) => (
                <div
                  key={provider.provider}
                  className="border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl rounded-[16px] p-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">
                        {provider.label}
                      </p>
                      <p className="text-xs text-zinc-400">
                        {formatQuotaRemaining(provider)}
                      </p>
                      <p className="text-xs text-zinc-400 mt-1">
                        {provider.remaining_message || formatQuotaUsage(provider)}
                      </p>
                      {formatRequestRemaining(provider) && (
                        <p className="text-xs text-zinc-400 mt-1">
                          {formatRequestRemaining(provider)}
                        </p>
                      )}
                      {formatQuotaReset(provider) && (
                        <p className="text-xs text-zinc-400 mt-1">
                          {formatQuotaReset(provider)}
                        </p>
                      )}
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${quotaStatusClasses(provider.status)}`}
                    >
                      {humanizeValue(provider.status)}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-zinc-400">
                    <span>Snapshots: {provider.snapshot_count}</span>
                    <span>Cost: {formatCurrency(provider.cost_usd)}</span>
                    {formatTrackedUsage(provider) && (
                      <span>{formatTrackedUsage(provider)}</span>
                    )}
                    {provider.monthly_limit !== null && provider.monthly_limit !== undefined && (
                      <span>
                        Limit: {formatQuotaNumber(provider.monthly_limit)}{" "}
                        {provider.usage_unit}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-zinc-400">
              No API usage snapshots yet. Runtime calls and manual snapshots will
              appear here.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function formatDateTime(date: Date): string {
  return `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

function humanizeValue(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatEngagementSummary(
  metrics?: ContentItem["engagementMetrics"],
): string | null {
  if (!metrics) {
    return null;
  }

  const parts: string[] = [];
  const likes = toDisplayNumber(metrics.likes);
  const comments = toDisplayNumber(metrics.comments);
  const shares = toDisplayNumber(metrics.shares);
  const engagementRate = toDisplayNumber(metrics.engagement_rate);

  if (likes !== null) {
    parts.push(`Likes ${likes}`);
  }
  if (comments !== null) {
    parts.push(`Comments ${comments}`);
  }
  if (shares !== null) {
    parts.push(`Shares ${shares}`);
  }
  if (engagementRate !== null) {
    parts.push(`Rate ${engagementRate}%`);
  }

  return parts.length > 0 ? parts.join(" | ") : null;
}

function toDisplayNumber(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  if (typeof value === "string" && value.trim() !== "") {
    return value;
  }
  return null;
}

function formatQuotaUsage(provider: QuotaProviderSummary): string {
  const usageValue =
    provider.usage_value ??
    (typeof provider.usage?.[provider.usage_unit] === "number"
      ? provider.usage[provider.usage_unit]
      : null);
  const usageLabel = provider.usage_unit.replace(/_/g, " ");

  if (usageValue === null || usageValue === undefined) {
    return `No ${usageLabel} usage captured yet`;
  }

  const formattedUsage = formatQuotaNumber(usageValue);
  if (provider.monthly_limit !== null && provider.monthly_limit !== undefined) {
    return `${formattedUsage} / ${formatQuotaNumber(provider.monthly_limit)} ${usageLabel}`;
  }

  return `${formattedUsage} ${usageLabel}`;
}

function formatQuotaRemaining(provider: QuotaProviderSummary): string {
  const remainingValue =
    typeof provider.remaining_value === "number"
      ? provider.remaining_value
      : null;
  const remainingLimit =
    typeof provider.remaining_limit === "number"
      ? provider.remaining_limit
      : null;
  const unit = (provider.remaining_unit || provider.usage_unit || "quota").replace(
    /_/g,
    " ",
  );

  if (remainingValue !== null) {
    const prefix = provider.remaining_exact ? "Remaining" : "Tracked remaining";
    if (remainingLimit !== null) {
      return `${prefix}: ${formatQuotaNumber(remainingValue)} / ${formatQuotaNumber(
        remainingLimit,
      )} ${unit} left`;
    }
    return `${prefix}: ${formatQuotaNumber(remainingValue)} ${unit} left`;
  }

  const usage = formatQuotaUsage(provider);
  if (usage.startsWith("No ")) {
    return "No provider quota data yet";
  }
  return `Used: ${usage}`;
}

function formatTrackedUsage(provider: QuotaProviderSummary): string | null {
  const usage = formatQuotaUsage(provider);
  if (usage.startsWith("No ")) {
    return null;
  }
  return `Used: ${usage}`;
}

function formatRequestRemaining(provider: QuotaProviderSummary): string | null {
  if (typeof provider.remaining_requests !== "number") {
    return null;
  }
  const base =
    typeof provider.remaining_requests_limit === "number"
      ? `Requests left: ${formatQuotaNumber(
          provider.remaining_requests,
        )} / ${formatQuotaNumber(provider.remaining_requests_limit)}`
      : `Requests left: ${formatQuotaNumber(provider.remaining_requests)}`;

  if (provider.remaining_requests_reset_after) {
    return `${base} (resets in ${provider.remaining_requests_reset_after})`;
  }
  if (provider.remaining_requests_reset_at) {
    return `${base} (resets at ${provider.remaining_requests_reset_at})`;
  }
  return base;
}

function formatQuotaReset(provider: QuotaProviderSummary): string | null {
  if (provider.remaining_reset_after) {
    return `Quota reset: in ${provider.remaining_reset_after}`;
  }
  if (provider.remaining_reset_at) {
    return `Quota reset: ${provider.remaining_reset_at}`;
  }
  return null;
}

function formatQuotaNumber(value: number): string {
  if (!Number.isFinite(value)) {
    return "0";
  }
  if (Number.isInteger(value)) {
    return value.toLocaleString();
  }
  return value.toFixed(2);
}

function formatCurrency(value: number): string {
  return `$${(Number.isFinite(value) ? value : 0).toFixed(2)}`;
}

function quotaStatusClasses(status: string): string {
  switch (status) {
    case "ok":
      return "bg-emerald-500/15 text-emerald-400";
    case "warning":
      return "bg-amber-500/15 text-amber-400";
    case "critical":
      return "bg-rose-500/15 text-rose-400";
    case "not_configured":
      return "bg-zinc-500/15 text-zinc-400";
    default:
      return "bg-sky-500/15 text-sky-400";
  }
}

function StatCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-[16px] border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500 mb-1">
            {title}
          </p>
          <p className="text-3xl font-semibold text-white">
            {value}
          </p>
        </div>
        <div>{icon}</div>
      </div>
    </div>
  );
}
