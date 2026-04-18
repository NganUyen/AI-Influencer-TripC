'use client';

import { useEffect, useMemo, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type {
  PersonaPlanCardViewModel,
  PlanReviewDecision,
  ViewTone,
} from '@/types/video-planning';

interface CreateVideoReviewStepProps {
  planCards: PersonaPlanCardViewModel[];
  onCardsChange: Dispatch<SetStateAction<PersonaPlanCardViewModel[]>>;
  onSaveEdits: () => void | Promise<void>;
  isSaving?: boolean;
  onUploadPlanVideo: (planId: string, file: File | null) => void;
  uploadingPlanIds?: string[];
  onContinue: () => void;
  isContinuing?: boolean;
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

function decisionButtonClass(
  current: PlanReviewDecision,
  target: Extract<PlanReviewDecision, 'approved' | 'rejected'>,
): string {
  const active =
    current === target
      ? target === 'approved'
        ? ' cv-action-btn--approve'
        : ' cv-action-btn--reject'
      : '';
  return `cv-action-btn${active}`;
}

export function CreateVideoReviewStep({
  planCards,
  onCardsChange,
  onSaveEdits,
  isSaving = false,
  onUploadPlanVideo,
  uploadingPlanIds = [],
  onContinue,
  isContinuing = false,
  onBack,
}: CreateVideoReviewStepProps) {
  const [isEditingContract, setIsEditingContract] = useState(false);
  const [globalScript, setGlobalScript] = useState('');
  const [globalScenes, setGlobalScenes] = useState('');

  const approvedCount = planCards.filter(
    (card) => card.reviewDecision === 'approved',
  ).length;
  const approvedCards = planCards.filter(
    (card) => card.reviewDecision === 'approved',
  );
  const missingUploadCount = approvedCards.filter(
    (card) => card.requiresUpload && !card.outputReady,
  ).length;
  const canContinue = approvedCount > 0 && missingUploadCount === 0;

  const parseScenes = (input: string) => {
    const rows = input
      .split('\n')
      .map((row) => row.trim())
      .filter(Boolean);

    return rows.map((row, idx) => {
      const [descPart, durationPart] = row.split('|').map((part) => part.trim());
      const duration = durationPart
        ? Number(durationPart.replace(/[^\d.]/g, ''))
        : NaN;
      return {
        index: idx + 1,
        description: descPart || `Scene ${idx + 1}`,
        durationSeconds: Number.isFinite(duration) ? duration : undefined,
      };
    });
  };

  useEffect(() => {
    if (planCards.length === 0) {
      return;
    }
    if (globalScript.trim() || globalScenes.trim()) {
      return;
    }

    const firstCard = planCards[0];
    setGlobalScript(firstCard?.scriptPreview || '');
    setGlobalScenes(
      (firstCard?.scenes || [])
        .map((scene) =>
          `${scene.description}${scene.durationSeconds !== undefined ? ` | ${scene.durationSeconds}` : ''}`,
        )
        .join('\n'),
    );
  }, [globalScenes, globalScript, planCards]);

  const applyContractToAll = () => {
    const parsedScenes = parseScenes(globalScenes);
    onCardsChange((cards) =>
      cards.map((card) => ({
        ...card,
        scriptPreview: globalScript.trim() ? globalScript : card.scriptPreview,
        scenes: parsedScenes.length > 0 ? parsedScenes : card.scenes,
      })),
    );
  };

  const setContractDecision = (
    decision: Extract<PlanReviewDecision, 'approved' | 'rejected'>,
  ) => {
    onCardsChange((cards) =>
      cards.map((card) => ({ ...card, reviewDecision: decision })),
    );
  };

  const setPersonaDecision = (
    planId: string | null | undefined,
    decision: Extract<PlanReviewDecision, 'approved' | 'rejected'>,
  ) => {
    onCardsChange((cards) =>
      cards.map((card) =>
        card.planId === planId ? { ...card, reviewDecision: decision } : card,
      ),
    );
  };

  const timelineRows = useMemo(() => {
    const scenes = parseScenes(globalScenes);
    let currentSecond = 0;
    return scenes.map((scene) => {
      const duration = scene.durationSeconds ?? 0;
      const startSecond = currentSecond;
      const endSecond = duration > 0 ? currentSecond + duration : currentSecond;
      currentSecond = endSecond;
      return {
        index: scene.index,
        secondLabel:
          duration > 0 ? `${startSecond}s - ${endSecond}s` : `${startSecond}s`,
        description: scene.description,
      };
    });
  }, [globalScenes]);

  if (planCards.length === 0) {
    return (
      <div className="cv-empty-state">
        <p>No persona plans were generated. Go back and select at least one persona.</p>
        <button type="button" onClick={onBack} className="cv-back-btn">← Go back</button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="cv-step-header">
        <button type="button" onClick={onBack} className="cv-back-btn">← Back</button>
        <div>
          <h2 className="cv-step-heading">Review Plan</h2>
          <p className="cv-step-sub">
            Review real backend plans, save edits, approve selected personas, then start production.
          </p>
        </div>
      </div>

      <section className="cv-section-card" style={{ marginBottom: 0 }}>
        <div className="cv-section-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <h3 className="cv-section-title" style={{ margin: 0 }}>
            Contract Overview
            <span className="cv-section-badge cv-section-badge--optional">Backend backed</span>
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span className="cv-badge cv-badge--ready">
              {approvedCount}/{planCards.length} approved
            </span>
            <button
              type="button"
              className="cv-action-btn cv-action-btn--reject"
              onClick={() => setContractDecision('rejected')}
            >
              Reject all
            </button>
            <button
              type="button"
              className="cv-action-btn cv-action-btn--approve"
              onClick={() => setContractDecision('approved')}
            >
              Approve all
            </button>
            <button
              type="button"
              className="cv-persona-action-btn"
              onClick={() => setIsEditingContract((value) => !value)}
            >
              {isEditingContract ? 'Done' : 'Edit'}
            </button>
          </div>
        </div>

        <div className="cv-section-content" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <p className="cv-card-section-label" style={{ marginBottom: 6 }}>Script Contract</p>
            {isEditingContract ? (
              <textarea
                className="cv-input cv-textarea"
                rows={6}
                value={globalScript}
                onChange={(event) => setGlobalScript(event.target.value)}
                placeholder="Generated script appears here..."
              />
            ) : (
              <p className="cv-script-text cv-script-text--expanded">
                {globalScript.trim() || 'No script generated yet.'}
              </p>
            )}
          </div>

          <div>
            <p className="cv-card-section-label" style={{ marginBottom: 6 }}>Scene Timeline</p>
            {isEditingContract ? (
              <textarea
                className="cv-input cv-textarea"
                rows={6}
                value={globalScenes}
                onChange={(event) => setGlobalScenes(event.target.value)}
                placeholder={"One scene per line. Format: Scene text | 6\nExample: Hook about product value | 5"}
              />
            ) : timelineRows.length === 0 ? (
              <p className="cv-cta-disabled-reason">No scene timeline generated yet.</p>
            ) : (
              <ol className="cv-scene-list">
                {timelineRows.map((row) => (
                  <li key={`${row.index}-${row.secondLabel}`} className="cv-scene-item">
                    <span style={{ display: 'inline-flex', minWidth: 98, fontWeight: 700 }}>{row.secondLabel}</span>
                    <span>{row.description}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>

          {isEditingContract && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
              <button type="button" className="btn-secondary" onClick={applyContractToAll}>
                Apply locally
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={onSaveEdits}
                disabled={isSaving}
              >
                {isSaving ? 'Saving…' : 'Save plan edits'}
              </button>
            </div>
          )}
        </div>
      </section>

      <section className="cv-section-card" style={{ marginBottom: 0 }}>
        <div className="cv-section-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 className="cv-section-title" style={{ margin: 0 }}>
            Selected Personas
            <span className="cv-section-badge cv-section-badge--optional">{planCards.length} selected</span>
          </h3>
        </div>
        <div className="cv-section-content" style={{ display: 'grid', gap: 12 }}>
          {planCards.map((card) => {
            const isUploading =
              Boolean(card.planId) && uploadingPlanIds.includes(card.planId || '');
            return (
              <div
                key={card.planId || card.jobId}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                  border: '1px solid rgb(174 173 169 / 0.2)',
                  borderRadius: 12,
                  padding: '12px 14px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'space-between', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <PersonaAvatar name={card.personaName} avatarUrl={card.personaAvatarUrl} size={30} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span className="cv-card-persona-name">{card.personaName}</span>
                      <span className="cv-cta-disabled-reason">
                        {card.inputModeLabel} · {card.sourceUrl || 'No source URL'}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span className={toneBadgeClass(card.statusTone)}>
                      {card.backendStatusLabel}
                    </span>
                    <button
                      type="button"
                      className={decisionButtonClass(card.reviewDecision, 'rejected')}
                      onClick={() => setPersonaDecision(card.planId, 'rejected')}
                    >
                      Reject
                    </button>
                    <button
                      type="button"
                      className={decisionButtonClass(card.reviewDecision, 'approved')}
                      onClick={() => setPersonaDecision(card.planId, 'approved')}
                    >
                      Approve
                    </button>
                  </div>
                </div>

                {card.requiresUpload && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 10,
                      flexWrap: 'wrap',
                    }}
                  >
                    <p className="cv-cta-disabled-reason" style={{ margin: 0 }}>
                      Human phone mode needs final video upload before approval.
                    </p>
                    {card.planId && (
                      <label className="btn-secondary" style={{ cursor: isUploading ? 'wait' : 'pointer' }}>
                        {isUploading ? 'Uploading…' : 'Upload final video'}
                        <input
                          type="file"
                          accept="video/*"
                          hidden
                          disabled={isUploading}
                          onChange={(event) => {
                            onUploadPlanVideo(
                              card.planId || '',
                              event.target.files?.[0] || null,
                            );
                            event.currentTarget.value = '';
                          }}
                        />
                      </label>
                    )}
                  </div>
                )}

                {card.outputReady && (
                  <p className="cv-cta-disabled-reason" style={{ margin: 0 }}>
                    Output uploaded or rendered. Ready for approval.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <div className="cv-continue-bar">
        <div className="cv-cta-wrap">
          <button
            type="button"
            onClick={canContinue ? onContinue : undefined}
            disabled={!canContinue || isContinuing}
            className="btn-primary btn-wide"
          >
            {isContinuing ? 'Starting…' : 'Approve and Continue →'}
          </button>
          {!canContinue && (
            <p className="cv-cta-disabled-reason">
              {approvedCount === 0
                ? 'Approve at least one persona to continue.'
                : 'Upload final video for approved human phone jobs before continuing.'}
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
