"use client";

import React from "react";
import { toast } from "react-hot-toast";
import {
  Send,
  Clock,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Share2,
  Calendar,
  Globe,
  Filter,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { customerApiRequest } from "@/lib/customer-api";
import {
  getReviewJobActiveTikTokChannels,
  getReviewJobChannelLabel,
  getReviewJobPreferredTikTokChannelId,
  type ReviewEngineJob,
} from "@/lib/review-engine";

interface PublishingTabProps {
  jobs?: ReviewEngineJob[];
  onRefresh?: () => Promise<void> | void;
}

export function PublishingTab({ jobs, onRefresh }: PublishingTabProps) {
  const [searchTerm, setSearchTerm] = React.useState("");
  const [detailJob, setDetailJob] = React.useState<ReviewEngineJob | null>(null);
  const [shareJob, setShareJob] = React.useState<ReviewEngineJob | null>(null);
  const [publishingJobId, setPublishingJobId] = React.useState<string | null>(null);
  const [selectedChannelIds, setSelectedChannelIds] = React.useState<Record<string, string>>({});
  const safeJobs = Array.isArray(jobs) ? jobs : [];
  const [liveJobs, setLiveJobs] = React.useState<ReviewEngineJob[]>(safeJobs);

  React.useEffect(() => {
    setLiveJobs(safeJobs);
  }, [safeJobs]);

  React.useEffect(() => {
    setSelectedChannelIds((current) => {
      const next: Record<string, string> = {};
      for (const job of liveJobs) {
        const activeChannels = getReviewJobActiveTikTokChannels(job);
        const currentSelection = current[job.job_id];
        if (
          currentSelection &&
          activeChannels.some((channel) => channel.id === currentSelection)
        ) {
          next[job.job_id] = currentSelection;
          continue;
        }
        const preferred = getReviewJobPreferredTikTokChannelId(job);
        if (preferred) {
          next[job.job_id] = preferred;
        }
      }
      const currentKeys = Object.keys(current);
      const nextKeys = Object.keys(next);
      if (
        currentKeys.length === nextKeys.length &&
        nextKeys.every((key) => current[key] === next[key])
      ) {
        return current;
      }
      return next;
    });
  }, [liveJobs]);

  const publishingJobs = liveJobs.filter(
    (j) =>
      j.publish?.requested ||
      j.publish?.status === "published" ||
      j.publish?.status === "failed" ||
      j.publish?.status === "scheduled" ||
      j.publish?.status === "auth_required" ||
      j.publish?.status === "ready_to_publish",
  );

  const updateJob = React.useCallback(
    (jobId: string, updater: (job: ReviewEngineJob) => ReviewEngineJob) => {
      setLiveJobs((current) =>
        current.map((job) => (job.job_id === jobId ? updater(job) : job)),
      );
    },
    [],
  );

  const handlePublishNow = async (jobId: string, socialAccountId?: string | null) => {
    setPublishingJobId(jobId);
    try {
      const updated = await customerApiRequest<ReviewEngineJob>(
        `/api/customer/review-engine/jobs/${jobId}/publish`,
        {
          method: "POST",
          body: JSON.stringify(
            socialAccountId ? { social_account_id: socialAccountId } : {},
          ),
        },
      );
      updateJob(jobId, () => updated);
      await Promise.resolve(onRefresh?.());
      toast.success("Publish request sent.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to publish job";
      toast.error(message);
    } finally {
      setPublishingJobId(null);
    }
  };

  const handleCopyShare = async (job: ReviewEngineJob) => {
    const text =
      job.publish?.post_url || job.production?.playable_video_url || "No share link";
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      }
      toast.success("Share link copied.");
    } catch {
      toast.success(`Share link: ${text}`);
    }
  };

  const filteredContent = publishingJobs.filter(
    (item) =>
      (item.content?.title || item.page_title || "App Review")
        .toLowerCase()
        .includes(searchTerm.toLowerCase()) ||
      (item.target_platform || "tiktok").toLowerCase().includes(searchTerm.toLowerCase()),
  );

  const getStatusIcon = (status?: string | null) => {
    switch (status?.toLowerCase()) {
      case "published":
        return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
      case "scheduled":
      case "ready_to_publish":
        return <Clock className="w-4 h-4 text-aura-primary" />;
      case "failed":
      case "auth_required":
        return <AlertCircle className="w-4 h-4 text-rose-500" />;
      default:
        return <Send className="w-4 h-4 text-aura-on-surface-variant" />;
    }
  };

  const getStatusColor = (status?: string | null) => {
    switch (status?.toLowerCase()) {
      case "published":
        return "bg-emerald-50 text-emerald-700 border-emerald-100";
      case "scheduled":
      case "ready_to_publish":
        return "bg-aura-primary/10 text-aura-primary border-aura-primary/10";
      case "failed":
      case "auth_required":
        return "bg-rose-50 text-rose-700 border-rose-100";
      default:
        return "bg-aura-surface-container text-aura-on-surface-variant border-aura-outline/10";
    }
  };

  return (
    <div className="space-y-10 animate-fade-in pb-20">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-4xl font-extrabold text-aura-on-surface font-headline tracking-tight">
            Post Publishing
          </h1>
          <p className="text-aura-on-surface-variant max-w-2xl text-lg font-body">
            Manage your global content distribution. Monitor scheduled posts, track
            published performance, and resolve delivery issues across all platforms.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-aura-on-surface-variant group-focus-within:text-aura-primary transition-colors" />
            <input
              type="text"
              placeholder="Search content..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-11 pr-6 py-3 bg-white border border-aura-outline-variant/15 rounded-full text-sm font-medium text-aura-on-surface shadow-aura-sm focus:ring-2 focus:ring-aura-primary/10 transition-all outline-none w-64"
            />
          </div>
          <button className="p-3 bg-white border border-aura-outline-variant/15 rounded-full shadow-aura-sm hover:bg-aura-surface-container transition-colors">
            <Filter className="w-4 h-4 text-aura-on-surface-variant" />
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="dashboard-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 flex items-center justify-center text-emerald-500">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-bold text-aura-on-surface-variant uppercase tracking-widest font-label">
              Published
            </p>
            <p className="text-3xl font-black text-aura-on-surface font-headline">
              {publishingJobs.filter((c) => c.publish?.status === "published").length}
            </p>
          </div>
        </div>
        <div className="dashboard-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-2xl bg-aura-primary/10 flex items-center justify-center text-aura-primary">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-bold text-aura-on-surface-variant uppercase tracking-widest font-label">
              Scheduled
            </p>
            <p className="text-3xl font-black text-aura-on-surface font-headline">
              {
                publishingJobs.filter(
                  (c) =>
                    c.publish?.status === "scheduled" ||
                    c.publish?.status === "ready_to_publish",
                ).length
              }
            </p>
          </div>
        </div>
        <div className="dashboard-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-2xl bg-rose-50 flex items-center justify-center text-rose-500">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-bold text-aura-on-surface-variant uppercase tracking-widest font-label">
              Failed / Auth
            </p>
            <p className="text-3xl font-black text-aura-on-surface font-headline">
              {
                publishingJobs.filter(
                  (c) =>
                    c.publish?.status === "failed" ||
                    c.publish?.status === "auth_required",
                ).length
              }
            </p>
          </div>
        </div>
      </div>

      <div className="dashboard-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-aura-outline-variant/10">
                <th className="px-8 py-5 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">
                  Content Title
                </th>
                <th className="px-8 py-5 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">
                  Platforms
                </th>
                <th className="px-8 py-5 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">
                  Status
                </th>
                <th className="px-8 py-5 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">
                  Timing
                </th>
                <th className="px-8 py-5 text-right text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-aura-outline-variant/5">
              {filteredContent.length > 0 ? (
                filteredContent.map((item) => {
                  const activeChannels = getReviewJobActiveTikTokChannels(item);
                  const selectedChannelId =
                    selectedChannelIds[item.job_id] ??
                    getReviewJobPreferredTikTokChannelId(item);
                  const needsExplicitChannelSelection = activeChannels.length > 1;
                  const selectedChannel = activeChannels.find(
                    (channel) => channel.id === selectedChannelId,
                  );
                  const publishDisabled =
                    publishingJobId === item.job_id ||
                    (needsExplicitChannelSelection && !selectedChannelId);

                  return (
                    <tr
                      key={item.job_id}
                      className="group hover:bg-aura-surface-container-lowest transition-colors"
                    >
                      <td className="px-8 py-6">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-lg bg-aura-surface-container flex items-center justify-center shrink-0 border border-aura-outline-variant/10">
                            <Globe className="w-5 h-5 text-aura-on-surface-variant" />
                          </div>
                          <span
                            className="font-bold text-aura-on-surface font-headline truncate max-w-[200px]"
                            title={item.content?.title || item.page_title || "App Review"}
                          >
                            {item.content?.title || item.page_title || "App Review"}
                          </span>
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <div className="flex gap-1.5 flex-wrap">
                          {[(item.target_platform || "tiktok")].map((p) => (
                            <span
                              key={p}
                              className="px-2.5 py-1 bg-aura-surface-container rounded-full text-[10px] font-bold text-aura-on-surface-variant uppercase tracking-widest border border-aura-outline/5"
                            >
                              {p}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-8 py-6 text-sm">
                        <div
                          className={cn(
                            "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest border transition-all",
                            getStatusColor(item.publish?.status),
                          )}
                        >
                          {getStatusIcon(item.publish?.status)}
                          {(item.publish?.status || "Draft").replace(/_/g, " ")}
                        </div>
                      </td>
                      <td className="px-8 py-6">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2 text-xs font-semibold text-aura-on-surface">
                            <Calendar className="w-3 h-3 text-aura-primary/60" />
                            {item.published_at
                              ? new Date(item.published_at).toLocaleDateString()
                              : item.scheduled_at
                                ? new Date(item.scheduled_at).toLocaleDateString()
                                : "Pending"}
                          </div>
                          <div className="text-[10px] text-aura-on-surface-variant font-medium font-body opacity-60">
                            {item.published_at
                              ? new Date(item.published_at).toLocaleTimeString()
                              : item.scheduled_at
                                ? new Date(item.scheduled_at).toLocaleTimeString()
                                : "Pending"}
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6 text-right">
                        <div className="flex flex-col items-end gap-2">
                          {activeChannels.length > 0 &&
                            (needsExplicitChannelSelection ? (
                              <select
                                className="min-h-[36px] min-w-[190px] rounded-full border border-aura-outline-variant/15 bg-white px-3 text-xs font-medium text-aura-on-surface shadow-aura-sm outline-none"
                                value={selectedChannelId || ""}
                                onChange={(event) =>
                                  setSelectedChannelIds((current) => {
                                    if (!event.target.value) {
                                      const next = { ...current };
                                      delete next[item.job_id];
                                      return next;
                                    }
                                    return {
                                      ...current,
                                      [item.job_id]: event.target.value,
                                    };
                                  })
                                }
                                aria-label={`Select TikTok channel for ${item.content?.title || item.page_title || item.job_id}`}
                              >
                                <option value="">Select channel</option>
                                {activeChannels.map((channel) => (
                                  <option
                                    key={channel.id || channel.handle || "channel"}
                                    value={channel.id || ""}
                                  >
                                    {getReviewJobChannelLabel(channel)}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <span className="rounded-full border border-aura-outline/10 bg-aura-surface-container px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-aura-on-surface-variant">
                                {getReviewJobChannelLabel(activeChannels[0])}
                              </span>
                            ))}

                          {selectedChannel && (
                            <span className="text-[10px] font-medium text-aura-on-surface-variant">
                              Target: {getReviewJobChannelLabel(selectedChannel)}
                            </span>
                          )}

                          {needsExplicitChannelSelection && !selectedChannelId && (
                            <span className="text-[10px] font-medium text-rose-500">
                              Choose a TikTok channel first
                            </span>
                          )}

                          <div className="flex items-center justify-end gap-2 flex-wrap">
                            {(item.publish?.status === "scheduled" ||
                              item.publish?.status === "ready_to_publish" ||
                              item.publish?.status === "failed" ||
                              item.publish?.status === "auth_required") && (
                              <button
                                className="px-3 py-1.5 text-xs font-semibold rounded-full border border-aura-primary/30 text-aura-primary hover:bg-aura-primary/10 transition-all disabled:opacity-60"
                                onClick={() => {
                                  void handlePublishNow(item.job_id, selectedChannelId);
                                }}
                                disabled={publishDisabled}
                              >
                                {publishingJobId === item.job_id ? "Publishing..." : "Publish"}
                              </button>
                            )}

                            <button
                              className="p-2 hover:bg-aura-primary/10 hover:text-aura-primary rounded-lg transition-all"
                              title="View details"
                              onClick={() => setDetailJob(item)}
                            >
                              <ExternalLink className="w-4 h-4" />
                            </button>
                            <button
                              className="p-2 hover:bg-aura-primary/10 hover:text-aura-primary rounded-lg transition-all"
                              title="Share"
                              onClick={() => setShareJob(item)}
                            >
                              <Share2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} className="px-8 py-20 text-center">
                    <div className="flex flex-col items-center gap-4">
                      <div className="w-16 h-16 rounded-full bg-aura-surface-container flex items-center justify-center">
                        <Search className="w-8 h-8 text-aura-on-surface-variant/20" />
                      </div>
                      <div className="space-y-1">
                        <p className="text-aura-on-surface font-bold font-headline">
                          No content found
                        </p>
                        <p className="text-aura-on-surface-variant text-sm font-body">
                          Try adjusting your search or filters.
                        </p>
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {detailJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4">
          <div className="w-full max-w-2xl rounded-3xl bg-white shadow-xl border border-aura-outline-variant/15 overflow-hidden">
            <div className="px-6 py-4 border-b border-aura-outline-variant/10 flex items-center justify-between">
              <h3 className="text-xl font-bold text-aura-on-surface">
                Publishing Details
              </h3>
              <button
                className="text-sm font-semibold text-aura-on-surface-variant hover:text-aura-on-surface"
                onClick={() => setDetailJob(null)}
              >
                Close
              </button>
            </div>
            <div className="p-6 space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <DetailItem label="Job ID" value={detailJob.job_id} />
                <DetailItem label="Workflow ID" value={detailJob.workflow_id || "-"} />
                <DetailItem
                  label="Title"
                  value={detailJob.content?.title || detailJob.page_title || "App Review"}
                />
                <DetailItem label="Platform" value={detailJob.target_platform || "tiktok"} />
                <DetailItem label="Status" value={detailJob.publish?.status || "draft"} />
                <DetailItem label="Persona" value={detailJob.persona?.display_name || "-"} />
              </div>

              <div className="rounded-2xl bg-aura-surface-container p-4 border border-aura-outline-variant/10">
                <p className="text-xs uppercase tracking-wider font-bold text-aura-on-surface-variant mb-2">
                  Activity Feed
                </p>
                <ul className="space-y-1 text-aura-on-surface">
                  {(detailJob.activity_feed || []).length > 0 ? (
                    (detailJob.activity_feed || []).slice(-5).map((step, idx) => (
                      <li key={`${detailJob.job_id}-step-${idx}`}>• {step.label}</li>
                    ))
                  ) : (
                    <li>• No activity feed available.</li>
                  )}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {shareJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4">
          <div className="w-full max-w-xl rounded-3xl bg-white shadow-xl border border-aura-outline-variant/15 overflow-hidden">
            <div className="px-6 py-4 border-b border-aura-outline-variant/10 flex items-center justify-between">
              <h3 className="text-xl font-bold text-aura-on-surface">Share Link</h3>
              <button
                className="text-sm font-semibold text-aura-on-surface-variant hover:text-aura-on-surface"
                onClick={() => setShareJob(null)}
              >
                Close
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-sm text-aura-on-surface-variant">
                Share this generated publish or preview link.
              </p>
              <div className="rounded-xl border border-aura-outline-variant/15 bg-aura-surface-container p-3 break-all text-sm text-aura-on-surface">
                {shareJob.publish?.post_url ||
                  shareJob.production?.playable_video_url ||
                  "No link available"}
              </div>
              <div className="flex justify-end gap-2">
                <button
                  className="px-4 py-2 rounded-xl border border-aura-outline-variant/20 text-aura-on-surface-variant"
                  onClick={() => setShareJob(null)}
                >
                  Cancel
                </button>
                <button
                  className="px-4 py-2 rounded-xl bg-aura-primary text-white font-semibold"
                  onClick={() => {
                    void handleCopyShare(shareJob);
                  }}
                >
                  Copy Link
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-aura-outline-variant/10 p-3 bg-aura-surface-container-lowest">
      <p className="text-[10px] font-bold uppercase tracking-wider text-aura-on-surface-variant mb-1">
        {label}
      </p>
      <p className="text-sm font-semibold text-aura-on-surface break-all">{value}</p>
    </div>
  );
}
