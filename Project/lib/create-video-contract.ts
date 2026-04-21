import type { ScenePreviewItem } from '@/types/video-planning';

function getSceneDescription(scene: unknown, index: number): string {
  if (!scene || typeof scene !== 'object') {
    return `Scene ${index + 1}`;
  }

  const payload = scene as Record<string, unknown>;
  return String(
    payload.description ||
      payload.caption ||
      payload.scene_description ||
      payload.voiceover ||
      payload.script ||
      payload.text ||
      `Scene ${index + 1}`,
  ).trim();
}

export function getSceneDurationSeconds(scene: unknown): number | undefined {
  if (!scene || typeof scene !== 'object') {
    return undefined;
  }

  const payload = scene as Record<string, unknown>;
  const directDuration = Number(
    payload.durationSeconds ?? payload.duration_seconds ?? payload.duration,
  );
  if (Number.isFinite(directDuration) && directDuration > 0) {
    return directDuration;
  }

  const start = Number(payload.timestamp_start ?? payload.start_time ?? payload.start);
  const end = Number(payload.timestamp_end ?? payload.end_time ?? payload.end);
  if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
    return end - start;
  }

  return undefined;
}

export function toScenePreviewItem(scene: unknown, index: number): ScenePreviewItem {
  return {
    index: index + 1,
    description: getSceneDescription(scene, index),
    durationSeconds: getSceneDurationSeconds(scene),
  };
}

export function formatScenesForEditor(scenes: ScenePreviewItem[]): string {
  return scenes
    .map((scene) =>
      `${scene.description}${scene.durationSeconds !== undefined ? ` | ${scene.durationSeconds}` : ''}`,
    )
    .join('\n');
}

export function buildSharedContractScenesText(scenes: unknown[]): string {
  return formatScenesForEditor(scenes.map((scene, index) => toScenePreviewItem(scene, index)));
}
