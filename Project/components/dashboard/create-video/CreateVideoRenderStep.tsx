'use client';

import type { CreateVideoProgressViewModel, RenderStatus } from '@/types/video-planning';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CreateVideoRenderStepProps {
  progressItems: CreateVideoProgressViewModel[];
  onContinue: () => void;
  onBack: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVideoRenderStep({ progressItems, onContinue, onBack }: CreateVideoRenderStepProps) {
  if (progressItems.length === 0) {
    return (
      <div className="cv-empty-state">
        <p>No approved plans yet. Go back and approve at least one persona plan.</p>
        <button type="button" onClick={onBack} className="cv-back-btn">← Go back</button>
      </div>
    );
  }

  const allDone = progressItems.every(
    (item) => item.status === 'completed' || item.status === 'pending_backend',
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div className="cv-step-header">
        <button type="button" onClick={onBack} className="cv-back-btn">← Back</button>
        <div>
          <h2 className="cv-step-heading">Rendering</h2>
          <p className="cv-step-sub">
            Video production is being simulated. Real render progress will appear here in Phase 3.
          </p>
        </div>
      </div>

      {/* Progress cards */}
      <div className="cv-render-cards">
        {progressItems.map((item) => (
          <RenderProgressCard key={item.personaId} item={item} />
        ))}
      </div>

      {allDone && (
        <div className="cv-continue-bar">
          <button type="button" onClick={onContinue} className="btn-primary">
            Continue to publish
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RenderProgressCard
// ---------------------------------------------------------------------------

function RenderProgressCard({ item }: { item: CreateVideoProgressViewModel }) {
  const isDone = item.status === 'completed' || item.status === 'pending_backend';

  return (
    <div className="cv-progress-card">
      {/* Card header */}
      <div className="cv-card-header">
        <PersonaAvatar name={item.personaName} avatarUrl={item.personaAvatarUrl} size={36} />
        <span className="cv-card-persona-name">{item.personaName}</span>
        <RenderStatusBadge status={item.status} />
      </div>

      {/* Card body */}
      <div className="cv-progress-body">
        {/* Timeline */}
        <div>
          <p className="cv-card-section-label">Timeline</p>
          <div className="cv-timeline">
            {item.timelineEvents.map((event, idx) => {
              const dotClass = [
                'cv-timeline-dot',
                event.status === 'done'    ? 'cv-timeline-dot--done' :
                event.status === 'active'  ? 'cv-timeline-dot--active' :
                                             'cv-timeline-dot--pending',
              ].join(' ');

              const labelClass = [
                'cv-timeline-label',
                event.status === 'done'   ? 'cv-timeline-label--done' :
                event.status === 'active' ? 'cv-timeline-label--active' : '',
              ].filter(Boolean).join(' ');

              return (
                <div key={idx} className="cv-timeline-row">
                  <span className={dotClass} aria-hidden="true" />
                  <div className="cv-timeline-content">
                    <span className={labelClass}>{event.label}</span>
                    {event.timestamp && (
                      <span className="cv-timeline-time">{event.timestamp}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Progress bar */}
        {item.progressPercent !== undefined && (
          <div className="cv-render-progress-track">
            <div
              className={`cv-render-progress-fill${isDone ? ' cv-render-progress-fill--done' : ''}`}
              style={{ width: `${item.progressPercent}%` }}
            />
          </div>
        )}

        {/* Output preview */}
        <div>
          <p className="cv-card-section-label">Output</p>
          {item.outputPreviewUrl ? (
            <img
              src={item.outputPreviewUrl}
              alt="Video preview"
              className="cv-output-preview-img"
              loading="lazy"
              decoding="async"
            />
          ) : (
            <div className="cv-output-placeholder">
              Preview available after render
            </div>
          )}
        </div>

        {/* Final state label */}
        {isDone && (
          <div className="cv-ready-banner">
            <strong>Ready for backend integration.</strong>
            Real render progress and output will be available once the Phase 3 backend is connected.
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RenderStatusBadge
// ---------------------------------------------------------------------------

function RenderStatusBadge({ status }: { status: RenderStatus }) {
  const labelMap: Record<RenderStatus, string> = {
    queued:          'Queued',
    in_progress:     'Processing...',
    completed:       'Completed',
    failed:          'Failed',
    pending_backend: 'Ready (demo)',
  };

  const classMap: Record<RenderStatus, string> = {
    queued:          'cv-badge cv-badge--queued',
    in_progress:     'cv-badge cv-badge--in_progress',
    completed:       'cv-badge cv-badge--completed',
    failed:          'cv-badge cv-badge--failed',
    pending_backend: 'cv-badge cv-badge--pending_backend',
  };

  return <span className={classMap[status]}>{labelMap[status]}</span>;
}

// ---------------------------------------------------------------------------
// PersonaAvatar (shared utility)
// ---------------------------------------------------------------------------

function PersonaAvatar({ name, avatarUrl, size }: { name: string; avatarUrl?: string; size: number }) {
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        className="cv-avatar"
        style={{ width: size, height: size }}
        loading="lazy"
        decoding="async"
      />
    );
  }
  return (
    <div
      className="cv-avatar-fallback"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {name.charAt(0).toUpperCase()}
    </div>
  );
}
