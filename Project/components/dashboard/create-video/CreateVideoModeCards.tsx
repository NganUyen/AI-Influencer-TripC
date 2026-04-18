'use client';

import type { CreateVideoModeViewModel, VideoCreationMode } from '@/types/video-planning';

// ---------------------------------------------------------------------------
// Hardcoded mode definitions — Phase 1 spec
// ---------------------------------------------------------------------------

const MODES: CreateVideoModeViewModel[] = [
  {
    id: 'ai_auto',
    title: 'AI Auto-Record',
    description: 'AI handles the full recording and assembly process automatically.',
    badge: 'Default',
    readiness: 'ready',
  },
  {
    id: 'ai_remote',
    title: 'AI Remote Recording',
    description: 'AI operates a remote computer session to record content.',
    badge: 'Coming later',
    readiness: 'coming_later',
    note: 'Requires website login and remote recording handoff.',
  },
  {
    id: 'human_phone',
    title: 'Human Phone Recording',
    description: 'Human captures footage on a phone, then AI assembles the final video.',
    badge: 'Ready',
    readiness: 'ready',
    note: 'Human-captured footage from phone, then AI assembles the final video.',
  },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CreateVideoModeCardsProps {
  selectedMode: VideoCreationMode;
  onSelect: (mode: VideoCreationMode) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVideoModeCards({ selectedMode, onSelect }: CreateVideoModeCardsProps) {
  return (
    <div className="cv-mode-cards">
      {MODES.map((mode) => {
        const isSelected = selectedMode === mode.id;
        const isDisabled = mode.readiness === 'coming_later';

        const cardClass = [
          'cv-mode-card',
          isSelected ? 'cv-mode-card--selected' : '',
          isDisabled ? 'cv-mode-card--disabled' : '',
        ]
          .filter(Boolean)
          .join(' ');

        return (
          <button
            key={mode.id}
            type="button"
            disabled={isDisabled}
            onClick={() => !isDisabled && onSelect(mode.id)}
            aria-pressed={isSelected}
            aria-disabled={isDisabled}
            className={cardClass}
          >
            {/* Badge */}
            <span
              className={
                mode.readiness === 'ready'
                  ? 'cv-mode-badge cv-mode-badge--ready'
                  : 'cv-mode-badge cv-mode-badge--coming'
              }
            >
              {mode.badge}
            </span>

            {/* Title */}
            <span className="cv-mode-title">{mode.title}</span>

            {/* Description */}
            <span className="cv-mode-desc">{mode.description}</span>

            {/* Note */}
            {mode.note && <span className="cv-mode-note">{mode.note}</span>}
          </button>
        );
      })}
    </div>
  );
}
