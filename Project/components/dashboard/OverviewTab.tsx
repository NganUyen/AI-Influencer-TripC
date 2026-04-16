"use client";

import React from "react";
import { Download, Edit2, PlayCircle, Send } from "lucide-react";
import {
  type ReviewEngineJob,
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
  onPublishJob?: (jobId: string) => Promise<void> | void;
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
  const jobCards = reviewJobs.slice(0, 6);
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

          <div className="space-y-4">
            {activityItems.length > 0 ? (
              activityItems.slice(0, 6).map((item) => {
                const tone = (item.tone || "default") as
                  | "default"
                  | "success"
                  | "warning";
                return (
                  <article
                    key={item.id}
                    className="dashboard-card flex items-center gap-4 p-5"
                  >
                    <div className="relative">
                      <img
                        alt="Persona"
                        className="w-12 h-12 rounded-full object-cover ring-2 ring-background shadow-md"
                        src={
                          item.personaImage ||
                          "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=128&h=128&auto=format&fit=crop"
                        }
                        width={48}
                        height={48}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-end mb-2 gap-3">
                        <p className="text-sm font-bold text-on-surface truncate">
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
                    <div className="text-xs font-semibold text-on-surface-variant w-16 text-right">
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
            <button
              type="button"
              onClick={() => onTabChange("create_video")}
              className="btn-primary btn-sm"
            >
              Create New Review
            </button>
          </div>

          {jobCards.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {jobCards.map((job) => {
                const tone = getReviewJobTone(job);
                const statusLabel = getReviewJobStatusLabel(job);
                const personaImage =
                  getReviewJobPersonaImage(job) ||
                  "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop";
                return (
                  <article
                    key={job.job_id}
                    className="dashboard-panel overflow-hidden p-0 flex flex-col"
                  >
                    <div className="relative aspect-[4/5] overflow-hidden bg-black">
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
                            className="w-12 h-12 rounded-full object-cover ring-2 ring-white/20"
                            src={personaImage}
                            width={48}
                            height={48}
                          />
                          <div className="min-w-0">
                            <p className="text-white font-bold truncate">
                              {job.persona?.display_name || "Persona"}
                            </p>
                            <p className="text-white/70 text-xs uppercase tracking-widest">
                              {job.persona?.region_label || job.persona?.language || "Global"}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="p-5 space-y-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="text-lg font-black text-aura-on-surface font-headline line-clamp-2">
                            {job.content?.title || job.page_title || "App Review"}
                          </p>
                          <p className="text-xs text-aura-on-surface-variant mt-1">
                            {job.source_url || "No source URL"}
                          </p>
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

                      <div className="rounded-2xl bg-aura-surface-container-low p-4">
                        <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold mb-2">
                          Content
                        </p>
                        <p className="text-sm text-aura-on-surface line-clamp-3">
                          {job.content?.body || job.script?.script || "No content available yet."}
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={() => onTabChange("create_video")}
                          className="btn-secondary btn-sm flex items-center gap-2"
                        >
                          <Edit2 className="w-4 h-4" />
                          Edit Content
                        </button>
                        {job.production?.download_url ? (
                          <a
                            href={job.production.download_url}
                            target="_blank"
                            rel="noreferrer"
                            className="btn-secondary btn-sm flex items-center gap-2"
                          >
                            <Download className="w-4 h-4" />
                            Download
                          </a>
                        ) : (
                          <button
                            type="button"
                            disabled
                            className="btn-secondary btn-sm opacity-50 cursor-not-allowed flex items-center gap-2"
                          >
                            <PlayCircle className="w-4 h-4" />
                            Pending
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={
                            !job.production?.ready ||
                            job.publish?.status === "published" ||
                            !onPublishJob
                          }
                          onClick={() => onPublishJob?.(job.job_id)}
                          className="btn-primary btn-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <Send className="w-4 h-4" />
                          {job.publish?.status === "published"
                            ? "Published"
                            : "Publish"}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
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
