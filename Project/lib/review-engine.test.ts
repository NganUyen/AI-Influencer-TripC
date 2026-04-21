import {
  getReviewJobActiveTikTokChannels,
  getReviewJobChannelLabel,
  getReviewJobPreferredTikTokChannelId,
  type ReviewEngineJob,
} from '@/lib/review-engine';

function makeJob(overrides: Partial<ReviewEngineJob> = {}): ReviewEngineJob {
  return {
    job_id: overrides.job_id || 'job-1',
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

describe('review-engine channel helpers', () => {
  it('returns only active TikTok channels when status flags are present', () => {
    const job = makeJob({
      persona: {
        tiktok_integration: {
          active_channels: 2,
          channels: [
            { id: 'social-1', display_name: 'Main', status: 'active' },
            { id: 'social-2', display_name: 'Backup', status: 'inactive' },
            { id: 'social-3', display_name: 'Alt', status: 'connected' },
          ],
        },
      },
    });

    expect(getReviewJobActiveTikTokChannels(job).map((item) => item.id)).toEqual([
      'social-1',
      'social-3',
    ]);
  });

  it('prefers persisted publish channel id over inferred default', () => {
    const job = makeJob({
      persona: {
        tiktok_integration: {
          active_channels: 1,
          channels: [{ id: 'social-1', display_name: 'Main', status: 'active' }],
        },
      },
      publish: {
        social_account_id: 'social-9',
      },
    });

    expect(getReviewJobPreferredTikTokChannelId(job)).toBe('social-9');
  });

  it('falls back to the single active TikTok channel id', () => {
    const job = makeJob({
      persona: {
        tiktok_integration: {
          active_channels: 1,
          channels: [{ id: 'social-1', display_name: 'Main', status: 'active' }],
        },
      },
    });

    expect(getReviewJobPreferredTikTokChannelId(job)).toBe('social-1');
    expect(getReviewJobChannelLabel(getReviewJobActiveTikTokChannels(job)[0])).toBe(
      'Main',
    );
  });
});
