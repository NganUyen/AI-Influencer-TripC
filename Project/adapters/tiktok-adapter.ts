/**
 * tiktok-adapter.ts
 * Maps persona data → TikTokChannelStatusViewModel demo fixtures.
 *
 * Phase 1: returns hardcoded demo state per persona.
 * Phase 3: replace with real TikTok OAuth channel status fetch.
 */

import type { TikTokChannelStatusViewModel } from '@/types/video-planning';
import type { Persona } from '@/components/customer-dashboard';

/**
 * Returns a demo TikTok channel status for the given persona.
 * Phase 3: replace with real API call to /api/customer/social-accounts/tiktok/:personaId/status
 */
export function toTikTokChannelStatus(
  persona: Persona,
): TikTokChannelStatusViewModel {
  // Cycle through demo states so different personas show different UI states
  const demoIndex = deterministicIndex(persona.persona_id, 3);

  const DEMO_STATES: TikTokChannelStatusViewModel[] = [
    {
      personaId: persona.persona_id,
      activeState: 'active',
      connectionState: 'connected_demo',
      channelHandle: `@${slugify(persona.display_name)}`,
      displayName: persona.display_name,
      lastSyncLabel: 'Just now (demo)',
    },
    {
      personaId: persona.persona_id,
      activeState: 'active',
      connectionState: 'not_connected',
      channelHandle: undefined,
      displayName: undefined,
      lastSyncLabel: undefined,
    },
    {
      personaId: persona.persona_id,
      activeState: 'inactive',
      connectionState: 'not_connected',
      channelHandle: undefined,
      displayName: undefined,
      lastSyncLabel: undefined,
    },
  ];

  return DEMO_STATES[demoIndex];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function deterministicIndex(id: string, mod: number): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) & 0xffffffff;
  }
  return Math.abs(hash) % mod;
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}
