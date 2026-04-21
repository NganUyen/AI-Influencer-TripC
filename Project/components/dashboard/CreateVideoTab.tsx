'use client';

import '@/app/create-video.css';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Clapperboard, FileCheck2, Play, Settings2, type LucideIcon } from 'lucide-react';
import { toast } from 'react-hot-toast';
import type { Persona } from '@/components/customer-dashboard';
import type {
  ReviewEngineJob,
  ReviewEngineJobResponse,
  ReviewEngineSetup,
} from '@/lib/review-engine';
import {
  getReviewJobActiveTikTokChannels,
  getReviewJobChannelLabel,
  getReviewJobPreferredTikTokChannelId,
} from '@/lib/review-engine';
import { customerApiRequest } from '@/lib/customer-api';
import {
  deriveStepFromJobs,
  getJobsForPlanIds,
  getPlanIdsFromJobs,
  inferBackendFlowJobs,
} from '@/lib/create-video-flow';
import type {
  CreateVideoProgressViewModel,
  CreateVideoSetupState,
  PersonaPlanCardViewModel,
  ScenePreviewItem,
  SharedContractDraft,
} from '@/types/video-planning';
import type { ReviewEngineMasterContract } from '@/lib/review-engine';
import {
  formatScenesForEditor,
  toScenePreviewItem,
} from '@/lib/create-video-contract';
import { DEFAULT_SETUP_STATE } from '@/types/video-planning';
import {
  buildCreateJobPayload,
  buildCreativePreferences,
  isCreateVideoModeSupportedForSubmit,
  toPersonaPlanCards,
  toRenderProgressItems,
} from '@/adapters/create-video-adapter';
import { CreateVideoSetupStep } from './create-video/CreateVideoSetupStep';
import { CreateVideoReviewStep } from './create-video/CreateVideoReviewStep';
import { CreateVideoRenderStep } from './create-video/CreateVideoRenderStep';

type Step = 1 | 2 | 3 | 4;

interface CreateVideoTabProps {
  personas: Persona[];
  setup?: ReviewEngineSetup | null;
  initialJobs?: ReviewEngineJob[];
  onRefresh?: () => Promise<void> | void;
  initialSourceUrl?: string;
  initialPersonaIds?: string[];
}

const ACTIVE_FLOW_STORAGE_KEY = 'create-video-active-flow';
const ACTIVE_FLOW_MAX_AGE_MS = 1000 * 60 * 60 * 6;

function jobKey(job: ReviewEngineJob): string {
  return String(job.plan_id || job.job_id);
}

function sortJobs(jobs: ReviewEngineJob[]): ReviewEngineJob[] {
  return [...jobs].sort((left, right) => {
    const leftStamp =
      left.updated_at || left.started_at || left.created_at || '';
    const rightStamp =
      right.updated_at || right.started_at || right.created_at || '';
    return rightStamp.localeCompare(leftStamp);
  });
}

function mergeJobs(
  existing: ReviewEngineJob[],
  incoming: ReviewEngineJob[],
): ReviewEngineJob[] {
  const merged = new Map<string, ReviewEngineJob>();
  existing.forEach((job) => merged.set(jobKey(job), job));
  incoming.forEach((job) => merged.set(jobKey(job), job));
  return sortJobs(Array.from(merged.values()));
}

function parseScenesFromEditor(input: string): ScenePreviewItem[] {
  return input
    .split('\n')
    .map((row) => row.trim())
    .filter(Boolean)
    .map((row, idx) => {
      const [descPart, durationPart] = row.split('|').map((part) => part.trim());
      const duration = durationPart
        ? Number(durationPart.replace(/[^\d.]/g, ''))
        : Number.NaN;
      return {
        index: idx + 1,
        description: descPart || `Scene ${idx + 1}`,
        durationSeconds: Number.isFinite(duration) ? duration : undefined,
      };
    });
}

function buildSharedContractDraft(
  jobs: ReviewEngineJob[],
  masterContract?: ReviewEngineMasterContract | null,
): SharedContractDraft {
  const masterSource = masterContract || jobs[0]?.master_contract || jobs[0]?.publish_settings?.shared_contract;
  if (masterSource) {
    const scenes = Array.isArray(masterSource.scenes_data)
      ? masterSource.scenes_data.map((scene, index) => toScenePreviewItem(scene, index))
      : [];
    return {
      scriptText: String(masterSource.script_text || '').trim(),
      scenesText: formatScenesForEditor(scenes),
    };
  }

  const firstJob = jobs[0];
  const scriptText = String(
    firstJob?.script?.script || firstJob?.editable_content || firstJob?.content?.body || '',
  ).trim();
  const scenes = Array.isArray(firstJob?.script?.scenes)
    ? firstJob.script?.scenes.map((scene, index) => toScenePreviewItem(scene, index))
    : [];
  return {
    scriptText,
    scenesText: formatScenesForEditor(scenes),
  };
}

