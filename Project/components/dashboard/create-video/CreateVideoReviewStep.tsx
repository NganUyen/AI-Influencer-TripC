'use client';

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
      <EmptyState message="No personas selected. Go back to Step 1 to select personas." onBack={onBack} />
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
          <h2 style={stepHeadingStyle}>Review Plan</h2>
          <p style={stepSubStyle}>
            Review the generated plan for each persona. Approve, edit, or reject each one.
          </p>
        </div>
      </div>

      {/* Plan cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
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
        <div
          style={{
            paddingTop: '8px',
            borderTop: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.08))',
          }}
        >
          <button
            id="cv-start-render-btn"
            type="button"
            onClick={onContinue}
            style={{
              padding: '14px 32px',
              borderRadius: '10px',
              border: 'none',
              background: 'var(--color-primary, #6366f1)',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 600,
              cursor: 'pointer',
              minHeight: '44px',
              letterSpacing: '0.01em',
              transition: 'background 0.15s ease',
            }}
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

  const handleEditSave = () => {
    onScriptEdit(editDraft);
    setEditMode(false);
  };

  const handleEditCancel = () => {
    setEditDraft(card.scriptPreview);
    setEditMode(false);
  };

  return (
    <div
      style={{
        borderRadius: '16px',
        border: `1px solid ${
          card.status === 'approved'
            ? 'var(--color-border-success, rgba(134,239,172,0.3))'
            : card.status === 'rejected'
              ? 'var(--color-border-error, rgba(248,113,113,0.2))'
              : 'var(--color-border-tertiary, rgba(255,255,255,0.08))'
        }`,
        background: 'var(--color-surface-secondary, rgba(255,255,255,0.03))',
        overflow: 'hidden',
        opacity: isRejected ? 0.6 : 1,
        transition: 'opacity 0.2s ease, border-color 0.2s ease',
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
        {/* Avatar */}
        <PersonaAvatar name={card.personaName} avatarUrl={card.personaAvatarUrl} size={36} />

        <span
          style={{
            flex: 1,
            fontSize: '15px',
            fontWeight: 600,
            color: 'var(--color-on-surface, #f4f4f5)',
          }}
        >
          {card.personaName}
        </span>

        <StatusBadge status={card.status} />
      </div>

      {/* Collapsed view for rejected */}
      {isRejected ? (
        <div
          style={{
            padding: '12px 20px',
            fontSize: '12px',
            color: 'var(--color-on-surface-variant, rgba(244,244,245,0.4))',
          }}
        >
          Plan rejected. You can un-reject by clicking Approve below.
        </div>
      ) : (
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Script preview */}
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
              Script Preview
            </p>

            {editMode ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <textarea
                  value={editDraft}
                  onChange={(e) => setEditDraft(e.target.value)}
                  rows={5}
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--color-border-info, #3b82f6)',
                    background: 'var(--color-surface-secondary, rgba(255,255,255,0.06))',
                    color: 'var(--color-on-surface, #f4f4f5)',
                    fontSize: '13px',
                    lineHeight: 1.6,
                    boxSizing: 'border-box',
                    resize: 'vertical',
                    fontFamily: 'inherit',
                    outline: 'none',
                  }}
                />
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button type="button" onClick={handleEditSave} style={{ ...actionBtnStyle, background: 'var(--color-primary, #6366f1)', color: '#fff' }}>
                    Save
                  </button>
                  <button type="button" onClick={handleEditCancel} style={actionBtnStyle}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div
                style={{
                  position: 'relative',
                }}
              >
                <p
                  style={{
                    fontSize: '13px',
                    color: 'var(--color-on-surface, rgba(244,244,245,0.85))',
                    lineHeight: 1.7,
                    margin: 0,
                    overflow: scriptExpanded ? 'visible' : 'hidden',
                    display: scriptExpanded ? 'block' : '-webkit-box',
                    WebkitLineClamp: scriptExpanded ? undefined : 3,
                    WebkitBoxOrient: 'vertical' as any,
                  }}
                >
                  {card.scriptPreview}
                </p>
                <button
                  type="button"
                  onClick={() => setScriptExpanded((v) => !v)}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: '4px 0',
                    cursor: 'pointer',
                    fontSize: '12px',
                    color: 'var(--color-primary, #6366f1)',
                    display: 'block',
                    marginTop: '4px',
                  }}
                >
                  {scriptExpanded ? 'Show less' : 'Show more'}
                </button>
              </div>
            )}
          </div>

          {/* Scenes */}
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
              Scenes
            </p>
            <ol style={{ margin: 0, padding: '0 0 0 20px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {card.scenes.map((scene) => (
                <li
                  key={scene.index}
                  style={{
                    fontSize: '13px',
                    color: 'var(--color-on-surface, rgba(244,244,245,0.8))',
                    lineHeight: 1.5,
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: '12px',
                  }}
                >
                  <span>{scene.description}</span>
                  {scene.durationSeconds !== undefined && (
                    <span
                      style={{
                        color: 'var(--color-on-surface-variant, rgba(244,244,245,0.4))',
                        flexShrink: 0,
                        fontSize: '12px',
                      }}
                    >
                      ({scene.durationSeconds}s)
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {/* Action row */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          padding: '12px 20px',
          borderTop: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.06))',
          justifyContent: 'flex-end',
        }}
      >
        <button
          type="button"
          onClick={onReject}
          disabled={card.status === 'rejected'}
          style={{
            ...actionBtnStyle,
            color: card.status === 'rejected'
              ? 'var(--color-on-surface-variant, rgba(244,244,245,0.3))'
              : 'var(--color-error, #f87171)',
            borderColor: card.status === 'rejected'
              ? 'transparent'
              : 'var(--color-border-error, rgba(248,113,113,0.3))',
            cursor: card.status === 'rejected' ? 'not-allowed' : 'pointer',
          }}
        >
          Reject
        </button>
        {!editMode && (
          <button
            type="button"
            onClick={() => { setEditDraft(card.scriptPreview); setEditMode(true); }}
            style={actionBtnStyle}
          >
            Edit
          </button>
        )}
        <button
          type="button"
          onClick={onApprove}
          disabled={card.status === 'approved'}
          style={{
            ...actionBtnStyle,
            color: card.status === 'approved'
              ? 'var(--color-on-surface-variant, rgba(244,244,245,0.3))'
              : 'var(--color-success, #86efac)',
            borderColor: card.status === 'approved'
              ? 'transparent'
              : 'var(--color-border-success, rgba(134,239,172,0.3))',
            cursor: card.status === 'approved' ? 'not-allowed' : 'pointer',
            background: card.status === 'approved'
              ? 'var(--color-surface-tertiary, rgba(255,255,255,0.05))'
              : undefined,
          }}
        >
          {card.status === 'approved' ? '✓ Approved' : 'Approve'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: PlanCardStatus }) {
  const CONFIG: Record<PlanCardStatus, { label: string; color: string; bg: string }> = {
    loading: { label: 'Loading...', color: 'rgba(244,244,245,0.5)', bg: 'rgba(255,255,255,0.06)' },
    demo: { label: 'Demo', color: '#fde68a', bg: 'rgba(234,179,8,0.12)' },
    ready: { label: 'Ready to review', color: '#93c5fd', bg: 'rgba(59,130,246,0.12)' },
    approved: { label: 'Approved', color: '#86efac', bg: 'rgba(34,197,94,0.12)' },
    rejected: { label: 'Rejected', color: '#f87171', bg: 'rgba(239,68,68,0.12)' },
    pending_backend: { label: 'Pending backend', color: 'rgba(244,244,245,0.5)', bg: 'rgba(255,255,255,0.06)' },
  };

  const cfg = CONFIG[status] ?? CONFIG.demo;
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

function EmptyState({ message, onBack }: { message: string; onBack: () => void }) {
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
        {message}
      </p>
      <button type="button" onClick={onBack} style={backBtnStyle}>
        ← Go back
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Style constants
// ---------------------------------------------------------------------------

const actionBtnStyle: React.CSSProperties = {
  padding: '8px 16px',
  borderRadius: '8px',
  border: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.1))',
  background: 'transparent',
  color: 'var(--color-on-surface-variant, rgba(244,244,245,0.7))',
  fontSize: '13px',
  fontWeight: 500,
  cursor: 'pointer',
  minHeight: '44px',
  transition: 'border-color 0.15s ease, color 0.15s ease',
};

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

const stepHeadingStyle: React.CSSProperties = {
  fontSize: '18px',
  fontWeight: 700,
  color: 'var(--color-on-surface, #f4f4f5)',
  margin: '0 0 4px',
};

const stepSubStyle: React.CSSProperties = {
  fontSize: '13px',
  color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
  margin: 0,
  lineHeight: 1.5,
};

import React from 'react';
