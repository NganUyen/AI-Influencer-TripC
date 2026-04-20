import type { ReviewEngineJob } from '@/lib/review-engine';

export type CreateVideoStep = 1 | 2 | 3 | 4;

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
  const candidates = sortReviewJobsByRecency(jobs).filter(hasBackendExecution);
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

  const allSettled = jobs.every((job) => {
    const status = normalizeStatus(job);
    return (
      Boolean(job.production?.ready) ||
      status === 'completed' ||
      status === 'failed' ||
      job.publish?.status === 'published'
    );
  });

  return allSettled ? 4 : 3;
}