function syncPlanCardsWithSharedDraft(
  cards: PersonaPlanCardViewModel[],
  draft: SharedContractDraft,
): PersonaPlanCardViewModel[] {
  const scenes = parseScenesFromEditor(draft.scenesText);
  return cards.map((card) => ({
    ...card,
    scriptPreview: draft.scriptText.trim() || card.scriptPreview,
    scenes: scenes.length > 0 ? scenes : card.scenes,
  }));
}

function resetReviewFlowState() {
  return {
    activePlanIds: [] as string[],
    planCards: [] as PersonaPlanCardViewModel[],
    progressItems: [] as CreateVideoProgressViewModel[],
    sharedContractDraft: { scriptText: '', scenesText: '' } as SharedContractDraft,
    sharedContractDirty: false,
    currentStep: 1 as Step,
  };
}

function haveSamePlanIds(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((value, index) => value === right[index]);
}

function PublishStep({
  jobs,
  publishingJobId,
  onPublish,
  selectedChannelIds,
  onChannelChange,
  onBack,
}: {
  jobs: ReviewEngineJob[];
  publishingJobId: string | null;
  onPublish: (jobId: string, socialAccountId?: string | null) => void;
  selectedChannelIds: Record<string, string>;
  onChannelChange: (jobId: string, socialAccountId: string) => void;
  onBack: () => void;
}) {
  const publishableJobs = jobs.filter(
    (job) => job.production?.ready && job.production?.publish_enabled,
  );

  return (
    <div className="cv-step-panel">
      <div className="cv-step-content-inner" style={{ display: 'grid', gap: 18 }}>
        <div>
          <h2 className="cv-step-title">Publish</h2>
          <p className="cv-step-subtitle">
            Only backend-supported publish actions are shown here.
          </p>
        </div>

        {publishableJobs.length === 0 ? (
          <div className="cv-empty-box">
            No backend publish actions are available for the current flow yet.
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 12 }}>
            {publishableJobs.map((job) => {
              const alreadyPublished = job.publish?.status === 'published';
              const activeChannels = getReviewJobActiveTikTokChannels(job);
              const selectedChannelId =
                selectedChannelIds[job.job_id] ?? getReviewJobPreferredTikTokChannelId(job);
              const needsExplicitChannelSelection = activeChannels.length > 1;
              const selectedChannel = activeChannels.find(
                (channel) => channel.id === selectedChannelId,
              );
              const publishDisabled =
                alreadyPublished ||
                publishingJobId === job.job_id ||
                (needsExplicitChannelSelection && !selectedChannelId);
              return (
                <div
                  key={job.plan_id || job.job_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 12,
                    border: '1px solid rgb(174 173 169 / 0.2)',
                    borderRadius: 12,
                    padding: '12px 14px',
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ display: 'grid', gap: 8, minWidth: 240, flex: 1 }}>
                    <strong>{job.persona?.display_name || job.persona_id || 'Persona'}</strong>
                    <span className="cv-cta-disabled-reason">
                      {job.page_title || job.objective || 'Ready for publish'}
                    </span>
                    {activeChannels.length > 0 && (
                      needsExplicitChannelSelection ? (
                        <label
                          style={{
                            display: 'grid',
                            gap: 6,
                            fontSize: 12,
                            color: 'var(--cv-text-muted, #6b7280)',
                          }}
                        >
                          <span>Choose TikTok channel</span>
                          <select
                            value={selectedChannelId || ''}
                            onChange={(event) =>
                              onChannelChange(job.job_id, event.target.value)
                            }
                            style={{
                              minHeight: 38,
                              borderRadius: 10,
                              border: '1px solid rgb(174 173 169 / 0.3)',
                              padding: '8px 10px',
                              background: '#fff',
                              color: '#111827',
                            }}
                          >
                            <option value="">Select channel</option>
                            {activeChannels.map((channel) => (
                              <option key={channel.id || channel.handle || 'channel'} value={channel.id || ''}>
                                {getReviewJobChannelLabel(channel)}
                              </option>
                            ))}
                          </select>
                        </label>
                      ) : (
                        <span className="cv-cta-disabled-reason">
                          Channel: {getReviewJobChannelLabel(activeChannels[0])}
                        </span>
                      )
                    )}
                    {needsExplicitChannelSelection && !selectedChannelId && (
                      <span className="cv-cta-disabled-reason">
                        Pick a TikTok channel before publish.
                      </span>
                    )}
                    {selectedChannel && (
                      <span className="cv-cta-disabled-reason">
                        Target: {getReviewJobChannelLabel(selectedChannel)}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {job.production?.playable_video_url && (
                      <a
                        className="btn-secondary"
                        href={job.production.playable_video_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Preview
                      </a>
                    )}
                    <button
                      className="btn-primary"
                      type="button"
                      disabled={publishDisabled}
                      onClick={() => onPublish(job.job_id, selectedChannelId)}
                    >
                      {alreadyPublished
                        ? 'Published'
                        : publishingJobId === job.job_id
                          ? 'Publishing…'
                          : 'Publish to TikTok'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="cv-step-actions">
          <button className="btn-secondary" onClick={onBack}>
            Back
          </button>
        </div>
      </div>
    </div>
  );
}

export function CreateVideoTab({
  personas,
  setup,
  initialJobs = [],
  onRefresh,
  initialSourceUrl = '',
  initialPersonaIds = [],
}: CreateVideoTabProps) {
  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [setupState, setSetupState] = useState<CreateVideoSetupState>(DEFAULT_SETUP_STATE);
  const [jobs, setJobs] = useState<ReviewEngineJob[]>(initialJobs);
  const [planCards, setPlanCards] = useState<PersonaPlanCardViewModel[]>([]);
  const [progressItems, setProgressItems] = useState<CreateVideoProgressViewModel[]>([]);
  const [sharedContractDraft, setSharedContractDraft] = useState<SharedContractDraft>({
    scriptText: '',
    scenesText: '',
  });
  const [sharedContractDirty, setSharedContractDirty] = useState(false);
  const [activePlanIds, setActivePlanIds] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSavingPlans, setIsSavingPlans] = useState(false);
  const [isSubmittingPlans, setIsSubmittingPlans] = useState(false);
  const [uploadingPlanIds, setUploadingPlanIds] = useState<string[]>([]);
  const [publishingJobId, setPublishingJobId] = useState<string | null>(null);
  const [selectedPublishChannelIds, setSelectedPublishChannelIds] = useState<
    Record<string, string>
  >({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const restoredFlowPlanIdsRef = useRef<string[] | null>(null);

  // UI/UX Pro Max Enhanced Loading State
  const [generatingStage, setGeneratingStage] = useState<'validating' | 'generating' | 'finalizing' | null>(null);
  const [isGeneratingSuccess, setIsGeneratingSuccess] = useState(false);

  const setupPersonaLists = useMemo(() => {
    if (setup) {
      const configuredSystemPersonas = (setup.persona_options || []).map(reviewPersonaToPersona);
      const configuredCustomPersonas = (setup.custom_personas || []).map(reviewPersonaToPersona);
      const systemPersonas = dedupePersonas([
        ...configuredSystemPersonas,
        ...configuredCustomPersonas.filter(isSystemPersona),
      ]);
      const customPersonas = configuredCustomPersonas.filter((persona) => !isSystemPersona(persona));
      return {
        systemPersonas,
        customPersonas,
        allPersonas: [...systemPersonas, ...customPersonas],
      };
    }

    const systemPersonas = personas.filter(isSystemPersona);
    const customPersonas = personas.filter((persona) => !isSystemPersona(persona));
    return {
      systemPersonas,
      customPersonas,
      allPersonas: personas,
    };
  }, [personas, setup]);

  const persistActiveFlow = useCallback((planIds: string[]) => {
    if (typeof window === 'undefined') {
      return;
    }
    if (planIds.length === 0) {
      window.localStorage.removeItem(ACTIVE_FLOW_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(
      ACTIVE_FLOW_STORAGE_KEY,
      JSON.stringify({ planIds, updatedAt: Date.now() }),
    );
  }, []);

  const refreshJobs = useCallback(async (silent = false): Promise<ReviewEngineJob[]> => {
    try {
      const payload = await customerApiRequest<ReviewEngineJobResponse>(
        '/api/customer/review-engine/jobs',
      );
      const nextJobs = payload.jobs || [];
      setJobs(nextJobs);
      return nextJobs;
    } catch (error) {
      if (!silent) {
        const message =
          error instanceof Error ? error.message : 'Failed to refresh review-engine jobs';
        setErrorMessage(message);
      }
      throw error;
    }
  }, []);

  const persistPlanCards = useCallback(async (cards: PersonaPlanCardViewModel[]) => {
    const creativePreferences = buildCreativePreferences(setupState);
    const editableCards = cards.filter((card) => card.planId);
    if (editableCards.length === 0) {
      return;
    }
    const scriptText = sharedContractDraft.scriptText.trim();
    const scenesData = parseScenesFromEditor(sharedContractDraft.scenesText);
    await Promise.all(
      editableCards.map((card) =>
        customerApiRequest(`/api/customer/review-engine/plans/${card.planId}`, {
          method: 'PATCH',
          body: JSON.stringify({
            script_text: scriptText,
            scenes_data: scenesData,
            publish_settings: {
              shared_contract: {
                language: 'English',
                script_text: scriptText,
                scenes_data: scenesData,
              },
            },
            creative_preferences: creativePreferences,
          }),
        }),
      ),
    );
  }, [setupState, sharedContractDraft]);

  useEffect(() => {
    setJobs(initialJobs);
  }, [initialJobs]);

  useEffect(() => {
    void refreshJobs(true).catch(() => undefined);
  }, [refreshJobs]);

  useEffect(() => {
    setSetupState((current) => ({
      ...current,
      sourceUrl: current.sourceUrl || initialSourceUrl,
      selectedPersonaIds:
        current.selectedPersonaIds.length > 0
          ? current.selectedPersonaIds
          : initialPersonaIds,
    }));
  }, [initialPersonaIds, initialSourceUrl]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const raw = window.localStorage.getItem(ACTIVE_FLOW_STORAGE_KEY);
    if (!raw) {
      return;
    }
    try {
      const payload = JSON.parse(raw) as { planIds?: string[]; updatedAt?: number };
      const updatedAt = Number(payload.updatedAt || 0);
      if (!Number.isFinite(updatedAt) || Date.now() - updatedAt > ACTIVE_FLOW_MAX_AGE_MS) {
        window.localStorage.removeItem(ACTIVE_FLOW_STORAGE_KEY);
        return;
      }
      const nextPlanIds = Array.isArray(payload.planIds)
        ? payload.planIds.filter(Boolean)
        : [];
      if (nextPlanIds.length > 0) {
        restoredFlowPlanIdsRef.current = nextPlanIds;
        setActivePlanIds(nextPlanIds);
      }
    } catch {
      window.localStorage.removeItem(ACTIVE_FLOW_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    const restoredPlanIds = restoredFlowPlanIdsRef.current;
    if (!restoredPlanIds) {
      return;
    }

    const restoredJobs = getJobsForPlanIds(jobs, restoredPlanIds);
    if (restoredJobs.length === 0) {
      setActivePlanIds([]);
      setCurrentStep(1);
      setPlanCards([]);
      setProgressItems([]);
      setSharedContractDraft({ scriptText: '', scenesText: '' });
      setSharedContractDirty(false);
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(ACTIVE_FLOW_STORAGE_KEY);
      }
    }

    restoredFlowPlanIdsRef.current = null;
  }, [jobs]);

  const explicitActiveJobs = useMemo(() => {
    return getJobsForPlanIds(jobs, activePlanIds);
  }, [activePlanIds, jobs]);

  const inferredActiveJobs = useMemo(() => {
    return inferBackendFlowJobs(jobs);
  }, [jobs]);

  const inferredActivePlanIds = useMemo(() => {
    return getPlanIdsFromJobs(inferredActiveJobs);
  }, [inferredActiveJobs]);

  const activeJobs = useMemo(() => {
    if (explicitActiveJobs.length > 0) {
      return explicitActiveJobs;
    }
    return inferredActiveJobs;
  }, [explicitActiveJobs, inferredActiveJobs]);

  useEffect(() => {
    if (inferredActivePlanIds.length === 0) {
      return;
    }
    setActivePlanIds((current) => {
      if (current.length > 0 && explicitActiveJobs.length > 0) {
        return current;
      }
      return haveSamePlanIds(current, inferredActivePlanIds)
        ? current
        : inferredActivePlanIds;
    });
  }, [explicitActiveJobs.length, inferredActivePlanIds]);

  const isAllTerminal = activeJobs.length > 0 && activeJobs.every((job) => {
    const s = String(job.status || '').toLowerCase();
    return s === 'completed' || s === 'failed' || job.production?.ready;
  });

  const shouldPollJobs = 
    (activePlanIds.length > 0 || inferredActiveJobs.length > 0) && 
    !isAllTerminal;

  useEffect(() => {
    if (!shouldPollJobs) {
      return;
    }
    void refreshJobs(true).catch(() => undefined);
    const interval = window.setInterval(() => {
      void refreshJobs(true).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(interval);
  }, [refreshJobs, shouldPollJobs]);

  useEffect(() => {
    if (activeJobs.length === 0) {
      return;
    }
    setPlanCards((current) => {
      const nextCards = toPersonaPlanCards(activeJobs);
      const currentById = new Map(current.map((c) => [c.planId || c.jobId, c]));
      const changed = nextCards.some((card) => {
        const existing = currentById.get(card.planId || card.jobId);
        return !existing || JSON.stringify(existing) !== JSON.stringify({ ...card, reviewDecision: existing.reviewDecision });
      });
      
      if (!changed) return current;

      return nextCards.map((card) => {
        const existing = currentById.get(card.planId || card.jobId);
        return existing ? { ...card, reviewDecision: existing.reviewDecision } : card;
      });
    });

    const nextProgress = toRenderProgressItems(activeJobs);
    setProgressItems((current) => {
      if (JSON.stringify(current) === JSON.stringify(nextProgress)) return current;
      return nextProgress;
    });

    if (!sharedContractDirty) {
      const nextDraft = buildSharedContractDraft(activeJobs);
      setSharedContractDraft((current) => {
        if (current.scriptText === nextDraft.scriptText && current.scenesText === nextDraft.scenesText) return current;
        return nextDraft;
      });
    }

    const derivedStep = deriveStepFromJobs(activeJobs);
    const autoStep = Math.min(derivedStep, 3) as Step;
    setCurrentStep((current) => {
      if (autoStep > current) {
        return autoStep;
      }
      return current;
    });
  }, [activeJobs, sharedContractDirty]);

  useEffect(() => {
    setSelectedPublishChannelIds((current) => {
      const next: Record<string, string> = {};
      for (const job of activeJobs) {
        const jobId = String(job.job_id);
        const activeChannels = getReviewJobActiveTikTokChannels(job);
        const currentSelection = current[jobId];
        if (
          currentSelection &&
          activeChannels.some((channel) => channel.id === currentSelection)
        ) {
          next[jobId] = currentSelection;
          continue;
        }
        const preferred = getReviewJobPreferredTikTokChannelId(job);
        if (preferred) {
          next[jobId] = preferred;
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
  }, [activeJobs]);

  useEffect(() => {
    persistActiveFlow(activePlanIds);
  }, [activePlanIds, persistActiveFlow]);

  const handleSetupChange = useCallback((patch: Partial<CreateVideoSetupState>) => {
    setSetupState((current) => ({ ...current, ...patch }));
  }, []);

  const goToStep2 = useCallback(async () => {
    if (!isCreateVideoModeSupportedForSubmit(setupState.selectedMode)) {
      const message = 'Selected mode is not supported yet.';
      setErrorMessage(message);
      toast.error(message);
      return;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });

    setErrorMessage(null);
    setIsGenerating(true);
    setGeneratingStage('validating');
    setIsGeneratingSuccess(false);

    // Track simulated progress stages over time
    const simulatedTimer1 = setTimeout(() => setGeneratingStage('generating'), 2000);
    const simulatedTimer2 = setTimeout(() => setGeneratingStage('finalizing'), 7000);

    try {
      const payload = buildCreateJobPayload(setupState);
      const result = await customerApiRequest<{
        jobs: ReviewEngineJob[];
        master_contract?: ReviewEngineMasterContract | null;
        warnings?: Array<{ message?: string }>;
      }>('/api/customer/review-engine/jobs', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const nextJobs = result.jobs || [];
      const nextPlanIds = nextJobs
        .map((job) => String(job.plan_id || '').trim())
        .filter(Boolean);
      setJobs((current) => mergeJobs(current, nextJobs));
      setActivePlanIds(nextPlanIds);
      setPlanCards(toPersonaPlanCards(nextJobs));
      setSharedContractDraft(buildSharedContractDraft(nextJobs, result.master_contract));
      setSharedContractDirty(false);
      setProgressItems([]);
      
      if (result.warnings?.[0]?.message) {
        toast(`Review jobs created with a warning: ${result.warnings[0].message}`);
      }
      await Promise.resolve(onRefresh?.());

      // Success UX: show checkmark for 500ms before transition
      clearTimeout(simulatedTimer1);
      clearTimeout(simulatedTimer2);
      setGeneratingStage(null);
      setIsGeneratingSuccess(true);
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setCurrentStep(2);
    } catch (error) {
      clearTimeout(simulatedTimer1);
      clearTimeout(simulatedTimer2);
      setGeneratingStage(null);
      const message =
        error instanceof Error ? error.message : 'Failed to create review jobs';
      setErrorMessage(message);
      toast.error(message);
    } finally {
      clearTimeout(simulatedTimer1);
      clearTimeout(simulatedTimer2);
      setIsGenerating(false);
      setIsGeneratingSuccess(false);
    }
  }, [onRefresh, setupState]);
  const savePlanEdits = useCallback(async () => {
    setErrorMessage(null);
    setIsSavingPlans(true);
    try {
      await persistPlanCards(planCards);
      setSharedContractDirty(false);
      await refreshJobs();
      await Promise.resolve(onRefresh?.());
      toast.success('Shared contract saved and synced to editable persona plans.');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to save plan edits';
      setErrorMessage(message);
      toast.error(`Shared edits were not saved: ${message}`);
    } finally {
      setIsSavingPlans(false);
    }
  }, [onRefresh, persistPlanCards, planCards, refreshJobs]);

  const goToStep3 = useCallback(async () => {
    const approvedCards = planCards.filter(
      (card) => card.reviewDecision === 'approved' && card.planId,
    );
    if (approvedCards.length === 0) {
      return;
    }

    setErrorMessage(null);
    setIsSubmittingPlans(true);
    const approvedPlanIds: string[] = [];
    const failedApprovals: string[] = [];
    try {
      await persistPlanCards(planCards);
      setSharedContractDirty(false);

      for (const card of approvedCards) {
        try {
          await customerApiRequest(`/api/customer/review-engine/plans/${card.planId}/approve`, {
            method: 'POST',
            body: JSON.stringify({}),
          });
          approvedPlanIds.push(String(card.planId || '').trim());
        } catch (error) {
          console.error(`[Approve Plan] Failed for ${card.personaName} (${card.planId}):`, error);
          failedApprovals.push(card.personaName);
        }
      }

      const nextPlanIds = approvedPlanIds.filter(Boolean);
      if (nextPlanIds.length === 0) {
        const failMessage = failedApprovals.length > 0
          ? `All ${approvedCards.length} plans failed to approve. Check console for details.`
          : 'No approved plans were selected.';
        throw new Error(failMessage);
      }
      setActivePlanIds(nextPlanIds);
      const nextJobs = await refreshJobs();
      const refreshedActiveJobs = nextJobs.filter((job) =>
        nextPlanIds.includes(String(job.plan_id || '').trim()),
      );
      setPlanCards(toPersonaPlanCards(refreshedActiveJobs));
      setSharedContractDraft(buildSharedContractDraft(refreshedActiveJobs));
      setProgressItems(toRenderProgressItems(refreshedActiveJobs));
      setCurrentStep(3);
      await Promise.resolve(onRefresh?.());
      toast.success(`Approved ${nextPlanIds.length} persona plan${nextPlanIds.length > 1 ? 's' : ''} and moved to Step 3.`);
      if (failedApprovals.length > 0) {
        toast.error(`Some persona plans stayed on Step 2: ${failedApprovals.join(', ')}.`);
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to approve plans';
      const detailedMessage = `${message}${failedApprovals.length > 0 ? ` (${failedApprovals.length} failed)` : ''} - Check browser console for details.`;
      setErrorMessage(detailedMessage);
      toast.error(`Could not approve the selected persona plans: ${message}`);
      console.error('[goToStep3] Approval process error:', error, { failedApprovals });
    } finally {
      setIsSubmittingPlans(false);
    }
  }, [onRefresh, persistPlanCards, planCards, refreshJobs]);

  const deleteReviewPlans = useCallback(async (planIds: string[]) => {
    const uniquePlanIds = Array.from(new Set(planIds.map((planId) => planId.trim()).filter(Boolean)));
    if (uniquePlanIds.length === 0) {
      throw new Error('No plans were selected for discard.');
    }

    setErrorMessage(null);
    const failures: string[] = [];

    for (const planId of uniquePlanIds) {
      try {
        await customerApiRequest(`/api/customer/review-engine/plans/${planId}`, {
          method: 'DELETE',
        });
      } catch (error) {
        console.error(`[Delete Plan] Failed for planId ${planId}:`, error);
        failures.push(planId);
      }
    }

    if (failures.length > 0) {
      const message = `Failed to discard plan(s): ${failures.join(', ')}`;
      setErrorMessage(message);
      toast.error(message);
      throw new Error(message);
    }

    await refreshJobs();
    await Promise.resolve(onRefresh?.());
    const nextState = resetReviewFlowState();
    setActivePlanIds(nextState.activePlanIds);
    setPlanCards(nextState.planCards);
    setProgressItems(nextState.progressItems);
    setSharedContractDraft(nextState.sharedContractDraft);
    setSharedContractDirty(nextState.sharedContractDirty);
    setCurrentStep(nextState.currentStep);
    toast.success('Discarded the selected plan(s) and returned to Setup.');
  }, [onRefresh, refreshJobs]);

  const handleUploadPlanVideo = useCallback(async (planId: string, file: File | null) => {
    if (!file) {
      return;
    }
    setErrorMessage(null);
    setUploadingPlanIds((current) => [...current, planId]);
    try {
      const updatedJob = await customerApiRequest<ReviewEngineJob>(
        `/api/customer/review-engine/jobs/${planId}/upload`,
        {
          method: 'POST',
          headers: {
            'Content-Type': file.type || 'video/mp4',
            'x-filename': file.name,
          },
          body: file,
        },
      );
      setJobs((current) => mergeJobs(current, [updatedJob]));
      await Promise.resolve(onRefresh?.());
      toast.success('Video uploaded.');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to upload video';
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setUploadingPlanIds((current) => current.filter((item) => item !== planId));
    }
  }, [onRefresh]);

  const handlePublishJob = useCallback(async (jobId: string, socialAccountId?: string | null) => {
    setErrorMessage(null);
    setPublishingJobId(jobId);
    try {
      const updatedJob = await customerApiRequest<ReviewEngineJob>(
        `/api/customer/review-engine/jobs/${jobId}/publish`,
        {
          method: 'POST',
          body: JSON.stringify(
            socialAccountId ? { social_account_id: socialAccountId } : {},
          ),
        },
      );
      setJobs((current) => mergeJobs(current, [updatedJob]));
      await Promise.resolve(onRefresh?.());
      toast.success('Publish request sent.');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to publish review job';
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setPublishingJobId(null);
    }
  }, [onRefresh]);

  const goBack = useCallback((toStep: Step) => {
    setCurrentStep(toStep);
  }, []);

  const generatingOverlayVisible = isGenerating || isGeneratingSuccess;
  const generatingStageLabel =
    generatingStage === 'validating'
      ? 'Validating source context...'
      : generatingStage === 'generating'
        ? 'Generating scripts...'
        : 'Finalizing plans...';

  return (
    <div className={`cv-container${generatingOverlayVisible ? ' cv-container--submitting' : ''}`}>
      <StepIndicator currentStep={currentStep} />

      {errorMessage && (
        <div className="cv-empty-box" style={{ marginBottom: 20 }}>
          {errorMessage}
        </div>
      )}

      <div className="cv-step-content">
        {currentStep === 1 && (
          <CreateVideoSetupStep
            setupState={setupState}
            onChange={handleSetupChange}
            personas={setupPersonaLists.allPersonas}
            systemPersonaOptions={setupPersonaLists.systemPersonas}
            customPersonaOptions={setupPersonaLists.customPersonas}
            isSubmitting={isGenerating || isGeneratingSuccess}
            onContinue={goToStep2}
          />
        )}
        {currentStep === 2 && (
          <CreateVideoReviewStep
            planCards={planCards}
            sharedContractDraft={sharedContractDraft}
            hasUnsavedChanges={sharedContractDirty}
            onSharedContractChange={(nextDraft) => {
              setSharedContractDraft(nextDraft);
              setPlanCards((current) => syncPlanCardsWithSharedDraft(current, nextDraft));
              setSharedContractDirty(true);
            }}
            onResetSharedContract={() => {
              const baselineDraft = buildSharedContractDraft(activeJobs);
              setSharedContractDraft(baselineDraft);
              setPlanCards((current) => syncPlanCardsWithSharedDraft(current, baselineDraft));
              setSharedContractDirty(false);
            }}
            onCardsChange={setPlanCards}
            onSaveEdits={savePlanEdits}
            isSaving={isSavingPlans}
            onDeletePlans={deleteReviewPlans}
            onReturnToSetup={() => setCurrentStep(1)}
            onUploadPlanVideo={handleUploadPlanVideo}
            uploadingPlanIds={uploadingPlanIds}
            onContinue={goToStep3}
            isContinuing={isSubmittingPlans}
            onBack={() => goBack(1)}
          />
        )}

        {currentStep === 3 && (
          <CreateVideoRenderStep
            progressItems={progressItems}
            onContinue={() => goBack(4)}
            onBack={() => goBack(2)}
          />
        )}

        {currentStep === 4 && (
          <PublishStep
            jobs={activeJobs}
            publishingJobId={publishingJobId}
            selectedChannelIds={selectedPublishChannelIds}
            onChannelChange={(jobId, socialAccountId) => {
              setSelectedPublishChannelIds((current) => {
                if (!socialAccountId) {
                  const next = { ...current };
                  delete next[jobId];
                  return next;
                }
                return {
                  ...current,
                  [jobId]: socialAccountId,
                };
              });
            }}
            onPublish={handlePublishJob}
            onBack={() => goBack(3)}
          />
        )}
      </div>

      {generatingOverlayVisible && (
        <div className="cv-plan-creating-overlay" role="status" aria-live="polite">
          <div className="cv-plan-creating-badge">
            <span className="cv-plan-creating-title">
              {isGeneratingSuccess ? 'Plans Ready ✅' : 'Creating Review Plans'}
            </span>
            <span className="cv-plan-creating-subtitle">
              {isGeneratingSuccess
                ? 'Your draft plans are ready for review.'
                : `Hang tight, we're preparing ${setupState.selectedPersonaIds.length} persona draft${setupState.selectedPersonaIds.length === 1 ? '' : 's'}.`}
            </span>

            {!isGeneratingSuccess && (
              <>
                <span className="cv-plan-creating-stage">{generatingStageLabel}</span>
                <span className="cv-plan-creating-dots" aria-hidden="true">
                  <span className="cv-plan-creating-dot" />
                  <span className="cv-plan-creating-dot" />
                  <span className="cv-plan-creating-dot" />
                </span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const STEP_CONFIG: Array<{
  label: string;
  detail: string;
  icon: LucideIcon;
}> = [
  {
    label: 'Setup',
    detail: 'Configure source, objective, and persona inputs for generation.',
    icon: Settings2,
  },
  {
    label: 'Review Plan',
    detail: 'Validate storyboard and approve persona-level draft directions.',
    icon: FileCheck2,
  },
  {
    label: 'Render',
    detail: 'Track render progress and monitor timeline status in real time.',
    icon: Clapperboard,
  },
  {
    label: 'Publish',
    detail: 'Finalize channel distribution and push content live.',
    icon: Play,
  },
];

const StepIndicator = memo(({ currentStep }: { currentStep: Step }) => {
  return (
    <div className="cv-progress-tracker">
      <div className="cv-progress-track" role="progressbar" aria-valuenow={currentStep} aria-valuemin={1} aria-valuemax={4}>
        {STEP_CONFIG.map((step, idx) => {
          const stepNum = (idx + 1) as Step;
          const isCompleted = currentStep > stepNum;
          const isActive = currentStep === stepNum;
          const Icon = step.icon;

          return (
            <div key={step.label} className="cv-progress-step-wrapper">
              <div
                className={`cv-progress-step ${isActive ? 'cv-progress-step--active' : ''} ${
                  isCompleted ? 'cv-progress-step--completed' : ''
                }`}
              >
                <Icon className="cv-progress-step-icon" />
                <span className="cv-progress-step-label">{stepNum}. {step.label}</span>
              </div>

              {idx < STEP_CONFIG.length - 1 && (
                <div
                  className={`cv-progress-connector ${
                    isCompleted ? 'cv-progress-connector--completed' : ''
                  }`}
                  aria-hidden="true"
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="cv-progress-detail-grid" aria-hidden="true">
        {STEP_CONFIG.map((step, idx) => {
          const stepNum = (idx + 1) as Step;
          const isCurrent = currentStep === stepNum;
          const isCompleted = currentStep > stepNum;
          return (
            <div key={`${step.label}-detail`} className="cv-progress-detail-item">
              <p
                className={`cv-progress-phase ${
                  isCurrent ? 'cv-progress-phase--current' : isCompleted ? 'cv-progress-phase--done' : ''
                }`}
              >
                {isCurrent ? 'Current phase' : isCompleted ? 'Completed' : 'Upcoming'}
              </p>
              <p className="cv-progress-detail-text">{step.detail}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
});

StepIndicator.displayName = 'StepIndicator';

const SYSTEM_PERSONA_USER_ID = '00000000-0000-0000-0000-000000000001';

function isSystemPersona(persona: Persona): boolean {
  return (
    persona.persona_id?.startsWith('global-') ||
    !persona.user_id ||
    persona.user_id === SYSTEM_PERSONA_USER_ID ||
    Boolean(persona.is_preset_catalog)
  );
}

function reviewPersonaToPersona(persona: ReviewEngineSetup['persona_options'][number]): Persona {
  return {
    persona_id: persona.persona_id,
    display_name: persona.display_name,
    avatar_image_url: persona.selection_image_url || persona.image_url || null,
    selection_image_url: persona.selection_image_url || persona.image_url || null,
    status: 'ready',
    video_count: 0,
    language: persona.language || undefined,
    region_label: persona.region_label,
    description: persona.description,
    market_default: persona.market_default,
    tone_default: persona.tone_default,
    is_preset_catalog: Boolean(persona.is_preset_catalog || persona.is_preset),
    user_id: persona.is_preset_catalog || persona.is_preset ? SYSTEM_PERSONA_USER_ID : 'customer',
  };
}

function dedupePersonas(personas: Persona[]): Persona[] {
  const seen = new Set<string>();
  return personas.filter((persona) => {
    if (seen.has(persona.persona_id)) {
      return false;
    }
    seen.add(persona.persona_id);
    return true;
  });
}
