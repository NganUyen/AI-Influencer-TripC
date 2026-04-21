import { buildSharedContractScenesText, getSceneDurationSeconds } from '@/lib/create-video-contract';

describe('create-video contract helpers', () => {
  it('derives scene duration from timestamp_start and timestamp_end', () => {
    expect(
      getSceneDurationSeconds({
        timestamp_start: 5,
        timestamp_end: 12,
      }),
    ).toBe(7);
  });

  it('builds shared contract scene rows using timestamp-derived durations', () => {
    expect(
      buildSharedContractScenesText([
        {
          caption: 'Hook',
          timestamp_start: 0,
          timestamp_end: 5,
        },
        {
          caption: 'Feature',
          timestamp_start: 5,
          timestamp_end: 12,
        },
      ]),
    ).toBe('Hook | 5\nFeature | 7');
  });
});
