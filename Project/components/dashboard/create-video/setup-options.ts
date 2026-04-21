export interface GestureStyleOption {
  value: string;
  label: string;
  summary: string;
  movementProfile: string;
  demoTitle: string;
  previewMode:
    | 'natural'
    | 'expressive'
    | 'minimal'
    | 'energetic'
    | 'professional'
    | 'casual'
    | 'storytelling'
    | 'calm';
}

export interface ReviewEngineAudioTrack {
  id?: string;
  group?: string;
  profile?: string;
  style?: string;
  mood?: string;
  duration_seconds?: number;
  preview_path?: string;
}

export interface ReviewEngineAudioLibrary {
  bgm?: ReviewEngineAudioTrack[];
  movement?: ReviewEngineAudioTrack[];
}

export const GESTURE_STYLE_OPTIONS: GestureStyleOption[] = [
  {
    value: 'Natural',
    label: 'Natural',
    summary: 'Balanced hand motion with subtle rhythm.',
    movementProfile: 'natural',
    demoTitle: 'Natural Motion Bed',
    previewMode: 'natural',
  },
  {
    value: 'Expressive',
    label: 'Expressive',
    summary: 'Larger hand movement for energetic hooks.',
    movementProfile: 'expressive',
    demoTitle: 'Expressive Motion Bed',
    previewMode: 'expressive',
  },
  {
    value: 'Minimal',
    label: 'Minimal',
    summary: 'Small controlled gestures and low visual noise.',
    movementProfile: 'minimal',
    demoTitle: 'Minimal Motion Bed',
    previewMode: 'minimal',
  },
  {
    value: 'Energetic',
    label: 'Energetic',
    summary: 'Fast upbeat movement for promo-style content.',
    movementProfile: 'energetic',
    demoTitle: 'Energetic Motion Bed',
    previewMode: 'energetic',
  },
  {
    value: 'Professional',
    label: 'Professional',
    summary: 'Confident measured delivery with structured cues.',
    movementProfile: 'professional',
    demoTitle: 'Professional Motion Bed',
    previewMode: 'professional',
  },
  {
    value: 'Casual',
    label: 'Casual',
    summary: 'Relaxed posture with conversational hand flow.',
    movementProfile: 'casual',
    demoTitle: 'Casual Motion Bed',
    previewMode: 'casual',
  },
  {
    value: 'Storytelling',
    label: 'Storytelling',
    summary: 'Directional gesture pattern to support narrative scenes.',
    movementProfile: 'storytelling',
    demoTitle: 'Storytelling Motion Bed',
    previewMode: 'storytelling',
  },
  {
    value: 'Calm',
    label: 'Calm',
    summary: 'Slow steady movement for trust-focused messaging.',
    movementProfile: 'calm',
    demoTitle: 'Calm Motion Bed',
    previewMode: 'calm',
  },
];

export interface MusicMoodOption {
  value: string;
  label: string;
  summary: string;
  bgmProfile: string;
  demoTitle: string;
  demoDurationLabel?: string;
  demoSrc?: string;
  demoRate?: number;
  demoStartSeconds?: number;
}

