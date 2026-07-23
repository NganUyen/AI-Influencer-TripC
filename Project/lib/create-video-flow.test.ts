import {
  approvePlanCards,
  deriveStepFromJobs,
  getJobsForPlanIds,
  getPlanIdsFromJobs,
  inferBackendFlowJobs,
  shouldPollReviewJobs,
  shouldShowPlanCreatingOverlay,
} from '@/lib/create-video-flow';
import type { ReviewEngineJob } from '@/lib/review-engine';

function makeJob(overrides: Partial<ReviewEngineJob> = {}): ReviewEngineJob {
  return {
    job_id: overrides.job_id || 'job-1',
    plan_id: overrides.plan_id || 'plan-1',
    status: overrides.status || 'generated',
    progress: overrides.progress || 0,
    activity_feed: overrides.activity_feed || [],
    persona: overrides.persona || {},
    content: overrides.content || {},
    production: overrides.production || {},
    publish: overrides.publish || {},
    ...overrides,
  };
}

describe('create-video flow helpers', () => {
  it('falls back to the latest active backend flow when active plan ids are missing', () => {
    const jobs = [
      makeJob({
        job_id: 'job-running-a',
        plan_id: 'plan-running-a',
        status: 'running',
        workflow_id: 'wf-1',
        source_url: 'https://example.com',
        objective: 'Review app',
        updated_at: '2026-04-20T10:00:00Z',
      }),
      makeJob({
        job_id: 'job-running-b',
        plan_id: 'plan-running-b',
        status: 'completed',
        production: { ready: true },
        source_url: 'https://example.com',
        objective: 'Review app',
        updated_at: '2026-04-20T09:59:00Z',
      }),
      makeJob({
        job_id: 'job-old',
        plan_id: 'plan-old',
        status: 'completed',
        production: { ready: true },
        source_url: 'https://other.example.com',
        objective: 'Older flow',
        updated_at: '2026-04-19T12:00:00Z',
      }),
    ];

    const inferred = inferBackendFlowJobs(jobs);

    expect(inferred.map((job) => job.plan_id)).toEqual(['plan-running-a']);
    expect(getPlanIdsFromJobs(inferred)).toEqual(['plan-running-a']);
    expect(deriveStepFromJobs(inferred)).toBe(3);
  });

  it('keeps explicit active plan filtering when plan ids exist', () => {
    const jobs = [
      makeJob({
        job_id: 'job-1',
        plan_id: 'plan-1',
        status: 'generated',
      }),
      makeJob({
        job_id: 'job-2',
        plan_id: 'plan-2',
        status: 'running',
        workflow_id: 'wf-2',
      }),
    ];

    expect(getJobsForPlanIds(jobs, ['plan-1']).map((job) => job.plan_id)).toEqual([
      'plan-1',
    ]);
    expect(deriveStepFromJobs(getJobsForPlanIds(jobs, ['plan-1']))).toBe(2);
  });

  it('keeps completed backend flows on render until publish is selected', () => {
    const completedJobs = [
      makeJob({
        job_id: 'job-1',
        plan_id: 'plan-1',
        status: 'completed',
        production: { ready: true, publish_enabled: true },
      }),
      makeJob({
        job_id: 'job-2',
        plan_id: 'plan-2',
        status: 'failed',
      }),
    ];

    expect(deriveStepFromJobs(completedJobs)).toBe(3);
  });

  it('hides plan-creating overlay immediately after review step is visible', () => {
    expect(
      shouldShowPlanCreatingOverlay({
        currentStep: 2,
        isGenerating: true,
        isGeneratingSuccess: false,
      }),
    ).toBe(false);

    expect(
      shouldShowPlanCreatingOverlay({
        currentStep: 2,
        isGenerating: false,
        isGeneratingSuccess: true,
      }),
    ).toBe(false);

    expect(
      shouldShowPlanCreatingOverlay({
        currentStep: 1,
        isGenerating: true,
        isGeneratingSuccess: false,
      }),
    ).toBe(true);
  });

  it('pauses polling while approval or refresh work is active', () => {
    expect(
      shouldPollReviewJobs({
        currentStep: 2,
        activePlanIdsCount: 2,
        inferredActiveJobsCount: 2,
        isAllTerminal: false,
        isSubmittingPlans: true,
        isSavingPlans: false,
        uploadingPlanIdsCount: 0,
        publishingJobId: null,
        hasRefreshInFlight: false,
      }),
    ).toBe(false);

    expect(
      shouldPollReviewJobs({
        currentStep: 3,
        activePlanIdsCount: 2,
        inferredActiveJobsCount: 2,
        isAllTerminal: false,
        isSubmittingPlans: false,
        isSavingPlans: false,
        uploadingPlanIdsCount: 0,
        publishingJobId: null,
        hasRefreshInFlight: true,
      }),
    ).toBe(false);

    expect(
      shouldPollReviewJobs({
        currentStep: 3,
        activePlanIdsCount: 2,
        inferredActiveJobsCount: 2,
        isAllTerminal: false,
        isSubmittingPlans: false,
        isSavingPlans: false,
        uploadingPlanIdsCount: 0,
        publishingJobId: null,
        hasRefreshInFlight: false,
      }),
    ).toBe(true);
  });

  it('approves selected plan cards concurrently and preserves failures', async () => {
    let activeApprovals = 0;
    let maxActiveApprovals = 0;

    const result = await approvePlanCards(
      [
        {
          planId: 'plan-1',
          personaName: 'Ava',
          reviewDecision: 'approved',
        },
        {
          planId: 'plan-2',
          personaName: 'Natasha',
          reviewDecision: 'approved',
        },
        {
          planId: 'plan-3',
          personaName: 'Mika',
          reviewDecision: 'pending',
        },
      ],
      async ({ planId }) => {
        activeApprovals += 1;
        maxActiveApprovals = Math.max(maxActiveApprovals, activeApprovals);
        await new Promise((resolve) => setTimeout(resolve, 10));
        activeApprovals -= 1;
        if (planId === 'plan-2') {
          throw new Error('approve failed');
        }
      },
    );

    expect(maxActiveApprovals).toBeGreaterThan(1);
    expect(result.approvedPlanIds).toEqual(['plan-1']);
    expect(result.failedApprovals).toEqual(['Natasha']);
  });
});
