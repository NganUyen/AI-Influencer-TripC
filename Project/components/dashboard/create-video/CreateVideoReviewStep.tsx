'use client';

import '@/app/create-video.css';
import { useState } from 'react';
import type { PersonaPlanCardViewModel, PlanCardStatus } from '@/types/video-planning';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CreateVideoReviewStepProps {
  planCards: PersonaPlanCardViewModel[];
  onCardsChange: (cards: PersonaPlanCardViewModel[]) => void;
  onContinue: () => void;
  onBack: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVideoReviewStep({
  planCards,
  onCardsChange,
  onContinue,
  onBack,
}: CreateVideoReviewStepProps) {
  const hasApproved = planCards.some((c) => c.status === 'approved');

  const updateCard = (personaId: string, patch: Partial<PersonaPlanCardViewModel>) => {
    onCardsChange(
      planCards.map((c) => (c.personaId === personaId ? { ...c, ...patch } : c)),
    );
  };

  if (planCards.length === 0) {
    return (
      <div className="cv-empty-state">
        <p>No personas selected. Go back to Step 1 to select personas.</p>
        <button type="button" onClick={onBack} className="cv-back-btn">← Go back</button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div className="cv-step-header">
        <button type="button" onClick={onBack} className="cv-back-btn">← Back</button>
        <div>
          <h2 className="cv-step-heading">Review Plan</h2>
          <p className="cv-step-sub">
            Review the generated plan for each persona. Approve, edit, or reject each one.
          </p>
        </div>
      </div>

      {/* Plan cards */}
      <div className="cv-plan-cards">
        {planCards.map((card) => (
          <PersonaPlanCard
            key={card.personaId}
            card={card}
            onApprove={() => updateCard(card.personaId, { status: 'approved' })}
            onReject={() => updateCard(card.personaId, { status: 'rejected' })}
            onScriptEdit={(scriptPreview) => updateCard(card.personaId, { scriptPreview })}
          />
        ))}
      </div>

      {/* Continue CTA */}
      {hasApproved && (
        <div className="cv-continue-bar">
          <button
            id="cv-start-render-btn"
            type="button"
            onClick={onContinue}
            className="btn-primary"
          >
            Start Render →
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PersonaPlanCard
// ---------------------------------------------------------------------------

interface PersonaPlanCardProps {
  card: PersonaPlanCardViewModel;
  onApprove: () => void;
  onReject: () => void;
  onScriptEdit: (script: string) => void;
}

function PersonaPlanCard({ card, onApprove, onReject, onScriptEdit }: PersonaPlanCardProps) {
  const [scriptExpanded, setScriptExpanded] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editDraft, setEditDraft] = useState(card.scriptPreview);

  const isRejected = card.status === 'rejected';
  const isApproved = card.status === 'approved';

  const cardClass = [
    'cv-plan-card',
    isApproved ? 'cv-plan-card--approved' : '',
    isRejected ? 'cv-plan-card--rejected' : '',
  ].filter(Boolean).join(' ');

  const handleEditSave = () => {
    onScriptEdit(editDraft);
    setEditMode(false);
  };

  const handleEditCancel = () => {
    setEditDraft(card.scriptPreview);
    setEditMode(false);
  };

  return (
    <div className={cardClass}>
      {/* Card header */}
      <div className="cv-card-header">
        <PersonaAvatar name={card.personaName} avatarUrl={card.personaAvatarUrl} size={36} />
        <span className="cv-card-persona-name">{card.personaName}</span>
        <StatusBadge status={card.status} />
      </div>

      {/* Collapsed body for rejected */}
      {isRejected ? (
        <div className="cv-card-rejected-hint">
          Plan rejected. You can un-reject by clicking Approve below.
        </div>
      ) : (
        <div className="cv-card-body">
          {/* Script preview */}
          <div>
            <p className="cv-card-section-label">Script Preview</p>

            {editMode ? (
              <>
                <textarea
                  value={editDraft}
                  onChange={(e) => setEditDraft(e.target.value)}
                  rows={5}
                  autoFocus
                  className="cv-edit-textarea"
                />
                <div className="cv-edit-actions">
                  <button
                    type="button"
                    onClick={handleEditSave}
                    className="btn-primary btn-sm"
                  >
                    Save
                  </button>
                  <button type="button" onClick={handleEditCancel} className="btn-secondary btn-sm">
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className={`cv-script-text${scriptExpanded ? ' cv-script-text--expanded' : ''}`}>
                  {card.scriptPreview}
                </p>
                <button
                  type="button"
                  onClick={() => setScriptExpanded((v) => !v)}
                  className="cv-script-toggle"
                >
                  {scriptExpanded ? 'Show less' : 'Show more'}
                </button>
              </>
            )}
          </div>

          {/* Scenes */}
          <div>
            <p className="cv-card-section-label">Scenes</p>
            <ol className="cv-scene-list">
              {card.scenes.map((scene) => (
                <li key={scene.index} className="cv-scene-item">
                  <span>{scene.description}</span>
                  {scene.durationSeconds !== undefined && (
                    <span className="cv-scene-duration">({scene.durationSeconds}s)</span>
                  )}
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {/* Action row */}
      <div className="cv-card-action-row">
        <button
          type="button"
          onClick={onReject}
          disabled={isRejected}
          className={`cv-action-btn cv-action-btn--reject${isRejected ? ' cv-action-btn--reject--done' : ''}`}
        >
          Reject
        </button>

        {!editMode && (
          <button
            type="button"
            onClick={() => { setEditDraft(card.scriptPreview); setEditMode(true); }}
            className="cv-action-btn"
          >
            Edit
          </button>
        )}

        <button
          type="button"
          onClick={onApprove}
          disabled={isApproved}
          className={`cv-action-btn cv-action-btn--approve${isApproved ? ' cv-action-btn--approve--done' : ''}`}
        >
          {isApproved ? '✓ Approved' : 'Approve'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: PlanCardStatus }) {
  const labelMap: Record<PlanCardStatus, string> = {
    loading: 'Loading...',
    demo: 'Demo',
    ready: 'Ready to review',
    approved: 'Approved',
    rejected: 'Rejected',
    pending_backend: 'Pending backend',
  };

  const classMap: Record<PlanCardStatus, string> = {
    loading: 'cv-badge cv-badge--loading',
    demo: 'cv-badge cv-badge--demo',
    ready: 'cv-badge cv-badge--ready',
    approved: 'cv-badge cv-badge--approved',
    rejected: 'cv-badge cv-badge--rejected',
    pending_backend: 'cv-badge cv-badge--pending',
  };

  return <span className={classMap[status]}>{labelMap[status]}</span>;
}

// ---------------------------------------------------------------------------
// PersonaAvatar
// ---------------------------------------------------------------------------

function PersonaAvatar({ name, avatarUrl, size }: { name: string; avatarUrl?: string; size: number }) {
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        className="cv-avatar"
        style={{ width: size, height: size }}
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
