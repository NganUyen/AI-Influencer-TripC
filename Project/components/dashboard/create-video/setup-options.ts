export interface GestureStyleOption {
  value: string;
  label: string;
  summary: string;
  movementProfile: string;
  demoTitle: string;
  demoDurationLabel?: string;
  demoSrc?: string;
  demoRate?: number;
  demoStartSeconds?: number;
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

export const GESTURE_STYLE_OPTIONS: GestureStyleOption[] = [
  {
    value: 'Natural',
    label: 'Natural',
    summary: 'Balanced hand motion with subtle rhythm.',
    movementProfile: 'natural',
    demoTitle: 'Natural Motion Bed',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/movement/movement_natural.mp3',
    demoRate: 0.94,
    demoStartSeconds: 0.4,
    previewMode: 'natural',
  },
  {
    value: 'Expressive',
    label: 'Expressive',
    summary: 'Larger hand movement for energetic hooks.',
    movementProfile: 'expressive',
    demoTitle: 'Expressive Motion Bed',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/movement/movement_expressive.mp3',
    demoRate: 1.06,
    demoStartSeconds: 14,
    previewMode: 'expressive',
  },
  {
    value: 'Minimal',
    label: 'Minimal',
    summary: 'Small controlled gestures and low visual noise.',
    movementProfile: 'minimal',
    demoTitle: 'Minimal Motion Bed',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/movement/movement_minimal.mp3',
    demoRate: 0.9,
    demoStartSeconds: 22,
    previewMode: 'minimal',
  },
  {
    value: 'Energetic',
    label: 'Energetic',
    summary: 'Fast upbeat movement for promo-style content.',
    movementProfile: 'energetic',
    demoTitle: 'Energetic Motion Bed',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/movement/movement_energetic.mp3',
    demoRate: 1.1,
    demoStartSeconds: 10,
    previewMode: 'energetic',
  },
  {
    value: 'Professional',
    label: 'Professional',
    summary: 'Confident measured delivery with structured cues.',
    movementProfile: 'professional',
    demoTitle: 'Professional Motion Bed',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/movement/movement_professional.mp3',
    demoRate: 0.97,
    demoStartSeconds: 34,
    previewMode: 'professional',
  },
  {
    value: 'Casual',
    label: 'Casual',
    summary: 'Relaxed posture with conversational hand flow.',
    movementProfile: 'casual',
    demoTitle: 'Casual Motion Bed',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/movement/movement_casual.mp3',
    demoRate: 1.02,
    demoStartSeconds: 0.2,
    previewMode: 'casual',
  },
  {
    value: 'Storytelling',
    label: 'Storytelling',
    summary: 'Directional gesture pattern to support narrative scenes.',
    movementProfile: 'storytelling',
    demoTitle: 'Storytelling Motion Bed',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/movement/movement_storytelling.mp3',
    demoRate: 1.0,
    demoStartSeconds: 16,
    previewMode: 'storytelling',
  },
  {
    value: 'Calm',
    label: 'Calm',
    summary: 'Slow steady movement for trust-focused messaging.',
    movementProfile: 'calm',
    demoTitle: 'Calm Motion Bed',
    demoDurationLabel: 'Live duration',
    demoSrc: '/create-video-demos/movement/movement_calm.mp3',
    demoRate: 0.88,
    demoStartSeconds: 0.6,
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

export function getGestureStyleOption(
  value?: string | null,
): GestureStyleOption | undefined {
  const normalized = String(value || '').trim().toLowerCase();
  return GESTURE_STYLE_OPTIONS.find(
    (item) => item.value.trim().toLowerCase() === normalized,
  );
}

export function getMusicMoodOption(
  value?: string | null,
): MusicMoodOption | undefined {
  const normalized = String(value || '').trim().toLowerCase();
  return MUSIC_MOOD_OPTIONS.find(
    (item) => item.value.trim().toLowerCase() === normalized,
  );
}
