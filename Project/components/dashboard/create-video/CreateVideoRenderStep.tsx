'use client';

import type { CreateVideoProgressViewModel, RenderStatus } from '@/types/video-planning';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CreateVideoRenderStepProps {
  progressItems: CreateVideoProgressViewModel[];
  onBack: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVideoRenderStep({ progressItems, onBack }: CreateVideoRenderStepProps) {
  if (progressItems.length === 0) {
    return (
      <div
        style={{
          padding: '48px 24px',
          textAlign: 'center',
          borderRadius: '16px',
          border: '1px dashed var(--color-border-tertiary, rgba(255,255,255,0.1))',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <p
          style={{
            fontSize: '14px',
            color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
            margin: 0,
          }}
        >
          No approved plans yet. Go back and approve at least one persona plan.
        </p>
        <button type="button" onClick={onBack} style={backBtnStyle}>
          ← Go back
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button type="button" onClick={onBack} style={backBtnStyle}>
          ← Back
        </button>
        <div>
          <h2
            style={{
              fontSize: '18px',
              fontWeight: 700,
              color: 'var(--color-on-surface, #f4f4f5)',
              margin: '0 0 4px',
            }}
          >
            Rendering
          </h2>
          <p
            style={{
              fontSize: '13px',
              color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
              margin: 0,
            }}
          >
            Video production is being simulated. Real render progress will appear here in Phase 3.
          </p>
        </div>
      </div>

      {/* Progress cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {progressItems.map((item) => (
          <RenderProgressCard key={item.personaId} item={item} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RenderProgressCard
// ---------------------------------------------------------------------------

function RenderProgressCard({ item }: { item: CreateVideoProgressViewModel }) {
  const isDone = item.status === 'completed' || item.status === 'pending_backend';

  return (
    <div
      style={{
        borderRadius: '16px',
        border: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.08))',
        background: 'var(--color-surface-secondary, rgba(255,255,255,0.03))',
        overflow: 'hidden',
      }}
    >
      {/* Card header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '16px 20px',
          borderBottom: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.06))',
        }}
      >
        <PersonaAvatar name={item.personaName} avatarUrl={item.personaAvatarUrl} size={36} />
        <span
          style={{
            flex: 1,
            fontSize: '15px',
            fontWeight: 600,
            color: 'var(--color-on-surface, #f4f4f5)',
          }}
        >
          {item.personaName}
        </span>
        <RenderStatusBadge status={item.status} />
      </div>

      {/* Card body */}
      <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Timeline */}
        <div>
          <p
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              margin: '0 0 12px',
            }}
          >
            Timeline
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {item.timelineEvents.map((event, idx) => (
              <TimelineDot key={idx} event={event} />
            ))}
          </div>
        </div>

        {/* Progress bar */}
        {item.progressPercent !== undefined && (
          <div
            style={{
              height: '4px',
              borderRadius: '999px',
              background: 'var(--color-surface-tertiary, rgba(255,255,255,0.08))',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${item.progressPercent}%`,
                background: isDone
                  ? 'var(--color-success, #86efac)'
                  : 'var(--color-primary, #6366f1)',
                borderRadius: '999px',
                transition: 'width 0.6s ease',
              }}
            />
          </div>
        )}

        {/* Output preview */}
        <div>
          <p
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              margin: '0 0 8px',
            }}
          >
            Output
          </p>
          {item.outputPreviewUrl ? (
            <img
              src={item.outputPreviewUrl}
              alt="Video preview"
              style={{
                width: '100%',
                maxHeight: '200px',
                objectFit: 'cover',
                borderRadius: '10px',
              }}
            />
          ) : (
            <div
              style={{
                padding: '20px',
                borderRadius: '10px',
                border: '1px dashed var(--color-border-tertiary, rgba(255,255,255,0.1))',
                textAlign: 'center',
                fontSize: '13px',
                color: 'var(--color-on-surface-variant, rgba(244,244,245,0.35))',
              }}
            >
              Preview available after render
            </div>
          )}
        </div>

        {/* Final state label */}
        {isDone && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: '10px',
              background: 'rgba(99,102,241,0.08)',
              border: '1px solid rgba(99,102,241,0.2)',
              fontSize: '13px',
              color: 'var(--color-on-surface-variant, rgba(244,244,245,0.7))',
              lineHeight: 1.5,
            }}
          >
            <strong style={{ color: 'var(--color-primary, #818cf8)', marginRight: '6px' }}>
              Ready for backend integration.
            </strong>
            Real render progress and output will be available once the Phase 3 backend is connected.
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TimelineDot
// ---------------------------------------------------------------------------

function TimelineDot({
  event,
}: {
  event: { label: string; timestamp?: string; status: 'done' | 'active' | 'pending' };
}) {
  const dotStyle: React.CSSProperties = {
    width: 10,
    height: 10,
    borderRadius: '50%',
    flexShrink: 0,
    marginTop: 3,
    position: 'relative',
    ...(event.status === 'done'
      ? {
          background: 'var(--color-success, #86efac)',
        }
      : event.status === 'active'
        ? {
            background: 'var(--color-primary, #6366f1)',
            boxShadow: '0 0 0 3px rgba(99,102,241,0.25)',
            animation: 'cv-pulse 1.2s ease-in-out infinite',
          }
        : {
            background: 'transparent',
            border: '2px solid var(--color-border-tertiary, rgba(255,255,255,0.2))',
          }),
  };

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
      <span style={dotStyle} aria-hidden="true" />
      <div style={{ flex: 1, display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
        <span
          style={{
            fontSize: '13px',
            color:
              event.status === 'active'
                ? 'var(--color-on-surface, #f4f4f5)'
                : event.status === 'done'
                  ? 'var(--color-on-surface-variant, rgba(244,244,245,0.6))'
                  : 'var(--color-on-surface-variant, rgba(244,244,245,0.35))',
            fontWeight: event.status === 'active' ? 500 : 400,
          }}
        >
          {event.label}
        </span>
        {event.timestamp && (
          <span
            style={{
              fontSize: '11px',
              color: 'var(--color-on-surface-variant, rgba(244,244,245,0.35))',
              flexShrink: 0,
            }}
          >
            {event.timestamp}
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RenderStatusBadge
// ---------------------------------------------------------------------------

function RenderStatusBadge({ status }: { status: RenderStatus }) {
  const config: Record<RenderStatus, { label: string; color: string; bg: string }> = {
    queued: { label: 'Queued', color: 'rgba(244,244,245,0.5)', bg: 'rgba(255,255,255,0.06)' },
    in_progress: { label: 'Processing...', color: '#93c5fd', bg: 'rgba(59,130,246,0.12)' },
    completed: { label: 'Completed', color: '#86efac', bg: 'rgba(34,197,94,0.12)' },
    failed: { label: 'Failed', color: '#f87171', bg: 'rgba(239,68,68,0.12)' },
    pending_backend: { label: 'Ready (demo)', color: '#fde68a', bg: 'rgba(234,179,8,0.12)' },
  };
  const cfg = config[status] ?? config.queued;
  return (
    <span
      style={{
        padding: '3px 10px',
        borderRadius: '999px',
        fontSize: '11px',
        fontWeight: 600,
        color: cfg.color,
        background: cfg.bg,
      }}
    >
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// PersonaAvatar (shared utility)
// ---------------------------------------------------------------------------

function PersonaAvatar({
  name,
  avatarUrl,
  size,
}: {
  name: string;
  avatarUrl?: string;
  size: number;
}) {
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
      />
    );
  }
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'var(--color-surface-tertiary, rgba(255,255,255,0.1))',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size * 0.4,
        fontWeight: 700,
        color: 'var(--color-on-surface-variant, rgba(244,244,245,0.6))',
        flexShrink: 0,
      }}
    >
      {name.charAt(0).toUpperCase()}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Style constants
// ---------------------------------------------------------------------------

const backBtnStyle: React.CSSProperties = {
  padding: '8px 14px',
  borderRadius: '8px',
  border: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.1))',
  background: 'transparent',
  color: 'var(--color-on-surface-variant, rgba(244,244,245,0.6))',
  fontSize: '13px',
  cursor: 'pointer',
  minHeight: '44px',
  flexShrink: 0,
};

import React from 'react';
