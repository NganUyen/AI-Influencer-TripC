"use client";

import React from "react";
import { Download, Edit2, PlayCircle, Send } from "lucide-react";
import {
  getReviewJobActiveTikTokChannels,
  getReviewJobChannelLabel,
  type ReviewEngineJob,
  getReviewJobPreferredTikTokChannelId,
  getReviewJobPersonaImage,
  getReviewJobStatusLabel,
  getReviewJobTone,
} from "@/lib/review-engine";

interface OverviewTabProps {
  campaigns: any[];
  approvals: any[];
  content: any[];
  personas: any[];
  systemSummary: any;
  onTabChange: (tabId: any) => void;
  activityItems: any[];
  quotaWarnings: any[];
  reviewJobs?: ReviewEngineJob[];
  onPublishJob?: (
    job: ReviewEngineJob,
    socialAccountId?: string | null,
  ) => Promise<void> | void;
}

function statusClass(tone: "default" | "success" | "warning") {
  if (tone === "success") return "text-emerald-600";
  if (tone === "warning") return "text-amber-600";
  return "text-aura-primary";
}

function progressBarClass(tone: "default" | "success" | "warning") {
  if (tone === "success") return "from-emerald-500 to-emerald-300";
  if (tone === "warning") return "from-amber-500 to-amber-300";
  return "from-aura-primary to-aura-primary-container";
}

