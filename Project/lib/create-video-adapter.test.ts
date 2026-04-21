import { toRenderProgressItems } from '@/adapters/create-video-adapter';
import type { ReviewEngineJob } from '@/lib/review-engine';

function makeJob(overrides: Partial<ReviewEngineJob> = {}): ReviewEngineJob {
  return {
    job_id: overrides.job_id || 'job-1',
    plan_id: overrides.plan_id || 'plan-1',
    status: overrides.status || 'failed',
    progress: overrides.progress || 70,
    activity_feed: overrides.activity_feed || [],
    persona: overrides.persona || {
      persona_id: 'persona-1',
      display_name: 'Ava',
    },
    content: overrides.content || {},
    production: overrides.production || {},
    publish: overrides.publish || {},
    ...overrides,
  };
}

describe('create-video adapter', () => {
  it('prefers structured top-half failure message for render cards', () => {
    const [item] = toRenderProgressItems([
      makeJob({
        error_detail: 'net::ERR_HTTP_RESPONSE_CODE_FAILURE at https://aisoeasy.co/',
        failure_details: {
          stage: 'top_half',
          code: 'http_response_failure',
          message:
            'Top-half recording failed because the website returned an HTTP response that browser automation could not use.',
          scene_id: '3',
          source_url: 'https://aisoeasy.co/',
          domain: 'aisoeasy.co',
          retryable: false,
          recommended_action:
            'Verify the site is reachable from automated browsers and try again.',
        },
      }),
    ]);

    expect(item.status).toBe('failed');
    expect(item.statusMessage).toBe(
      'Top-half recording failed because the website returned an HTTP response that browser automation could not use.',
    );
  });
});
