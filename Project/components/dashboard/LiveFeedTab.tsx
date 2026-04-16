"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Download,
  ExternalLink,
  Link as LinkIcon,
  Loader2,
  Send,
  Upload,
  Wand2,
} from "lucide-react";
import { customerApiRequest } from "@/lib/customer-api";
import { cn } from "@/lib/utils";
import {
  type ReviewEngineJob,
  type ReviewEnginePersonaOption,
  type ReviewEngineSetup,
  getReviewJobPersonaImage,
  getReviewJobStatusLabel,
  getReviewJobTone,
} from "@/lib/review-engine";

interface LiveFeedTabProps {
  activityItems: any[];
  systemWorkflows: any[];
  content: any[];
  personas: any[];
  setup: ReviewEngineSetup | null;
  jobs: ReviewEngineJob[];
  initialSourceUrl?: string;
  initialPersonaIds?: string[];
  onRefresh?: () => Promise<void> | void;
  onNavigateToPersonas?: () => void;
  onNavigateToPublishing?: () => void;
}

type InputMode = "ai_autonomous" | "user_upload";

function statusPillClass(status?: string | null) {
  if (status === "published") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (status === "failed") return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-aura-surface-container text-aura-on-surface-variant border-aura-outline-variant/20";
}

function progressBarClass(job: ReviewEngineJob) {
  const tone = getReviewJobTone(job);
  if (tone === "success") return "from-emerald-500 to-emerald-300";
  if (tone === "warning") return "from-amber-500 to-amber-300";
  return "from-aura-primary to-aura-primary-container";
}

function buildPersonaFallback(persona: any): ReviewEnginePersonaOption {
  return {
    persona_id: persona.persona_id,
    display_name: persona.display_name,
    language: persona.language,
    region_label: persona.region_label,
    description: persona.description,
    selection_image_url:
      persona.selection_image_url || persona.avatar_image_url || null,
    image_url: persona.selection_image_url || persona.avatar_image_url || null,
    is_preset: Boolean(persona.is_preset_catalog),
    is_preset_catalog: Boolean(persona.is_preset_catalog),
  };
}