export const MUSIC_MOOD_OPTIONS: MusicMoodOption[] = [
  {
    value: 'None',
    label: 'None',
    summary: 'Voice-only output with no music bed.',
    bgmProfile: 'product_explainer',
    demoTitle: 'No soundtrack',
  },
  {
    value: 'Upbeat',
    label: 'Upbeat',
    summary: 'Bright rhythm for launch and social promo clips.',
    bgmProfile: 'upbeat_demo',
    demoTitle: 'Upbeat Demo Loop',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/upbeat_demo_loop.mp3',
    demoRate: 1.04,
    demoStartSeconds: 0.3,
  },
  {
    value: 'Corporate',
    label: 'Corporate',
    summary: 'Neutral product explainer tone for business context.',
    bgmProfile: 'product_explainer',
    demoTitle: 'Atlas Corporate Pulse',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/bgm_corporate_atlasaudio.mp3',
    demoRate: 1.0,
    demoStartSeconds: 8,
  },
  {
    value: 'Ambient',
    label: 'Ambient',
    summary: 'Calm pad suitable for review narration.',
    bgmProfile: 'calm_review',
    demoTitle: 'Nastelbom Ambient Flow',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/bgm_ambient_nastelbom.mp3',
    demoRate: 0.95,
    demoStartSeconds: 12,
  },
  {
    value: 'Cinematic',
    label: 'Cinematic',
    summary: 'Dramatic bed for feature storytelling moments.',
    bgmProfile: 'cinematic_rise',
    demoTitle: 'Cinematic Rise',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/bgm_cinematic_rise.mp3',
    demoRate: 1.03,
    demoStartSeconds: 10,
  },
  {
    value: 'Lo-fi',
    label: 'Lo-fi',
    summary: 'Relaxed loop for lifestyle and creator-style delivery.',
    bgmProfile: 'lofi_focus',
    demoTitle: 'Lo-fi Focus',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/bgm_lofi_focus.mp3',
    demoRate: 0.95,
    demoStartSeconds: 16,
  },
  {
    value: 'Electronic',
    label: 'Electronic',
    summary: 'Pulse-driven groove for tech product launches.',
    bgmProfile: 'electro_drive',
    demoTitle: 'Electro Drive',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/bgm_electro_drive.mp3',
    demoRate: 1.05,
    demoStartSeconds: 12,
  },
  {
    value: 'Motivational',
    label: 'Motivational',
    summary: 'Positive rise-and-drop bed for conversion storytelling.',
    bgmProfile: 'motivational_lift',
    demoTitle: 'Eliveta Motivation Rise',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/bgm_motivation_eliveta.mp3',
    demoRate: 1.02,
    demoStartSeconds: 10,
  },
  {
    value: 'Focus',
    label: 'Focus',
    summary: 'Steady mid-tempo beat for product demos and tutorials.',
    bgmProfile: 'focus_loop',
    demoTitle: 'Focus Deep Loop',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/bgm_focus_track.mp3',
    demoRate: 0.97,
    demoStartSeconds: 18,
  },
  {
    value: 'Tropical',
    label: 'Tropical',
    summary: 'Bright summer rhythm for lifestyle creator vibe.',
    bgmProfile: 'tropical_pop',
    demoTitle: 'Tropical Pop Bounce',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/bgm/bgm_tropical_bounce.mp3',
    demoRate: 1.07,
    demoStartSeconds: 8,
  },
];

function normalizeToken(value?: string | null): string {
  return String(value || '').trim().toLowerCase();
}

function resolveTrackPreviewPath(
  tracks: ReviewEngineAudioTrack[],
  profile: string,
): string | undefined {
  const normalizedProfile = normalizeToken(profile);
  if (!normalizedProfile) {
    return undefined;
  }

  const selectedTrack = tracks.find(
    (track) => normalizeToken(track.profile) === normalizedProfile,
  );
  const previewPath = String(selectedTrack?.preview_path || '').trim();
  return previewPath || undefined;
}

export function applyAudioLibraryPreviewOverrides(
  gestureOptions: GestureStyleOption[],
  musicOptions: MusicMoodOption[],
  library?: ReviewEngineAudioLibrary | null,
): {
  gestureOptions: GestureStyleOption[];
  musicOptions: MusicMoodOption[];
} {
  const bgmTracks = Array.isArray(library?.bgm)
    ? library?.bgm ?? []
    : [];

  const nextMusicOptions = musicOptions.map((option) => {
    if (normalizeToken(option.value) === 'none') {
      return {
        ...option,
        demoSrc: undefined,
      };
    }
    const previewFromLibrary = resolveTrackPreviewPath(
      bgmTracks,
      option.bgmProfile,
    );
    if (!previewFromLibrary) {
      return {
        ...option,
        demoSrc: undefined,
      };
    }
    return {
      ...option,
      demoSrc: previewFromLibrary,
    };
  });

  return {
    gestureOptions,
    musicOptions: nextMusicOptions,
  };
}

export function getGestureStyleOption(
  value?: string | null,
  options: GestureStyleOption[] = GESTURE_STYLE_OPTIONS,
): GestureStyleOption | undefined {
  const normalized = normalizeToken(value);
  return options.find(
    (item) => item.value.trim().toLowerCase() === normalized,
  );
}

export function getMusicMoodOption(
  value?: string | null,
  options: MusicMoodOption[] = MUSIC_MOOD_OPTIONS,
): MusicMoodOption | undefined {
  const normalized = normalizeToken(value);
  return options.find(
    (item) => item.value.trim().toLowerCase() === normalized,
  );
}
