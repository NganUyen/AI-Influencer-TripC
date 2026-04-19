'use client';

import { useMemo, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type {
  PersonaPlanCardViewModel,
  PlanReviewDecision,
  SharedContractDraft,
  ViewTone,
} from '@/types/video-planning';

interface CreateVideoReviewStepProps {
  planCards: PersonaPlanCardViewModel[];
  sharedContractDraft: SharedContractDraft;
  hasUnsavedChanges?: boolean;
  onSharedContractChange: (draft: SharedContractDraft) => void;
  onResetSharedContract: () => void;
  hasDivergentContracts?: boolean;
  onCardsChange: Dispatch<SetStateAction<PersonaPlanCardViewModel[]>>;
  onSaveEdits: () => void | Promise<void>;
  isSaving?: boolean;
  onDeletePlans: (planIds: string[]) => Promise<void>;
  onReturnToSetup: () => void;
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

function parseScenes(input: string) {
  const rows = input
    .split('\n')
    .map((row) => row.trim())
    .filter(Boolean);

  return rows.map((row, idx) => {
    const [descPart, durationPart] = row.split('|').map((part) => part.trim());
    const duration = durationPart
      ? Number(durationPart.replace(/[^\d.]/g, ''))
      : Number.NaN;
    return {
      index: idx + 1,
      description: descPart || `Scene ${idx + 1}`,
      durationSeconds: Number.isFinite(duration) ? duration : undefined,
    };
  });
}

export function CreateVideoReviewStep({
  planCards,
  sharedContractDraft,
  hasUnsavedChanges = false,
  onSharedContractChange,
  onResetSharedContract,
  hasDivergentContracts = false,
  onCardsChange,
  onSaveEdits,
  isSaving = false,
  onDeletePlans,
  onReturnToSetup,
  onUploadPlanVideo,
  uploadingPlanIds = [],
  onContinue,
  isContinuing = false,
  onBack,
}: CreateVideoReviewStepProps) {
  const [isEditingContract, setIsEditingContract] = useState(false);
  const [rejectModalPlanIds, setRejectModalPlanIds] = useState<string[]>([]);
  const [isDeletingPlans, setIsDeletingPlans] = useState(false);

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

  const setContractDecision = (
    decision: Extract<PlanReviewDecision, 'approved' | 'rejected'>,
  ) => {
    onCardsChange((cards) =>
      cards.map((card) => ({ ...card, reviewDecision: decision })),
    );
  };

  const setPersonaDecision = (
    targetCardKey: string,
    decision: Extract<PlanReviewDecision, 'approved' | 'rejected'>,
  ) => {
    onCardsChange((cards) =>
      cards.map((card) =>
        (card.planId || card.jobId) === targetCardKey
          ? { ...card, reviewDecision: decision }
          : card,
      ),
    );
  };

  const openRejectModal = (planIds: string[]) => {
    const uniquePlanIds = Array.from(
      new Set(planIds.map((planId) => planId.trim()).filter(Boolean)),
    );
    if (uniquePlanIds.length === 0) {
      return;
    }
    setRejectModalPlanIds(uniquePlanIds);
  };

  const closeRejectModal = () => {
    if (isDeletingPlans) {
      return;
    }
    setRejectModalPlanIds([]);
  };

  const confirmDeletePlans = async () => {
    if (rejectModalPlanIds.length === 0) {
      return;
    }

    setIsDeletingPlans(true);
    try {
      await onDeletePlans(rejectModalPlanIds);
      setRejectModalPlanIds([]);
      onReturnToSetup();
    } finally {
      setIsDeletingPlans(false);
    }
  };

  const timelineRows = useMemo(() => {
    const scenes = parseScenes(sharedContractDraft.scenesText);
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
  }, [sharedContractDraft.scenesText]);

  const languageSummary = useMemo(() => {
    const labels = Array.from(
      new Set(
        planCards
          .map((card) => String(card.personaLanguage || '').trim())
          .filter(Boolean),
      ),
    );
    if (labels.length === 0) {
      return 'Persona languages stay synced from the selected targets.';
    }
    if (labels.length <= 3) {
      return `Persona targets: ${labels.join(' / ')}.`;
    }
    return `Persona targets span ${labels.length} languages and stay aligned to this shared contract.`;
  }, [planCards]);

  const personaStats = useMemo(() => {
    const languages = new Set(
      planCards
        .map((card) => String(card.personaLanguage || '').trim())
        .filter(Boolean),
    );
    return {
      total: planCards.length,
      languageCount: languages.size,
      uploadRequiredCount: planCards.filter((card) => card.requiresUpload).length,
      outputReadyCount: planCards.filter((card) => card.outputReady).length,
    };
  }, [planCards]);

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
            Edit one shared contract, then approve the persona lanes that should continue into production.
          </p>
        </div>
      </div>

      <section className="cv-section-card" style={{ marginBottom: 0 }}>
        <div className="cv-shared-contract-shell">
          <div className="cv-section-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
            <div style={{ display: 'grid', gap: 6 }}>
              <h3 className="cv-section-title" style={{ margin: 0 }}>
                Shared Video Contract
                <span className="cv-section-badge cv-section-badge--optional">English master draft</span>
              </h3>
              <p className="cv-shared-contract-subtitle">
                This is the shared contract for every selected persona. Edit it once in English, then each
                persona lane stays aligned with its own target language and production path.
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span className={`cv-badge ${hasUnsavedChanges ? 'cv-badge--pending_backend' : 'cv-badge--approved'}`}>
                {hasUnsavedChanges ? 'Unsaved shared edits' : 'Shared contract saved'}
              </span>
              <span className="cv-badge cv-badge--ready">
                {approvedCount}/{planCards.length} approved
              </span>
              <button
                type="button"
                className="cv-action-btn cv-action-btn--reject"
                onClick={() => openRejectModal(planCards.map((card) => card.planId || ''))}
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

          <div className="cv-shared-contract-meta">
            <div className="cv-shared-contract-stats">
              <span className="cv-persona-target-pill">{personaStats.total} personas</span>
              <span className="cv-persona-target-pill">{Math.max(personaStats.languageCount, 1)} language lanes</span>
              <span className="cv-persona-target-pill">{personaStats.outputReadyCount} ready outputs</span>
              {personaStats.uploadRequiredCount > 0 && (
                <span className="cv-persona-target-pill">{personaStats.uploadRequiredCount} upload required</span>
              )}
            </div>
            <div className="cv-shared-contract-note">
              <strong>Shared contract note</strong>
              <span>{languageSummary}</span>
            </div>
            {hasDivergentContracts && (
              <div className="cv-shared-contract-warning">
                Existing persona drafts differed. This editor is now the single shared contract source.
              </div>
            )}
          </div>

          <div className="cv-section-content cv-shared-contract-grid">
            <div className="cv-shared-contract-panel">
              <p className="cv-card-section-label" style={{ marginBottom: 6 }}>Master Script</p>
              {isEditingContract ? (
                <textarea
                  className="cv-input cv-textarea"
                  rows={8}
                  value={sharedContractDraft.scriptText}
                  onChange={(event) =>
                    onSharedContractChange({
                      ...sharedContractDraft,
                      scriptText: event.target.value,
                    })
                  }
                  placeholder="Write the shared English script that every selected persona follows..."
                />
              ) : (
                <p className="cv-script-text cv-script-text--expanded">
                  {sharedContractDraft.scriptText.trim() || 'No shared script generated yet.'}
                </p>
              )}
            </div>

            <div className="cv-shared-contract-panel">
              <p className="cv-card-section-label" style={{ marginBottom: 6 }}>Master Scene Timeline</p>
              {isEditingContract ? (
                <textarea
                  className="cv-input cv-textarea"
                  rows={8}
                  value={sharedContractDraft.scenesText}
                  onChange={(event) =>
                    onSharedContractChange({
                      ...sharedContractDraft,
                      scenesText: event.target.value,
                    })
                  }
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
          </div>

          {isEditingContract && (
            <div className="cv-shared-contract-actions">
              <button type="button" className="btn-secondary" onClick={onResetSharedContract}>
                Revert to backend draft
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={onSaveEdits}
                disabled={isSaving || !hasUnsavedChanges}
              >
                {isSaving ? 'Saving…' : 'Save shared edits'}
              </button>
            </div>
          )}
        </div>
      </section>

      <section className="cv-section-card" style={{ marginBottom: 0 }}>
        <div className="cv-section-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ display: 'grid', gap: 6 }}>
            <h3 className="cv-section-title" style={{ margin: 0 }}>
              Persona Targets
              <span className="cv-section-badge cv-section-badge--optional">Approval stays per persona</span>
            </h3>
            <p className="cv-shared-contract-subtitle">
              Keep one contract shared, then choose which persona lanes are approved to continue.
            </p>
          </div>
          <span className="cv-section-badge cv-section-badge--optional">{planCards.length} selected</span>
        </div>

        <div className="cv-section-content cv-persona-target-grid">
          {planCards.map((card) => {
            const isUploading =
              Boolean(card.planId) && uploadingPlanIds.includes(card.planId || '');
            const cardKey = card.planId || card.jobId;
            return (
              <div key={cardKey} className="cv-persona-target-card">
                <div className="cv-persona-target-toprow">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <PersonaAvatar name={card.personaName} avatarUrl={card.personaAvatarUrl} size={38} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <span className="cv-card-persona-name">{card.personaName}</span>
                      <span className="cv-cta-disabled-reason">
                        {card.inputModeLabel} · {card.sourceUrl || 'No source URL'}
                      </span>
                    </div>
                  </div>
                  <span className={toneBadgeClass(card.statusTone)}>
                    {card.backendStatusLabel}
                  </span>
                </div>

                <div className="cv-persona-target-meta">
                  <span className="cv-persona-target-pill">
                    {card.personaLanguage || 'Language synced from persona'}
                  </span>
                  <span className="cv-persona-target-pill">
                    {card.reviewDecision === 'approved'
                      ? 'Approved lane'
                      : card.reviewDecision === 'rejected'
                        ? 'Rejected lane'
                        : 'Pending lane'}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className={decisionButtonClass(card.reviewDecision, 'rejected')}
                    onClick={() => openRejectModal([card.planId || ''])}
                    disabled={!card.planId}
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    className={decisionButtonClass(card.reviewDecision, 'approved')}
                    onClick={() => setPersonaDecision(cardKey, 'approved')}
                  >
                    Approve
                  </button>
                </div>

                {card.requiresUpload && (
                  <div className="cv-persona-target-inline-note">
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

      {rejectModalPlanIds.length > 0 && (
        <div className="cv-delete-modal-backdrop" onClick={closeRejectModal} aria-hidden="true" />
      )}

      {rejectModalPlanIds.length > 0 && (
        <div className="cv-delete-modal-shell" role="dialog" aria-modal="true" aria-label="Delete review plans confirmation">
          <div className="cv-delete-modal-card">
            <div className="cv-delete-modal-header">
              <div>
                <h4 className="cv-delete-modal-title">Delete selected plan{rejectModalPlanIds.length > 1 ? 's' : ''}?</h4>
                <p className="cv-delete-modal-subtitle">
                  This will remove the selected plan{rejectModalPlanIds.length > 1 ? 's' : ''} and take you back to Setup.
                </p>
              </div>
              <button type="button" className="cv-delete-modal-close" onClick={closeRejectModal} aria-label="Close delete modal">
                ×
              </button>
            </div>

            <div className="cv-delete-modal-body">
              <p className="cv-delete-modal-note">
                If you only want to revise the shared contract, choose <strong>Keep editing</strong> instead of deleting.
              </p>
              <div className="cv-delete-modal-summary">
                <span className="cv-delete-modal-count">{rejectModalPlanIds.length} plan{rejectModalPlanIds.length > 1 ? 's' : ''} selected</span>
                <ul className="cv-delete-modal-list">
                  {rejectModalPlanIds.map((planId) => (
                    <li key={planId}>{planId}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="cv-delete-modal-actions">
              <button type="button" className="btn-secondary" onClick={closeRejectModal} disabled={isDeletingPlans}>
                Keep editing
              </button>
              <button
                type="button"
                className="cv-action-btn cv-action-btn--reject"
                onClick={confirmDeletePlans}
                disabled={isDeletingPlans}
              >
                {isDeletingPlans ? 'Deleting…' : 'Delete and return to Setup'}
              </button>
            </div>
          </div>
        </div>
      )}
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
