'use client';

import type { CreateVideoModeViewModel, VideoCreationMode } from '@/types/video-planning';

// ---------------------------------------------------------------------------
// Hardcoded mode definitions — Phase 1 spec
// ---------------------------------------------------------------------------

const MODES: CreateVideoModeViewModel[] = [
  {
    id: 'ai_auto',
    title: 'AI tự quay',
    description: 'AI handles the full recording and assembly process automatically.',
    badge: 'Default',
    readiness: 'ready',
  },
  {
    id: 'ai_remote',
    title: 'AI quay từ máy tính',
    description: 'AI operates a remote computer session to record content.',
    badge: 'Coming later',
    readiness: 'coming_later',
    note: 'Requires website login and remote recording handoff.',
  },
  {
    id: 'human_phone',
    title: 'Người quay từ điện thoại',
    description: 'Human captures footage on a phone, then AI assembles the final video.',
    badge: 'Coming later',
    readiness: 'coming_later',
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
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '12px',
      }}
      className="create-video-mode-cards"
    >
      {MODES.map((mode) => {
        const isSelected = selectedMode === mode.id;
        const isDisabled = mode.readiness === 'coming_later';

        return (
          <button
            key={mode.id}
            type="button"
            disabled={isDisabled}
            onClick={() => !isDisabled && onSelect(mode.id)}
            aria-pressed={isSelected}
            aria-disabled={isDisabled}
            style={{
              textAlign: 'left',
              padding: '16px',
              borderRadius: '12px',
              border: isSelected
                ? '2px solid var(--color-border-info, #3b82f6)'
                : '1px solid var(--color-border-tertiary, rgba(255,255,255,0.12))',
              background: isSelected
                ? 'var(--color-surface-info-subtle, rgba(59,130,246,0.08))'
                : 'var(--color-surface-secondary, rgba(255,255,255,0.04))',
              opacity: isDisabled ? 0.6 : 1,
              cursor: isDisabled ? 'not-allowed' : 'pointer',
              transition: 'border-color 0.15s ease, background 0.15s ease, opacity 0.15s ease',
              minHeight: '44px',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            {/* Badge */}
            <span
              style={{
                display: 'inline-flex',
                alignSelf: 'flex-start',
                alignItems: 'center',
                padding: '2px 8px',
                borderRadius: '999px',
                fontSize: '11px',
                fontWeight: 600,
                letterSpacing: '0.02em',
                background:
                  mode.readiness === 'ready'
                    ? 'var(--color-badge-success-bg, rgba(34,197,94,0.15))'
                    : 'var(--color-badge-warning-bg, rgba(234,179,8,0.15))',
                color:
                  mode.readiness === 'ready'
                    ? 'var(--color-badge-success-text, #86efac)'
                    : 'var(--color-badge-warning-text, #fde68a)',
              }}
            >
              {mode.badge}
            </span>

            {/* Title */}
            <span
              style={{
                fontSize: '14px',
                fontWeight: 500,
                color: 'var(--color-on-surface, #f4f4f5)',
                lineHeight: 1.3,
              }}
            >
              {mode.title}
            </span>

            {/* Description */}
            <span
              style={{
                fontSize: '12px',
                color: 'var(--color-on-surface-variant, rgba(244,244,245,0.6))',
                lineHeight: 1.5,
              }}
            >
              {mode.description}
            </span>

            {/* Note */}
            {mode.note && (
              <span
                style={{
                  fontSize: '11px',
                  color: 'var(--color-on-surface-variant, rgba(244,244,245,0.45))',
                  lineHeight: 1.5,
                  marginTop: '2px',
                }}
              >
                {mode.note}
              </span>
            )}
          </button>
        );
      })}

      {/* Responsive styles */}
      <style>{`
        @media (max-width: 640px) {
          .create-video-mode-cards {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
