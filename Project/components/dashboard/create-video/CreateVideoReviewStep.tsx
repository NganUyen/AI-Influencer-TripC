'use client';

import { useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { PersonaPlanCardViewModel, PlanCardStatus } from '@/types/video-planning';

interface CreateVideoReviewStepProps {
  planCards: PersonaPlanCardViewModel[];
  onCardsChange: Dispatch<SetStateAction<PersonaPlanCardViewModel[]>>;
  onContinue: () => void;
  onBack: () => void;
}

const STATUS_META: Record<PlanCardStatus, { label: string; className: string }> = {
  loading: { label: 'Loading', className: 'cv-badge cv-badge--loading' },
  demo: { label: 'Draft plan', className: 'cv-badge cv-badge--demo' },
  ready: { label: 'Ready', className: 'cv-badge cv-badge--ready' },
  approved: { label: 'Approved', className: 'cv-badge cv-badge--approved' },
  rejected: { label: 'Rejected', className: 'cv-badge cv-badge--rejected' },
  pending_backend: { label: 'Pending backend', className: 'cv-badge cv-badge--pending' },
};

export function CreateVideoReviewStep({
  planCards,
  onCardsChange,
  onContinue,
  onBack,
}: CreateVideoReviewStepProps) {
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});
  const approvedCount = planCards.filter((card) => card.status === 'approved').length;
  const canContinue = approvedCount > 0;

  const setCardStatus = (personaId: string, status: Extract<PlanCardStatus, 'approved' | 'rejected'>) => {
    onCardsChange((currentCards) =>
      currentCards.map((card) =>
        card.personaId === personaId
          ? {
              ...card,
              status,
            }
          : card,
      ),
    );
  };

  const toggleExpanded = (personaId: string) => {
    setExpandedCards((current) => ({
      ...current,
      [personaId]: !current[personaId],
    }));
  };

  if (planCards.length === 0) {
    return (
      <div className="cv-empty-state">
        <p>No persona plans were generated. Go back and select at least one persona.</p>
        <button type="button" onClick={onBack} className="cv-back-btn">← Go back</button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="cv-step-header">
        <button type="button" onClick={onBack} className="cv-back-btn">← Back</button>
        <div>
          <h2 className="cv-step-heading">Review Plan</h2>
          <p className="cv-step-sub">
            Approve at least one persona plan before sending it to rendering.
          </p>
        </div>
      </div>

      <div className="cv-plan-cards">
        {planCards.map((card) => {
          const isExpanded = expandedCards[card.personaId] ?? false;
          const isApproved = card.status === 'approved';
          const isRejected = card.status === 'rejected';
          const statusMeta = STATUS_META[card.status];

          return (
            <article
              key={card.personaId}
              className={[
                'cv-plan-card',
                isApproved ? 'cv-plan-card--approved' : '',
                isRejected ? 'cv-plan-card--rejected' : '',
              ].filter(Boolean).join(' ')}
            >
              <div className="cv-card-header">
                <PersonaAvatar name={card.personaName} avatarUrl={card.personaAvatarUrl} size={36} />
                <span className="cv-card-persona-name">{card.personaName}</span>
                <span className={statusMeta.className}>{statusMeta.label}</span>
              </div>

              <div className="cv-card-body">
                <div>
                  <p className="cv-card-section-label">Script Preview</p>
                  <p className={`cv-script-text${isExpanded ? ' cv-script-text--expanded' : ''}`}>
                    {card.scriptPreview}
                  </p>
                  {card.scriptPreview.length > 180 && (
                    <button
                      type="button"
                      className="cv-script-toggle"
                      onClick={() => toggleExpanded(card.personaId)}
                    >
                      {isExpanded ? 'Show less' : 'Show more'}
                    </button>
                  )}
                </div>

                <div>
                  <p className="cv-card-section-label">Scene Preview</p>
                  <ol className="cv-scene-list">
                    {card.scenes.map((scene) => (
                      <li key={scene.index} className="cv-scene-item">
                        <span>{scene.description}</span>
                        {scene.durationSeconds !== undefined && (
                          <span className="cv-scene-duration">{scene.durationSeconds}s</span>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>

              {isRejected && (
                <div className="cv-card-rejected-hint">
                  This plan will be excluded from the render queue until you approve it again.
                </div>
              )}

              <div className="cv-card-action-row">
                <button
                  type="button"
                  className={[
                    'cv-action-btn',
                    'cv-action-btn--reject',
                    isRejected ? 'cv-action-btn--reject--done' : '',
                  ].filter(Boolean).join(' ')}
                  onClick={() => setCardStatus(card.personaId, 'rejected')}
                  disabled={isRejected}
                >
                  Reject
                </button>
                <button
                  type="button"
                  className={[
                    'cv-action-btn',
                    'cv-action-btn--approve',
                    isApproved ? 'cv-action-btn--approve--done' : '',
                  ].filter(Boolean).join(' ')}
                  onClick={() => setCardStatus(card.personaId, 'approved')}
                  disabled={isApproved}
                >
                  {isApproved ? 'Approved' : 'Approve'}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <div className="cv-continue-bar">
        <div className="cv-cta-wrap">
          <button
            type="button"
            onClick={canContinue ? onContinue : undefined}
            disabled={!canContinue}
            className="btn-primary btn-wide"
          >
            Render Approved Videos →
          </button>
          {!canContinue && (
            <p className="cv-cta-disabled-reason">
              Approve at least one persona plan to continue.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

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
