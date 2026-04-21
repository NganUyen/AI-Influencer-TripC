import type { ReviewEngineJob } from '@/lib/review-engine';
import type { PersonaPlanCardViewModel } from '@/types/video-planning';

export type CreateVideoStep = 1 | 2 | 3 | 4;

export function shouldShowPlanCreatingOverlay({
  currentStep,
  isGenerating,
  isGeneratingSuccess,
}: {
  currentStep: CreateVideoStep;
  isGenerating: boolean;
  isGeneratingSuccess: boolean;
}): boolean {
  return currentStep === 1 && (isGenerating || isGeneratingSuccess);
}

export function shouldPollReviewJobs({
  currentStep,
  activePlanIdsCount,
  inferredActiveJobsCount,
  isAllTerminal,
  isSubmittingPlans,
  isSavingPlans,
  uploadingPlanIdsCount,
  publishingJobId,
  hasRefreshInFlight,
}: {
  currentStep: CreateVideoStep;
  activePlanIdsCount: number;
  inferredActiveJobsCount: number;
  isAllTerminal: boolean;
  isSubmittingPlans: boolean;
  isSavingPlans: boolean;
  uploadingPlanIdsCount: number;
  publishingJobId: string | null;
  hasRefreshInFlight: boolean;
}): boolean {
  const hasTrackedFlow = activePlanIdsCount > 0 || inferredActiveJobsCount > 0;
  if (!hasTrackedFlow || isAllTerminal) {
    return false;
  }

  if (
    isSubmittingPlans ||
    isSavingPlans ||
    uploadingPlanIdsCount > 0 ||
    Boolean(publishingJobId) ||
    hasRefreshInFlight
  ) {
    return false;
  }

  if (currentStep < 3 && inferredActiveJobsCount === 0) {
    return false;
  }

  return true;
}

type ApproveablePlanCard = Pick<
  PersonaPlanCardViewModel,
  'planId' | 'personaName' | 'reviewDecision'
>;

export async function approvePlanCards(
  cards: ApproveablePlanCard[],
  approvePlan: (card: { planId: string; personaName: string }) => Promise<void>,
): Promise<{ approvedPlanIds: string[]; failedApprovals: string[] }> {
  const approvedCards = cards.filter(
    (card): card is { planId: string; personaName: string; reviewDecision: 'approved' } =>
      card.reviewDecision === 'approved' && Boolean(card.planId),
  );

  const results = await Promise.allSettled(
    approvedCards.map(async (card) => {
      await approvePlan({
        planId: String(card.planId || '').trim(),
        personaName: card.personaName,
      });
      return {
        planId: String(card.planId || '').trim(),
        personaName: card.personaName,
      };
    }),
  );

  const approvedPlanIds: string[] = [];
  const failedApprovals: string[] = [];

  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      approvedPlanIds.push(result.value.planId);
      return;
    }
    failedApprovals.push(approvedCards[index]?.personaName || 'Persona');
  });

  return { approvedPlanIds, failedApprovals };
}

function jobTimestamp(job: ReviewEngineJob): string {
  return (
    job.updated_at ||
    job.approved_at ||
    job.started_at ||
    job.created_at ||
    ''
  );
}

function normalizeStatus(job: Pick<ReviewEngineJob, 'status'>): string {
  return String(job.status || '').trim().toLowerCase();
}

function normalizeFlowValue(value: string | null | undefined): string {
  return String(value || '').trim().toLowerCase();
}

function isTerminalJob(job: ReviewEngineJob): boolean {
  const status = normalizeStatus(job);
  return (
    Boolean(job.production?.ready) ||
    status === 'completed' ||
    status === 'failed' ||
    job.publish?.status === 'published' ||
    job.publish?.status === 'failed'
  );
}

function flowFingerprint(job: ReviewEngineJob): string | null {
  const sourceUrl = normalizeFlowValue(job.source_url);
  const objective = normalizeFlowValue(job.objective);
  if (!sourceUrl && !objective) {
    return null;
  }
  return `${sourceUrl}::${objective}`;
}

export function sortReviewJobsByRecency(
  jobs: ReviewEngineJob[],
): ReviewEngineJob[] {
  return [...jobs].sort((left, right) =>
    jobTimestamp(right).localeCompare(jobTimestamp(left)),
  );
}

export function getJobsForPlanIds(
  jobs: ReviewEngineJob[],
  planIds: string[],
): ReviewEngineJob[] {
  if (planIds.length === 0) {
    return [];
  }
  const activeIds = new Set(
    planIds.map((planId) => String(planId || '').trim()).filter(Boolean),
  );
  return jobs.filter((job) => {
    const planId = String(job.plan_id || '').trim();
    return planId && activeIds.has(planId);
  });
}

export function getPlanIdsFromJobs(jobs: ReviewEngineJob[]): string[] {
  return Array.from(
    new Set(
      jobs
        .map((job) => String(job.plan_id || '').trim())
        .filter(Boolean),
    ),
  );
}

export function hasBackendExecution(job: ReviewEngineJob): boolean {
  const status = normalizeStatus(job);
  return (
    Boolean(job.workflow_id) ||
    Boolean(job.production?.ready) ||
    Boolean(job.publish?.requested) ||
    job.publish?.status === 'published' ||
    status === 'approved' ||
    status === 'in_progress' ||
    status === 'running' ||
    status === 'completed' ||
    status === 'failed'
  );
}

export function inferBackendFlowJobs(
  jobs: ReviewEngineJob[],
): ReviewEngineJob[] {
  const candidates = sortReviewJobsByRecency(jobs).filter(
    (job) => hasBackendExecution(job) && !isTerminalJob(job),
  );
  if (candidates.length === 0) {
    return [];
  }

  const seed = candidates[0];
  const seedFingerprint = flowFingerprint(seed);
  if (!seedFingerprint) {
    return [seed];
  }

  return candidates.filter((job) => flowFingerprint(job) === seedFingerprint);
}

export function deriveStepFromJobs(jobs: ReviewEngineJob[]): CreateVideoStep {
  if (jobs.length === 0) {
    return 1;
  }

  const hasWorkflowOrApprovedState = jobs.some((job) => hasBackendExecution(job));
  if (!hasWorkflowOrApprovedState) {
    return 2;
  }

  // Step 4 (publish) is entered explicitly by user action from render step.
  return 3;
}
