/**
 * create-video-adapter.ts
 * Maps raw API data (or demo fixtures) into PersonaPlanCardViewModel[] and
 * CreateVideoProgressViewModel[].
 *
 * Phase 1: returns demo fixtures.
 * Phase 3: replace function bodies with real API response mapping — component
 * interfaces stay the same.
 */

import type {
  PersonaPlanCardViewModel,
  CreateVideoProgressViewModel,
  RenderTimelineEvent,
} from '@/types/video-planning';

// ---------------------------------------------------------------------------
// Plan cards (Step 2)
// ---------------------------------------------------------------------------

/**
 * Phase 1: returns demo fixtures regardless of rawJobs.
 * Phase 3: replace with real mapping from /api/customer/review-engine/jobs.
 */
export function toPersonaPlanCards(
  selectedPersonaIds: string[],
  personaMap: Record<string, { name: string; avatarUrl?: string }>,
): PersonaPlanCardViewModel[] {
  if (selectedPersonaIds.length === 0) return [];

  return selectedPersonaIds.map((id, index) => {
    const persona = personaMap[id];
    return {
      personaId: id,
      personaName: persona?.name ?? `Persona ${index + 1}`,
      personaAvatarUrl: persona?.avatarUrl,
      scriptPreview:
        'Bạn có biết rằng chỉ với 30 giây mỗi ngày, bạn có thể thay đổi hoàn toàn thói quen của mình? Hôm nay chúng ta sẽ khám phá những bí quyết đã giúp hàng nghìn người đạt được mục tiêu của họ...',
      scenes: [
        { index: 1, description: 'Hook mở đầu — câu hỏi kích thích sự tò mò', durationSeconds: 5 },
        { index: 2, description: 'Trình bày vấn đề chính', durationSeconds: 10 },
        { index: 3, description: 'Giới thiệu giải pháp / sản phẩm', durationSeconds: 12 },
        { index: 4, description: 'Call to action', durationSeconds: 4 },
      ],
      status: 'demo',
    };
  });
}

// ---------------------------------------------------------------------------
// Render progress (Step 3)
// ---------------------------------------------------------------------------

function buildInitialProgress(
  card: PersonaPlanCardViewModel,
): CreateVideoProgressViewModel {
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return {
    personaId: card.personaId,
    personaName: card.personaName,
    personaAvatarUrl: card.personaAvatarUrl,
    status: 'queued',
    progressPercent: 0,
    outputPreviewUrl: undefined,
    timelineEvents: [
      { label: 'Plan submitted', timestamp: now, status: 'done' },
      { label: 'Render queued', timestamp: now, status: 'done' },
      { label: 'Processing...', status: 'active' },
      { label: 'Output ready', status: 'pending' },
    ],
  };
}

/**
 * Simulates render progress via setTimeout chain.
 * onUpdate is called with the new list on each state change.
 * Returns a cleanup function to cancel pending timeouts.
 *
 * Phase 3: replace with real polling of /api/customer/render/jobs.
 */
export function simulateRenderProgress(
  approvedCards: PersonaPlanCardViewModel[],
  onUpdate: (items: CreateVideoProgressViewModel[]) => void,
): () => void {
  const timeouts: ReturnType<typeof setTimeout>[] = [];
  let cancelled = false;

  const items: CreateVideoProgressViewModel[] = approvedCards.map(buildInitialProgress);
  onUpdate([...items]);

  approvedCards.forEach((card, idx) => {
    // After 1.5s → in_progress
    const t1 = setTimeout(() => {
      if (cancelled) return;
      items[idx] = {
        ...items[idx],
        status: 'in_progress',
        progressPercent: 40,
        timelineEvents: items[idx].timelineEvents.map((e, i) => {
          if (i === 2) return { ...e, status: 'active' };
          return e;
        }) as RenderTimelineEvent[],
      };
      onUpdate([...items]);
    }, 1500 + idx * 800);

    // After 3.5s → completed
    const t2 = setTimeout(() => {
      if (cancelled) return;
      const completedAt = new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      });
      items[idx] = {
        ...items[idx],
        status: 'pending_backend',
        progressPercent: 100,
        timelineEvents: [
          { label: 'Plan submitted', timestamp: items[idx].timelineEvents[0].timestamp, status: 'done' },
          { label: 'Render queued', timestamp: items[idx].timelineEvents[1].timestamp, status: 'done' },
          { label: 'Processing...', timestamp: completedAt, status: 'done' },
          { label: 'Output ready', timestamp: completedAt, status: 'done' },
        ],
      };
      onUpdate([...items]);
    }, 3500 + idx * 800);

    timeouts.push(t1, t2);
  });

  return () => {
    cancelled = true;
    timeouts.forEach(clearTimeout);
  };
}