function formatTimeLabel(value?: string | null) {
  if (!value) return "Now";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return value;
  return new Date(parsed).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getWebsiteLabel(url?: string | null) {
  if (!url) return "Unknown";
  try {
    return new URL(url).hostname.replace(/^www\./i, "") || "Unknown";
  } catch {
    return "Unknown";
  }
}

function getJobTimestamp(job: ReviewEngineJob) {
  const value =
    job.published_at ||
    job.updated_at ||
    job.started_at ||
    job.created_at ||
    "";
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDateLabel(value?: string | null) {
  if (!value) return "No date";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return "No date";
  return new Date(parsed).toLocaleDateString([], {
    day: "2-digit",
    month: "short",
  });
}

export function OverviewTab({
  campaigns,
  approvals,
  content,
  personas,
  systemSummary,
  onTabChange,
  activityItems,
  reviewJobs = [],
  onPublishJob,
}: OverviewTabProps) {
  const [websiteFilter, setWebsiteFilter] = React.useState("all");
  const [dateSort, setDateSort] = React.useState<"newest" | "oldest">("newest");
  const [selectedChannelIds, setSelectedChannelIds] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    setSelectedChannelIds((current) => {
      const next: Record<string, string> = {};
      for (const job of reviewJobs) {
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
  }, [reviewJobs]);

  const websiteOptions = React.useMemo(() => {
    const unique = Array.from(
      new Set(reviewJobs.map((job) => getWebsiteLabel(job.source_url))),
    ).filter((label) => label !== "Unknown");
    return unique.sort((left, right) => left.localeCompare(right));
  }, [reviewJobs]);

  const jobCards = React.useMemo(() => {
    const filtered = reviewJobs.filter((job) => {
      if (websiteFilter === "all") return true;
      return getWebsiteLabel(job.source_url) === websiteFilter;
    });

    const sorted = [...filtered].sort((left, right) => {
      const leftTime = getJobTimestamp(left);
      const rightTime = getJobTimestamp(right);
      return dateSort === "newest" ? rightTime - leftTime : leftTime - rightTime;
    });

    return sorted.slice(0, 8);
  }, [dateSort, reviewJobs, websiteFilter]);

  const readyJobs = reviewJobs.filter((job) => job.production?.ready);
  const publishedJobs = reviewJobs.filter(
    (job) => job.publish?.status === "published",
  );

  return (
    <div className="space-y-8 animate-fade-in relative">
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="dashboard-panel p-6">
          <p className="text-[11px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
            Active Review Jobs
          </p>
          <p className="mt-3 text-4xl font-black text-aura-on-surface font-headline">
            {reviewJobs.length}
          </p>
        </div>
        <div className="dashboard-panel p-6">
          <p className="text-[11px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
            Ready To Publish
          </p>
          <p className="mt-3 text-4xl font-black text-aura-on-surface font-headline">
            {readyJobs.length}
          </p>
        </div>
        <div className="dashboard-panel p-6">
          <p className="text-[11px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
            Published
          </p>
          <p className="mt-3 text-4xl font-black text-aura-on-surface font-headline">
            {publishedJobs.length}
          </p>
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
        <div className="xl:col-span-4 flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold tracking-tight text-on-surface font-headline">
              Production Queue
            </h2>
            <span className="dashboard-pill dashboard-pill-muted text-[11px] uppercase tracking-wider">
              Active ({activityItems.length || 0})
            </span>
          </div>

          <div className="space-y-2 max-h-[620px] overflow-auto pr-1">
            {activityItems.length > 0 ? (
              activityItems.slice(0, 6).map((item) => {
                const tone = (item.tone || "default") as
                  | "default"
                  | "success"
                  | "warning";
                return (
                  <article
                    key={item.id}
                    className="dashboard-card flex items-center gap-3 p-3.5"
                  >
                    <div className="relative">
                      <img
                        alt="Persona"
                        className="w-10 h-10 rounded-full object-cover ring-2 ring-background shadow-sm"
                        src={
                          item.personaImage ||
                          "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=128&h=128&auto=format&fit=crop"
                        }
                        width={40}
                        height={40}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-end mb-1.5 gap-2">
                        <p className="text-xs font-bold text-on-surface truncate">
                          {item.title}
                        </p>
                        <span className={`text-[10px] font-bold ${statusClass(tone)}`}>
                          {item.detail?.split("•")[0] || "Active"}
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-surface-container rounded-full overflow-hidden">
                        <div
                          className={`h-full bg-gradient-to-r ${progressBarClass(tone)} transition-all duration-700`}
                          style={{ width: `${item.progress || 0}%` }}
                        />
                      </div>
                    </div>
                    <div className="text-[11px] font-semibold text-on-surface-variant w-14 text-right">
                      {formatTimeLabel(item.timeLabel)}
                    </div>
                  </article>
                );
              })
            ) : (
              <div className="dashboard-panel-soft flex flex-col items-center justify-center border-2 border-dashed border-surface-container py-12 text-on-surface-variant/40">
                <p className="text-sm font-medium text-center">
                  No active production tasks
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="xl:col-span-8 flex flex-col gap-6">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-on-surface font-headline">
                Final Products
              </h2>
              <p className="text-sm text-aura-on-surface-variant mt-1">
                URL, persona, editable content, current status, and publishing state.
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <label className="text-xs font-semibold text-aura-on-surface-variant">
                Website
              </label>
              <select
                className="dashboard-input h-9 min-w-[150px] text-xs"
                value={websiteFilter}
                onChange={(event) => setWebsiteFilter(event.target.value)}
                aria-label="Filter videos by website"
              >
                <option value="all">All sites</option>
                {websiteOptions.map((website) => (
                  <option key={website} value={website}>
                    {website}
                  </option>
                ))}
              </select>

              <label className="text-xs font-semibold text-aura-on-surface-variant">
                Date
              </label>
              <select
                className="dashboard-input h-9 min-w-[132px] text-xs"
                value={dateSort}
                onChange={(event) =>
                  setDateSort(event.target.value === "oldest" ? "oldest" : "newest")
                }
                aria-label="Sort videos by date"
              >
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
              </select>

              <button
                type="button"
                onClick={() => onTabChange("create_video")}
                className="btn-primary btn-sm"
              >
                Create New Review
              </button>
            </div>
          </div>

          {jobCards.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {jobCards.map((job) => {
                const tone = getReviewJobTone(job);
                const statusLabel = getReviewJobStatusLabel(job);
                const personaImage =
                  getReviewJobPersonaImage(job) ||
                  "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop";
                const activeChannels = getReviewJobActiveTikTokChannels(job);
                const selectedChannelId =
                  selectedChannelIds[job.job_id] ??
                  getReviewJobPreferredTikTokChannelId(job);
                const needsExplicitChannelSelection = activeChannels.length > 1;
                const selectedChannel = activeChannels.find(
                  (channel) => channel.id === selectedChannelId,
                );

                return (
                  <article
                    key={job.job_id}
                    className="dashboard-panel overflow-hidden p-0 flex flex-col h-full"
                  >
                    <div className="relative aspect-[4/3] overflow-hidden bg-black">
                      {job.production?.playable_video_url ? (
                        <video
                          className="w-full h-full object-cover"
                          src={job.production.playable_video_url}
                          muted
                          playsInline
                          controls
                        />
                      ) : (
                        <img
                          alt={job.persona?.display_name || "Persona"}
                          className="w-full h-full object-cover"
                          src={personaImage}
                        />
                      )}
                      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-5">
                        <div className="flex items-center gap-3">
                          <img
                            alt={job.persona?.display_name || "Persona"}
                            className="w-9 h-9 rounded-full object-cover ring-2 ring-white/20"
                            src={personaImage}
                            width={36}
                            height={36}
                          />
                          <div className="min-w-0">
                            <p className="text-white font-semibold text-sm truncate">
                              {job.persona?.display_name || "Persona"}
                            </p>
                            <p className="text-white/70 text-xs uppercase tracking-widest">
                              {job.persona?.region_label || job.persona?.language || "Global"}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="p-3.5 space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-black text-aura-on-surface font-headline line-clamp-2">
                            {job.content?.title || job.page_title || "App Review"}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-aura-on-surface-variant">
                            <span className="dashboard-pill dashboard-pill-muted px-2 py-0.5 normal-case tracking-normal">
                              {getWebsiteLabel(job.source_url)}
                            </span>
                            <span>{formatDateLabel(job.updated_at || job.created_at || job.published_at)}</span>
                          </div>
                        </div>
                        <span className={`text-[10px] font-bold uppercase tracking-widest ${statusClass(tone)}`}>
                          {statusLabel}
                        </span>
                      </div>

                      <div className="space-y-2">
                        <div className="w-full h-2 rounded-full bg-aura-surface-container overflow-hidden">
                          <div
                            className={`h-full bg-gradient-to-r ${progressBarClass(tone)}`}
                            style={{ width: `${job.progress || 0}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-xs text-aura-on-surface-variant">
                          <span>{job.progress || 0}% complete</span>
                          <span>
                            {job.publish?.status === "published"
                              ? "Published"
                              : job.production?.ready
                                ? "Ready"
                                : "In production"}
                          </span>
                        </div>
                      </div>

                      <div className="rounded-xl bg-aura-surface-container-low p-3">
                        <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold mb-2">
                          Content
                        </p>
                        <p className="text-xs text-aura-on-surface line-clamp-3">
                          {job.content?.body || job.script?.script || "No content available yet."}
                        </p>
                      </div>

                      <div className="flex flex-col gap-2">
                        {activeChannels.length > 0 &&
                          (needsExplicitChannelSelection ? (
                            <select
                              className="dashboard-input h-8 min-w-[180px] text-xs"
                              value={selectedChannelId || ""}
                              onChange={(event) =>
                                setSelectedChannelIds((current) => {
                                  if (!event.target.value) {
                                    const next = { ...current };
                                    delete next[job.job_id];
                                    return next;
                                  }
                                  return {
                                    ...current,
                                    [job.job_id]: event.target.value,
                                  };
                                })
                              }
                              aria-label={`Select TikTok channel for ${job.content?.title || job.page_title || job.job_id}`}
                            >
                              <option value="">Select TikTok channel</option>
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
                            <span className="dashboard-pill dashboard-pill-muted w-fit px-2 py-1 text-[10px] normal-case tracking-normal">
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

                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => onTabChange("create_video")}
                            className="btn-secondary btn-sm h-8 px-3 text-xs flex items-center gap-1.5"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                            Edit Content
                          </button>

                          {job.production?.download_url ? (
                            <a
                              href={job.production.download_url}
                              target="_blank"
                              rel="noreferrer"
                              className="btn-secondary btn-sm h-8 px-3 text-xs flex items-center gap-1.5"
                            >
                              <Download className="w-3.5 h-3.5" />
                              Download
                            </a>
                          ) : (
                            <button
                              type="button"
                              disabled
                              className="btn-secondary btn-sm h-8 px-3 text-xs opacity-50 cursor-not-allowed flex items-center gap-1.5"
                            >
                              <PlayCircle className="w-3.5 h-3.5" />
                              Pending
                            </button>
                          )}

                          <button
                            type="button"
                            disabled={
                              !job.production?.ready ||
                              job.publish?.status === "published" ||
                              !onPublishJob ||
                              (needsExplicitChannelSelection && !selectedChannelId)
                            }
                            onClick={() => onPublishJob?.(job, selectedChannelId)}
                            className="btn-primary btn-sm h-8 px-3 text-xs flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <Send className="w-3.5 h-3.5" />
                            {job.publish?.status === "published"
                              ? "Published"
                              : "Publish"}
                          </button>
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : reviewJobs.length > 0 ? (
            <div className="dashboard-panel-soft flex flex-col items-center justify-center border-2 border-dashed border-surface-container py-14 text-on-surface-variant/70">
              <p className="text-base font-bold">No videos match current filters</p>
              <p className="text-sm mt-1">Try another website or date sort.</p>
              <button
                type="button"
                onClick={() => {
                  setWebsiteFilter("all");
                  setDateSort("newest");
                }}
                className="btn-secondary btn-sm mt-4"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="dashboard-panel-soft flex flex-col items-center justify-center border-2 border-dashed border-surface-container py-20 text-on-surface-variant/40">
              <p className="text-lg font-bold">No review videos yet</p>
              <p className="text-sm">Create your first app review in the Create Video tab.</p>
            </div>
          )}
        </div>
      </section>

      <div className="dashboard-panel-soft relative mt-8 w-full overflow-hidden border border-surface-container">
        <div className="p-5 border-b border-surface-container flex items-center justify-between bg-surface-container-low/50">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-tertiary rounded-full animate-pulse" />
            <h3 className="font-bold text-sm tracking-tight text-on-surface">
              System Health
            </h3>
          </div>
          <span className="text-[10px] font-black text-on-surface-variant opacity-60">
            {(systemSummary?.services?.length || 0) + personas.length + campaigns.length} ACTIVE SIGNALS
          </span>
        </div>

        <ul className="p-4 space-y-3">
          {(systemSummary?.services || []).length > 0 ? (
            (systemSummary?.services || []).slice(0, 6).map((service: any, idx: number) => (
              <li key={service.name || idx} className="flex items-center justify-between rounded-lg p-2 bg-transparent">
                <span className="text-xs font-bold text-on-surface">
                  {service.name}
                </span>
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant">
                  {service.status}
                </span>
              </li>
            ))
          ) : (
            <li className="text-sm text-on-surface-variant">
              No external service alerts.
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
