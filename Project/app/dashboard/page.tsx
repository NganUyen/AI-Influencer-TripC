"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import apiClient from "@/lib/api-client";
import { WORKFLOW_POLL_INTERVAL } from "@/config/constants";
import { useContentStore } from "@/store/content-store";

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

export default function DashboardPage() {
  const [workflows, setWorkflows] = useState<DashboardWorkflow[]>([]);
  const [stats, setStats] = useState<ContentStats>({
    total_content: 0,
    active_campaigns: 0,
    published: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { items: contentItems, fetchItems } = useContentStore();

  const loadDashboardData = useCallback(async () => {
    try {
      const listResponse = await apiClient.get<{
        workflows: WorkflowListItem[];
      }>("/api/workflows/list", { params: { limit: 10 } });

      const statsResponse =
        await apiClient.get<ContentStats>("/api/content/stats");
      setStats(statsResponse.data);
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

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="container mx-auto p-8">
        <h1 className="text-4xl font-bold mb-8 text-gray-900 dark:text-white">
          Dashboard
        </h1>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Content"
            value={String(stats.total_content)}
            icon="📝"
          />
          <StatCard
            title="Active Campaigns"
            value={String(Math.max(runningCount, stats.active_campaigns))}
            icon="🚀"
          />
          <StatCard title="Engagement Rate" value="N/A" icon="📊" />
          <StatCard title="AI Personas" value="0" icon="👤" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
              Recent Content
            </h2>
            {isLoading && (
              <p className="text-gray-600 dark:text-gray-400">
                Loading workflows...
              </p>
            )}

            {!isLoading && error && (
              <p className="text-red-600 dark:text-red-400">{error}</p>
            )}

            {!isLoading && !error && contentItems.length === 0 && (
              <p className="text-gray-600 dark:text-gray-400">
                No content generated yet. Start your first campaign!
              </p>
            )}

            {!isLoading && !error && contentItems.length > 0 && (
              <div className="space-y-3">
                {contentItems.slice(0, 5).map((item) => {
                  const linkedWorkflow = workflows.find(
                    (workflow) => workflow.workflow_id === item.id,
                  );
                  const status =
                    linkedWorkflow?.details?.status ||
                    linkedWorkflow?.status ||
                    item.status;

                  return (
                    <div
                      key={item.id}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg p-3"
                    >
                      <p className="text-sm font-medium text-gray-900 dark:text-white break-all">
                        {item.title}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Status: {status}
                      </p>
                      {linkedWorkflow?.details?.current_step && (
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          Step: {linkedWorkflow.details.current_step}
                        </p>
                      )}
                      {status === "waiting_approval" && linkedWorkflow && (
                        <div className="flex gap-2 mt-3">
                          <button
                            type="button"
                            onClick={() =>
                              handleApproval(linkedWorkflow.workflow_id, true)
                            }
                            className="px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded-md hover:bg-green-700"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              handleApproval(linkedWorkflow.workflow_id, false)
                            }
                            className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-md hover:bg-red-700"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
              Upcoming Posts
            </h2>
            {completedCount > 0 ? (
              <p className="text-gray-600 dark:text-gray-400">
                {completedCount} workflow(s) completed. Scheduled post details
                will appear when content endpoints are connected.
              </p>
            ) : (
              <p className="text-gray-600 dark:text-gray-400">
                No scheduled posts. Create a content calendar!
              </p>
            )}

            {waitingApproval.length > 0 && (
              <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-3">
                {waitingApproval.length} workflow(s) waiting for approval.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: string;
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
            {title}
          </p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
        </div>
        <div className="text-4xl">{icon}</div>
      </div>
    </div>
  );
}
