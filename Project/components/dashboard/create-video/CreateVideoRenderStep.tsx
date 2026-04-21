'use client';
import { memo, useMemo } from 'react';

import type { CreateVideoProgressViewModel, RenderStatus, ViewTone } from '@/types/video-planning';

interface CreateVideoRenderStepProps {
  progressItems: CreateVideoProgressViewModel[];
  onContinue: () => void;
  onBack: () => void;
}

function toneBadgeClass(tone: ViewTone): string {
  if (tone === 'success') {
    return 'cv-badge cv-badge--approved';
  }
  if (tone === 'warning') {
    return 'cv-badge cv-badge--rejected';
  }
  return 'cv-badge cv-badge--ready';
}

export function CreateVideoRenderStep({ progressItems, onContinue, onBack }: CreateVideoRenderStepProps) {
  if (progressItems.length === 0) {
    return (
      <div className="cv-empty-state">
        <p>No approved plans yet. Go back and approve at least one persona plan.</p>
        <button type="button" onClick={onBack} className="cv-back-btn">← Go back</button>
      </div>
    );
  }

  const allDone = progressItems.every((item) =>
    item.status === 'completed' || item.status === 'failed' || item.status === 'upload_required',
  );
  const completedCount = progressItems.filter((item) => item.status === 'completed').length;
  const processingCount = progressItems.filter((item) => item.status === 'in_progress' || item.status === 'queued').length;
  const uploadRequiredCount = progressItems.filter((item) => item.status === 'upload_required').length;
  const avgProgress = Math.round(
    progressItems.reduce((sum, item) => sum + (item.progressPercent || 0), 0) /
      Math.max(progressItems.length, 1),
  );

  return (
    <div className="cv-render-shell">
      <div className="cv-step-header">
        <button type="button" onClick={onBack} className="cv-back-btn">← Back</button>
        <div>
          <h2 className="cv-step-heading">Rendering</h2>
          <p className="cv-step-sub">
            Live backend status from review-engine jobs. Refresh is automatic while work is running.
          </p>
        </div>
      </div>

      <div className="cv-render-summary-grid">
        <div className="cv-render-summary-card">
          <p className="cv-render-summary-label">Average Progress</p>
          <p className="cv-render-summary-value">{avgProgress}%</p>
        </div>
        <div className="cv-render-summary-card">
          <p className="cv-render-summary-label">Completed</p>
          <p className="cv-render-summary-value">{completedCount}</p>
        </div>
        <div className="cv-render-summary-card">
          <p className="cv-render-summary-label">In Queue/Processing</p>
          <p className="cv-render-summary-value">{processingCount}</p>
        </div>
        <div className="cv-render-summary-card">
          <p className="cv-render-summary-label">Need Upload</p>
          <p className="cv-render-summary-value">{uploadRequiredCount}</p>
        </div>
      </div>

      <div className="cv-render-cards">
        {progressItems.map((item) => (
          <RenderProgressCard key={item.planId || item.jobId} item={item} />
        ))}
      </div>

      {allDone && (
        <div className="cv-continue-bar">
          {completedCount > 0 ? (
            <button type="button" onClick={onContinue} className="btn-primary">
              Continue to publish
            </button>
          ) : (
            <div className="cv-render-fail-caution">
              <p>No videos were successfully rendered. You can try again or adjust your setup.</p>
              <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
                <button type="button" onClick={onBack} className="btn-secondary">
                  Back to Review
                </button>
                <button type="button" onClick={() => window.location.reload()} className="btn-primary">
                  Retry All
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const RenderProgressCard = memo(({ item }: { item: CreateVideoProgressViewModel }) => {
  const isDone = item.status === 'completed';
  const normalizedProgress = Math.max(0, Math.min(100, item.progressPercent || 0));
  const progressToneClass = isDone
    ? 'cv-render-progress-fill--done'
    : item.status === 'failed'
      ? 'cv-render-progress-fill--failed'
      : item.status === 'upload_required'
        ? 'cv-render-progress-fill--upload'
        : 'cv-render-progress-fill--active';
  const progressHint =
    item.status === 'completed'
      ? 'Render completed successfully.'
      : item.status === 'failed'
        ? 'Render failed. Check details below.'
        : item.status === 'upload_required'
          ? 'Waiting for your final footage upload.'
          : 'Backend is still processing. Updates are automatic.';

  return (
    <div className="cv-progress-card">
      <div className="cv-card-header">
        <PersonaAvatar name={item.personaName} avatarUrl={item.personaAvatarUrl} size={36} />
        <span className="cv-card-persona-name">{item.personaName}</span>
        <span className={toneBadgeClass(item.statusTone)}>{item.statusLabel}</span>
      </div>

      <div className="cv-progress-body">
        {item.progressPercent !== undefined && (
          <div className="cv-render-progress-panel" role="status" aria-live="polite">
            <div className="cv-render-progress-meta">
              <span className="cv-render-progress-title">Render progress</span>
              <span className="cv-render-progress-value">{normalizedProgress}%</span>
            </div>
            <div className="cv-render-progress-track" aria-label={`Progress ${normalizedProgress}%`}>
              <div
                className={`cv-render-progress-fill ${progressToneClass}`}
                style={{ width: `${normalizedProgress}%` }}
              />
            </div>
            <p className="cv-render-progress-hint">{progressHint}</p>
            <div className="cv-render-progress-scale" aria-hidden="true">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>
        )}

        <div>
          <p className="cv-card-section-label">Timeline</p>
          <div className="cv-timeline">
            {item.timelineEvents.map((event, idx) => {
              const dotClass = [
                'cv-timeline-dot',
                event.status === 'done'
                  ? 'cv-timeline-dot--done'
                  : event.status === 'active'
                    ? 'cv-timeline-dot--active'
                    : 'cv-timeline-dot--pending',
              ].join(' ');

              const labelClass = [
                'cv-timeline-label',
                event.status === 'done'
                  ? 'cv-timeline-label--done'
                  : event.status === 'active'
                    ? 'cv-timeline-label--active'
                    : '',
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

        {item.status === 'failed' && item.statusMessage && (
          <div className="cv-error-box" style={{ marginTop: 10, fontSize: '0.85rem' }}>
            <strong>Backend Error:</strong> {item.statusMessage}
          </div>
        )}

        <div>
          <p className="cv-card-section-label">Output</p>
          {item.playableVideoUrl ? (
            <div style={{ display: 'grid', gap: 10 }}>
              <video
                src={item.playableVideoUrl}
                className="cv-output-preview-img"
                controls
                preload="metadata"
              />
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <a className="btn-secondary" href={item.playableVideoUrl} target="_blank" rel="noreferrer">
                  Open preview
                </a>
                {item.downloadUrl && (
                  <a className="btn-secondary" href={item.downloadUrl} target="_blank" rel="noreferrer">
                    Download
                  </a>
                )}
              </div>
            </div>
          ) : (
            <div className="cv-output-placeholder">
              <p className="cv-output-placeholder-title">Preview is on the way</p>
              <p className="cv-output-placeholder-subtitle">We are still receiving backend output. This card updates automatically.</p>
            </div>
          )}
        </div>

        {item.status === 'upload_required' && (
          <div className="cv-ready-banner">
            <strong>Upload required.</strong>
            Final phone-recorded footage must be uploaded before backend approval can continue.
          </div>
        )}

        {item.readyToPublish && (
          <div className="cv-ready-banner">
            <strong>Ready for publish.</strong>
            Final video is available and backend publish action can run in next step.
          </div>
        )}
      </div>
    </div>
  );
});

RenderProgressCard.displayName = 'RenderProgressCard';

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

export function getRenderStatusLabel(status: RenderStatus): string {
  const labelMap: Record<RenderStatus, string> = {
    queued: 'Queued',
    in_progress: 'Processing',
    completed: 'Completed',
    failed: 'Failed',
    upload_required: 'Upload required',
  };
  return labelMap[status];
}
