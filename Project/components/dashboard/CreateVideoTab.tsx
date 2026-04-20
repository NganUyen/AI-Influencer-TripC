'use client';

import '@/app/create-video.css';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Clapperboard, FileCheck2, Play, Settings2, type LucideIcon } from 'lucide-react';
import { toast } from 'react-hot-toast';
import type { Persona } from '@/components/customer-dashboard';
import type {
  ReviewEngineJob,
  ReviewEngineJobResponse,
  ReviewEngineSetup,
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

function formatScenesForEditor(scenes: ScenePreviewItem[]): string {
  return scenes
    .map((scene) =>
      `${scene.description}${scene.durationSeconds !== undefined ? ` | ${scene.durationSeconds}` : ''}`,
    )
    .join('\n');
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
      ? masterSource.scenes_data.map((scene, index) => ({
          index: index + 1,
          description: String(
            scene?.description ||
              scene?.caption ||
              scene?.scene_description ||
              scene?.voiceover ||
              scene?.script ||
              scene?.text ||
              `Scene ${index + 1}`,
          ).trim(),
          durationSeconds: Number.isFinite(
            Number(scene?.durationSeconds ?? scene?.duration_seconds ?? scene?.duration),
          )
            ? Number(scene?.durationSeconds ?? scene?.duration_seconds ?? scene?.duration)
            : undefined,
        }))
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
    ? firstJob.script?.scenes.map((scene, index) => ({
        index: index + 1,
        description: String(
          scene?.description ||
            scene?.caption ||
            scene?.scene_description ||
            scene?.voiceover ||
            scene?.script ||
            scene?.text ||
            `Scene ${index + 1}`,
        ).trim(),
        durationSeconds: Number.isFinite(
          Number(scene?.durationSeconds ?? scene?.duration_seconds ?? scene?.duration),
        )
          ? Number(scene?.durationSeconds ?? scene?.duration_seconds ?? scene?.duration)
          : undefined,
      }))
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
  onBack,
}: {
  jobs: ReviewEngineJob[];
  publishingJobId: string | null;
  onPublish: (jobId: string) => void;
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
                  <div style={{ display: 'grid', gap: 4 }}>
                    <strong>{job.persona?.display_name || job.persona_id || 'Persona'}</strong>
                    <span className="cv-cta-disabled-reason">
                      {job.page_title || job.objective || 'Ready for publish'}
                    </span>
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
                      disabled={alreadyPublished || publishingJobId === job.job_id}
                      onClick={() => onPublish(job.job_id)}
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  const persistActiveFlow = useCallback((planIds: string[], step: Step) => {
    if (typeof window === 'undefined') {
      return;
    }
    if (planIds.length === 0) {
      window.localStorage.removeItem(ACTIVE_FLOW_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(
      ACTIVE_FLOW_STORAGE_KEY,
      JSON.stringify({ planIds, step }),
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
      const payload = JSON.parse(raw) as { planIds?: string[]; step?: Step };
      const nextPlanIds = Array.isArray(payload.planIds)
        ? payload.planIds.filter(Boolean)
        : [];
      if (nextPlanIds.length > 0) {
        setActivePlanIds(nextPlanIds);
        if (payload.step && payload.step >= 1 && payload.step <= 4) {
          setCurrentStep(payload.step);
        }
      }
    } catch {
      window.localStorage.removeItem(ACTIVE_FLOW_STORAGE_KEY);
    }
  }, []);

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

  const shouldPollJobs = activePlanIds.length > 0 || inferredActiveJobs.length > 0;

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
      const currentByPlanId = new Map(
        current.map((card) => [card.planId || card.jobId, card]),
      );
      return toPersonaPlanCards(activeJobs).map((card) => {
        const existing = currentByPlanId.get(card.planId || card.jobId);
        return existing
          ? {
              ...card,
              reviewDecision: existing.reviewDecision,
            }
          : card;
      });
    });
    setProgressItems(toRenderProgressItems(activeJobs));
    if (!sharedContractDirty) {
      setSharedContractDraft(buildSharedContractDraft(activeJobs));
    }

    const derivedStep = deriveStepFromJobs(activeJobs);
    setCurrentStep((current) => {
      if (derivedStep > current) {
        return derivedStep;
      }
      return current;
    });
  }, [activeJobs, sharedContractDirty]);

  useEffect(() => {
    persistActiveFlow(activePlanIds, currentStep);
  }, [activePlanIds, currentStep, persistActiveFlow]);

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

    setErrorMessage(null);
    setIsGenerating(true);
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
      setCurrentStep(2);
      if (result.warnings?.[0]?.message) {
        toast(`Review jobs created with a warning: ${result.warnings[0].message}`);
      }
      await Promise.resolve(onRefresh?.());
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to create review jobs';
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setIsGenerating(false);
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

  const handlePublishJob = useCallback(async (jobId: string) => {
    setErrorMessage(null);
    setPublishingJobId(jobId);
    try {
      const updatedJob = await customerApiRequest<ReviewEngineJob>(
        `/api/customer/review-engine/jobs/${jobId}/publish`,
        {
          method: 'POST',
          body: JSON.stringify({}),
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

  return (
    <div className="cv-container">
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
            isSubmitting={isGenerating}
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
            onPublish={handlePublishJob}
            onBack={() => goBack(3)}
          />
        )}
      </div>

      {isGenerating && (
        <div className="cv-cta-disabled-reason" style={{ marginTop: 16 }}>
          Creating backend plans…
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

function StepIndicator({ currentStep }: { currentStep: Step }) {
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
}

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