export function LiveFeedTab({
  personas,
  setup,
  jobs,
  initialSourceUrl = "",
  initialPersonaIds = [],
  onRefresh,
  onNavigateToPersonas,
  onNavigateToPublishing,
}: LiveFeedTabProps) {
  const [sourceUrl, setSourceUrl] = useState(initialSourceUrl);
  const [objective, setObjective] = useState("Create an English app review ready for TikTok.");
  const [inputMode, setInputMode] = useState<InputMode>("ai_autonomous");
  const [publishToTiktok, setPublishToTiktok] = useState(false);
  const [selectedPersonas, setSelectedPersonas] = useState<string[]>([]);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [publishingJobId, setPublishingJobId] = useState<string | null>(null);
  const [savingJobId, setSavingJobId] = useState<string | null>(null);
  const [uploadingJobId, setUploadingJobId] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const personaOptions = useMemo(() => {
    const map = new Map<string, ReviewEnginePersonaOption>();
    (setup?.persona_options || []).forEach((persona) => {
      map.set(persona.persona_id, persona);
    });
    (setup?.custom_personas || []).forEach((persona) => {
      map.set(persona.persona_id, persona);
    });
    (personas || []).forEach((persona) => {
      if (!map.has(persona.persona_id)) {
        map.set(persona.persona_id, buildPersonaFallback(persona));
      }
    });
    return Array.from(map.values());
  }, [personas, setup]);

  useEffect(() => {
    if (!sourceUrl && initialSourceUrl) {
      setSourceUrl(initialSourceUrl);
    }
  }, [initialSourceUrl, sourceUrl]);

  useEffect(() => {
    setSelectedPersonas((current) => {
      if (current.length > 0) return current;
      if (initialPersonaIds.length > 0) return initialPersonaIds;
      return personaOptions.slice(0, 8).map((persona) => persona.persona_id);
    });
  }, [initialPersonaIds, personaOptions]);

  useEffect(() => {
    setDrafts((current) => {
      const next = { ...current };
      jobs.forEach((job) => {
        if (!(job.job_id in next)) {
          next[job.job_id] = job.content?.body || job.script?.script || "";
        }
      });
      return next;
    });
  }, [jobs]);

  const handleTogglePersona = (personaId: string) => {
    setSelectedPersonas((current) =>
      current.includes(personaId)
        ? current.filter((id) => id !== personaId)
        : [...current, personaId],
    );
  };

  const handleValidate = async () => {
    if (!sourceUrl.trim()) return;
    setPageError(null);
    setIsValidating(true);
    try {
      const payload = await customerApiRequest<any>(
        "/api/customer/review-engine/source/validate",
        {
          method: "POST",
          body: JSON.stringify({ source_url: sourceUrl.trim() }),
        },
      );
      setValidationResult(payload);
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Failed to validate source URL",
      );
    } finally {
      setIsValidating(false);
    }
  };

  const handleGenerate = async () => {
    if (!sourceUrl.trim()) {
      setPageError("Enter an app URL first.");
      return;
    }
    if (selectedPersonas.length === 0) {
      setPageError("Select at least one persona.");
      return;
    }

    setPageError(null);
    setIsGenerating(true);
    try {
      await customerApiRequest("/api/customer/review-engine/jobs", {
        method: "POST",
        body: JSON.stringify({
          source_url: sourceUrl.trim(),
          objective: objective.trim(),
          target_personas: selectedPersonas,
          input_mode: inputMode,
          publish_to_tiktok: publishToTiktok,
        }),
      });
      await onRefresh?.();
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Failed to create review jobs",
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveJob = async (job: ReviewEngineJob) => {
    setPageError(null);
    setSavingJobId(job.job_id);
    try {
      await customerApiRequest(`/api/customer/review-engine/jobs/${job.job_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: job.content?.title || job.page_title || "App Review",
          content: drafts[job.job_id] || "",
        }),
      });
      await onRefresh?.();
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Failed to update content",
      );
    } finally {
      setSavingJobId(null);
    }
  };

  const handlePublishJob = async (jobId: string) => {
    setPageError(null);
    setPublishingJobId(jobId);
    try {
      await customerApiRequest(`/api/customer/review-engine/jobs/${jobId}/publish`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      await onRefresh?.();
      onNavigateToPublishing?.();
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Failed to publish review",
      );
    } finally {
      setPublishingJobId(null);
    }
  };

  const handleUploadVideo = async (jobId: string, file: File | null) => {
    if (!file) return;
    setPageError(null);
    setUploadingJobId(jobId);
    try {
      await customerApiRequest(`/api/customer/review-engine/jobs/${jobId}/upload`, {
        method: "POST",
        headers: {
          "Content-Type": file.type || "video/mp4",
          "x-filename": file.name,
        },
        body: file,
      });
      await onRefresh?.();
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Failed to upload video",
      );
    } finally {
      setUploadingJobId(null);
    }
  };

  const requirements = setup?.publishing_requirements;

  return (
    <div className="space-y-8 animate-fade-in">
      <header className="space-y-3">
        <h1 className="text-4xl font-extrabold tracking-tight text-aura-on-surface font-headline">
          App Review Studio
        </h1>
        <p className="max-w-3xl text-aura-on-surface-variant text-base leading-relaxed">
          Enter one URL, choose ready personas, generate English-first review content,
          then download or publish directly to TikTok when Telegram and TikTok auth are active.
        </p>
      </header>

      {pageError && (
        <div className="dashboard-banner dashboard-banner-error text-sm font-semibold">
          {pageError}
        </div>
      )}

      <section className="grid grid-cols-1 xl:grid-cols-12 gap-8">
        <div className="xl:col-span-7 dashboard-panel p-8 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4 items-end">
            <div className="space-y-2">
              <label className="text-[11px] font-black uppercase tracking-widest text-aura-on-surface-variant">
                App URL
              </label>
              <div className="flex items-center gap-3 rounded-full bg-aura-surface-container px-5 py-4">
                <LinkIcon className="w-5 h-5 text-aura-primary" />
                <input
                  type="url"
                  value={sourceUrl}
                  onChange={(event) => setSourceUrl(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      void handleGenerate();
                    }
                  }}
                  placeholder="Paste App Store, Play Store, or website URL"
                  className="w-full bg-transparent outline-none text-sm font-medium text-aura-on-surface"
                />
              </div>
            </div>
            <button
              type="button"
              onClick={handleValidate}
              disabled={isValidating || !sourceUrl.trim()}
              className="btn-secondary btn-sm disabled:opacity-50"
            >
              {isValidating ? "Validating..." : "Validate URL"}
            </button>
          </div>

          <div className="space-y-2">
            <label className="text-[11px] font-black uppercase tracking-widest text-aura-on-surface-variant">
              Content Objective
            </label>
            <textarea
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              className="w-full rounded-3xl bg-aura-surface-container px-5 py-4 min-h-[120px] outline-none text-sm text-aura-on-surface"
              placeholder="Describe what the content should focus on."
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => setInputMode("ai_autonomous")}
              className={cn(
                "rounded-3xl border p-5 text-left transition-all",
                inputMode === "ai_autonomous"
                  ? "border-aura-primary bg-aura-primary/5"
                  : "border-aura-outline-variant/20",
              )}
            >
              <p className="text-sm font-black text-aura-on-surface">AI Autonomous</p>
              <p className="text-xs text-aura-on-surface-variant mt-2">
                AI records, generates, and assembles the review video automatically.
              </p>
            </button>
            <button
              type="button"
              onClick={() => setInputMode("user_upload")}
              className={cn(
                "rounded-3xl border p-5 text-left transition-all",
                inputMode === "user_upload"
                  ? "border-aura-primary bg-aura-primary/5"
                  : "border-aura-outline-variant/20",
              )}
            >
              <p className="text-sm font-black text-aura-on-surface">User Upload</p>
              <p className="text-xs text-aura-on-surface-variant mt-2">
                AI generates the plan and captions; user records and uploads the final footage.
              </p>
            </button>
          </div>

          <div className="rounded-3xl bg-aura-surface-container-low p-5 flex items-start gap-4">
            <input
              id="publish-to-tiktok"
              type="checkbox"
              checked={publishToTiktok}
              onChange={(event) => setPublishToTiktok(event.target.checked)}
              className="mt-1 h-4 w-4 rounded border-aura-outline-variant"
            />
            <div className="space-y-1">
              <label
                htmlFor="publish-to-tiktok"
                className="text-sm font-bold text-aura-on-surface"
              >
                Publish to TikTok with auto-generated captions
              </label>
              <p className="text-xs text-aura-on-surface-variant">
                Requires Telegram auth and at least one active TikTok integration.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating || selectedPersonas.length === 0 || !sourceUrl.trim()}
              className="btn-primary btn-lg flex items-center gap-2 disabled:opacity-50"
            >
              {isGenerating ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Wand2 className="w-5 h-5" />
              )}
              Generate Output
            </button>
            {onNavigateToPersonas && (
              <button
                type="button"
                onClick={onNavigateToPersonas}
                className="btn-secondary btn-sm"
              >
                Create Your Own Persona
              </button>
            )}
          </div>
        </div>

        <div className="xl:col-span-5 dashboard-panel p-8 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-black text-aura-on-surface font-headline">
              Publishing Readiness
            </h2>
            <span className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
              {requirements?.tiktok_channels_total || 0} channels
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-3xl bg-aura-surface-container-low p-5">
              <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
                Telegram
              </p>
              <p className="mt-3 text-xl font-black text-aura-on-surface">
                {requirements?.telegram_linked ? "Linked" : "Not linked"}
              </p>
            </div>
            <div className="rounded-3xl bg-aura-surface-container-low p-5">
              <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
                TikTok
              </p>
              <p className="mt-3 text-xl font-black text-aura-on-surface">
                {requirements?.tiktok_channels_active ? "Active" : "Inactive"}
              </p>
            </div>
          </div>
          {validationResult ? (
            <div className="rounded-3xl border border-aura-outline-variant/10 p-5 space-y-3">
              <p className="text-sm font-black text-aura-on-surface">
                {validationResult.page_title || "Source validated"}
              </p>
              <p className="text-xs text-aura-on-surface-variant break-all">
                {validationResult.normalized_url || sourceUrl}
              </p>
              {validationResult.visible_features?.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {validationResult.visible_features.slice(0, 6).map((feature: any, index: number) => (
                    <span
                      key={`${feature.name || "feature"}-${index}`}
                      className="rounded-full bg-aura-primary/10 px-3 py-1 text-[11px] font-bold text-aura-primary"
                    >
                      {feature.name || feature.label || "Feature"}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-aura-on-surface-variant">
              Validate a source URL to preview page title and visible features before generation.
            </p>
          )}
        </div>
      </section>

      <section className="space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-2xl font-black text-aura-on-surface font-headline">
              Select Persona Options
            </h2>
            <p className="text-sm text-aura-on-surface-variant">
              English, Chinese, Spanish, Arabic, plus custom personas from your workspace.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              if (selectedPersonas.length === personaOptions.length) {
                setSelectedPersonas([]);
              } else {
                setSelectedPersonas(personaOptions.map((persona) => persona.persona_id));
              }
            }}
            className="btn-secondary btn-sm"
          >
            {selectedPersonas.length === personaOptions.length ? "Deselect All" : "Select All"}
          </button>
        </div>

        {personaOptions.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
            {personaOptions.map((persona) => {
              const isSelected = selectedPersonas.includes(persona.persona_id);
              const activeChannels = persona.tiktok_integration?.active_channels || 0;
              return (
                <button
                  key={persona.persona_id}
                  type="button"
                  onClick={() => handleTogglePersona(persona.persona_id)}
                  className={cn(
                    "dashboard-panel p-4 text-left transition-all border-2",
                    isSelected
                      ? "border-aura-primary bg-aura-primary/5"
                      : "border-transparent hover:border-aura-outline-variant/20",
                  )}
                >
                  <img
                    alt={persona.display_name}
                    className="w-full aspect-[4/5] rounded-2xl object-cover mb-4"
                    src={
                      persona.selection_image_url ||
                      persona.image_url ||
                      "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop"
                    }
                  />
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-black text-aura-on-surface truncate">
                        {persona.display_name}
                      </p>
                      {isSelected && <Check className="w-4 h-4 text-aura-primary" />}
                    </div>
                    <p className="text-xs text-aura-on-surface-variant uppercase tracking-widest">
                      {persona.region_label || persona.language || "Global"}
                    </p>
                    <p className="text-xs text-aura-on-surface-variant line-clamp-2">
                      {persona.description || "Ready for regional app review production."}
                    </p>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className={cn("rounded-full border px-2.5 py-1 font-bold", statusPillClass(activeChannels > 0 ? "published" : "draft"))}>
                        {activeChannels > 0 ? "TikTok active" : "TikTok inactive"}
                      </span>
                      {persona.demo?.available && (
                        <span className="text-aura-primary font-bold">Demo</span>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="dashboard-panel-soft p-10 text-center text-aura-on-surface-variant">
            No personas found yet.
          </div>
        )}
      </section>

      <section className="space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-2xl font-black text-aura-on-surface font-headline">
              Activity Feed
            </h2>
            <p className="text-sm text-aura-on-surface-variant">
              Step 1 URL, Step 2 persona, Step 3 final product. Edit content, upload manual video, or publish.
            </p>
          </div>
          {onNavigateToPublishing && (
            <button
              type="button"
              onClick={onNavigateToPublishing}
              className="btn-secondary btn-sm"
            >
              Open Publishing
            </button>
          )}
        </div>

        {jobs.length > 0 ? (
          <div className="space-y-6">
            {jobs.map((job) => {
              const personaImage =
                getReviewJobPersonaImage(job) ||
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop";
              const statusLabel = getReviewJobStatusLabel(job);
              return (
                <article key={job.job_id} className="dashboard-panel p-6 space-y-6">
                  <div className="flex flex-col xl:flex-row gap-6">
                    <div className="xl:w-72 shrink-0 space-y-4">
                      {job.production?.playable_video_url ? (
                        <video
                          className="w-full aspect-[9/16] rounded-3xl object-cover bg-black"
                          src={job.production.playable_video_url}
                          controls
                          playsInline
                        />
                      ) : (
                        <img
                          alt={job.persona?.display_name || "Persona"}
                          className="w-full aspect-[9/16] rounded-3xl object-cover"
                          src={personaImage}
                        />
                      )}
                      <div className="rounded-3xl bg-aura-surface-container-low p-4">
                        <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
                          Persona
                        </p>
                        <p className="mt-2 text-lg font-black text-aura-on-surface">
                          {job.persona?.display_name || "Persona"}
                        </p>
                        <p className="text-xs text-aura-on-surface-variant mt-1">
                          {job.persona?.region_label || job.persona?.language || "Global"}
                        </p>
                      </div>
                    </div>

                    <div className="flex-1 space-y-5">
                      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                        <div>
                          <h3 className="text-2xl font-black text-aura-on-surface font-headline">
                            {job.content?.title || job.page_title || "App Review"}
                          </h3>
                          <p className="text-sm text-aura-on-surface-variant mt-2 break-all">
                            {job.source_url}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <span className={cn("rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-widest", statusPillClass(job.publish?.status || job.status))}>
                            {statusLabel}
                          </span>
                          <span className={cn("rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-widest", statusPillClass(job.production?.ready ? "published" : "draft"))}>
                            {job.production?.ready ? "Final product ready" : "In production"}
                          </span>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="w-full h-2 rounded-full bg-aura-surface-container overflow-hidden">
                          <div
                            className={`h-full bg-gradient-to-r ${progressBarClass(job)}`}
                            style={{ width: `${job.progress || 0}%` }}
                          />
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {job.activity_feed?.map((step) => (
                            <span
                              key={`${job.job_id}-${step.key}`}
                              className={cn(
                                "rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-widest",
                                step.status === "completed"
                                  ? "bg-emerald-50 text-emerald-700"
                                  : step.status === "in_progress"
                                    ? "bg-aura-primary/10 text-aura-primary"
                                    : "bg-aura-surface-container text-aura-on-surface-variant",
                              )}
                            >
                              {step.label}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                        <div className="rounded-3xl bg-aura-surface-container-low p-5 space-y-3">
                          <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
                            Editable Content
                          </p>
                          <textarea
                            value={drafts[job.job_id] || ""}
                            onChange={(event) =>
                              setDrafts((current) => ({
                                ...current,
                                [job.job_id]: event.target.value,
                              }))
                            }
                            className="w-full min-h-[180px] rounded-2xl bg-white px-4 py-4 outline-none text-sm text-aura-on-surface"
                          />
                          <button
                            type="button"
                            onClick={() => void handleSaveJob(job)}
                            disabled={savingJobId === job.job_id}
                            className="btn-secondary btn-sm disabled:opacity-50"
                          >
                            {savingJobId === job.job_id ? "Saving..." : "Save Content"}
                          </button>
                        </div>

                        <div className="rounded-3xl bg-aura-surface-container-low p-5 space-y-4">
                          <div>
                            <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
                              Publish State
                            </p>
                            <p className="mt-2 text-sm font-bold text-aura-on-surface">
                              {job.publish?.status || "not_requested"}
                            </p>
                          </div>
                          {job.publish?.publish_error && (
                            <p className="text-xs text-amber-700 rounded-2xl bg-amber-50 px-4 py-3">
                              {job.publish.publish_error}
                            </p>
                          )}
                          {job.publish?.post_url && (
                            <a
                              href={job.publish.post_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-2 text-sm font-bold text-aura-primary"
                            >
                              View published post <ExternalLink className="w-4 h-4" />
                            </a>
                          )}
                          {job.type === "app_review_upload" && !job.production?.ready && (
                            <label className="btn-secondary btn-sm inline-flex items-center gap-2 cursor-pointer">
                              <Upload className="w-4 h-4" />
                              {uploadingJobId === job.job_id ? "Uploading..." : "Upload final video"}
                              <input
                                type="file"
                                accept="video/*"
                                className="hidden"
                                onChange={(event) =>
                                  void handleUploadVideo(
                                    job.job_id,
                                    event.target.files?.[0] || null,
                                  )
                                }
                              />
                            </label>
                          )}
                          <div className="flex flex-wrap gap-3 pt-2">
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
                            ) : null}
                            <button
                              type="button"
                              disabled={
                                !job.production?.ready ||
                                job.publish?.status === "published" ||
                                publishingJobId === job.job_id
                              }
                              onClick={() => void handlePublishJob(job.job_id)}
                              className="btn-primary btn-sm flex items-center gap-2 disabled:opacity-50"
                            >
                              {publishingJobId === job.job_id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Send className="w-4 h-4" />
                              )}
                              {job.publish?.status === "published" ? "Published" : "Publish"}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="dashboard-panel-soft p-12 text-center text-aura-on-surface-variant">
            No app review jobs yet. Generate one above.
          </div>
        )}
      </section>
    </div>
  );
}
