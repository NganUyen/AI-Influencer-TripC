'use client';

import '@/app/create-video.css';
import { useCallback, useRef, useState } from 'react';
import type { CreateVideoSetupState, VideoCreationMode } from '@/types/video-planning';
import type { Persona } from '@/components/customer-dashboard';
import { CreateVideoModeCards } from './CreateVideoModeCards';
import { CreateVideoSummaryPanel } from './CreateVideoSummaryPanel';
import { customerApiRequest } from '@/lib/customer-api';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CreateVideoSetupStepProps {
  setupState: CreateVideoSetupState;
  onChange: (patch: Partial<CreateVideoSetupState>) => void;
  personas: Persona[];
  onContinue: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVideoSetupStep({
  setupState,
  onChange,
  personas,
  onContinue,
}: CreateVideoSetupStepProps) {
  const {
    sourceUrl,
    urlValidationStatus,
    urlValidationMessage,
    selectedPersonaIds,
    objective,
    brief,
    selectedMode,
  } = setupState;

  const [isBriefExpanded, setIsBriefExpanded] = useState(false);
  const validationAbortRef = useRef<AbortController | null>(null);

  // -------------------------------------------------------------------------
  // URL validation on blur
  // -------------------------------------------------------------------------

  const handleUrlBlur = useCallback(async () => {
    const url = sourceUrl.trim();
    if (!url) {
      onChange({ urlValidationStatus: 'idle', urlValidationMessage: undefined });
      return;
    }

    validationAbortRef.current?.abort();
    const controller = new AbortController();
    validationAbortRef.current = controller;

    onChange({ urlValidationStatus: 'validating', urlValidationMessage: undefined });

    try {
      const result = await customerApiRequest<{ valid: boolean; message?: string; domain?: string }>(
        '/api/customer/review-engine/source/validate',
        { method: 'POST', body: JSON.stringify({ url }) },
      );

      if (controller.signal.aborted) return;

      if (result.valid) {
        onChange({
          urlValidationStatus: 'valid',
          urlValidationMessage: result.message ?? `Source validated: ${result.domain ?? url}`,
        });
      } else {
        onChange({
          urlValidationStatus: 'invalid',
          urlValidationMessage: result.message ?? 'This URL could not be validated.',
        });
      }
    } catch (err) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : 'Validation failed';
      onChange({ urlValidationStatus: 'invalid', urlValidationMessage: msg });
    }
  }, [sourceUrl, onChange]);

  // -------------------------------------------------------------------------
  // Persona selection toggle
  // -------------------------------------------------------------------------

  const togglePersona = (id: string) => {
    const next = selectedPersonaIds.includes(id)
      ? selectedPersonaIds.filter((p) => p !== id)
      : [...selectedPersonaIds, id];
    onChange({ selectedPersonaIds: next });
  };

  // -------------------------------------------------------------------------
  // Continue guard
  // -------------------------------------------------------------------------

  const canContinue = urlValidationStatus === 'valid' && selectedPersonaIds.length > 0;

  const disabledReason = (() => {
    if (urlValidationStatus !== 'valid' && selectedPersonaIds.length === 0)
      return 'Enter a valid source URL and select at least one persona to continue.';
    if (urlValidationStatus !== 'valid')
      return 'Enter a valid source URL to continue.';
    if (selectedPersonaIds.length === 0)
      return 'Select at least one persona to continue.';
    return null;
  })();

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <>
      {/* Keyframes live in create-video.css */}
      <div className="cv-setup-grid">
        {/* ---------------------------------------------------------------- */}
        {/* LEFT — Form                                                       */}
        {/* ---------------------------------------------------------------- */}
        <div className="cv-field-form">

          {/* Source URL */}
          <div className="cv-field-group">
            <label htmlFor="cv-source-url" className="cv-field-label">
              Source URL <span className="cv-required-star">*</span>
            </label>
            <div className="cv-input-wrap">
              <input
                id="cv-source-url"
                type="url"
                placeholder="https://example.com/product"
                value={sourceUrl}
                onChange={(e) =>
                  onChange({ sourceUrl: e.target.value, urlValidationStatus: 'idle', urlValidationMessage: undefined })
                }
                onBlur={handleUrlBlur}
                className="cv-input"
              />
              {urlValidationStatus === 'validating' && (
                <span className="cv-spinner" aria-label="Validating" />
              )}
            </div>
            {urlValidationStatus === 'valid' && urlValidationMessage && (
              <p className="cv-validation-msg cv-validation-msg--valid">✓ {urlValidationMessage}</p>
            )}
            {urlValidationStatus === 'invalid' && urlValidationMessage && (
              <p className="cv-validation-msg cv-validation-msg--invalid">✗ {urlValidationMessage}</p>
            )}
            {urlValidationStatus === 'validating' && (
              <p className="cv-validation-msg cv-validation-msg--loading">Validating source...</p>
            )}
          </div>

          {/* Personas */}
          <div className="cv-field-group">
            <span className="cv-field-label">
              Personas <span className="cv-required-star">*</span>
            </span>
            {personas.length === 0 ? (
              <div className="cv-empty-box">
                No personas available — create one in the <strong>Personas</strong> tab.
              </div>
            ) : (
              <div className="cv-persona-list">
                {personas.map((p) => {
                  const selected = selectedPersonaIds.includes(p.persona_id);
                  return (
                    <button
                      key={p.persona_id}
                      type="button"
                      onClick={() => togglePersona(p.persona_id)}
                      aria-pressed={selected}
                      className={`cv-persona-option${selected ? ' cv-persona-option--selected' : ''}`}
                    >
                      {p.avatar_image_url ? (
                        <img
                          src={p.avatar_image_url}
                          alt={p.display_name}
                          className="cv-persona-avatar"
                        />
                      ) : (
                        <div className="cv-persona-avatar-fallback">
                          {p.display_name.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <span className={`cv-persona-name${selected ? ' cv-persona-name--selected' : ''}`}>
                        {p.display_name}
                      </span>
                      {selected && (
                        <span className="cv-persona-check" aria-hidden="true">✓</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Video Objective */}
          <div className="cv-field-group">
            <label htmlFor="cv-objective" className="cv-field-label">
              Video Objective <span className="cv-required-star">*</span>
            </label>
            <div className="cv-input-wrap">
              <textarea
                id="cv-objective"
                placeholder="Describe the goal of this video (e.g. drive signups, showcase a feature…)"
                value={objective}
                onChange={(e) => onChange({ objective: e.target.value.slice(0, 200) })}
                rows={3}
                className="cv-input cv-textarea"
              />
              <span className={`cv-char-count${objective.length >= 160 ? ' cv-char-count--warn' : ''}`}>
                {objective.length}/200
              </span>
            </div>
          </div>

          {/* Brief — collapsible */}
          <div className="cv-field-group">
            <button
              type="button"
              className="cv-field-label--toggle"
              onClick={() => setIsBriefExpanded((v) => !v)}
            >
              Brief
              <span className={`cv-brief-chevron${isBriefExpanded ? ' cv-brief-chevron--open' : ''}`}>▼</span>
              <span className="cv-field-optional">(optional)</span>
            </button>
            {isBriefExpanded && (
              <div className="cv-input-wrap">
                <textarea
                  id="cv-brief"
                  placeholder="Any additional context, brand guidelines, or tone requirements…"
                  value={brief ?? ''}
                  onChange={(e) => onChange({ brief: e.target.value.slice(0, 500) })}
                  rows={4}
                  className="cv-input cv-textarea"
                />
                <span className={`cv-char-count${(brief ?? '').length >= 400 ? ' cv-char-count--warn' : ''}`}>
                  {(brief ?? '').length}/500
                </span>
              </div>
            )}
          </div>

          {/* Mode */}
          <div className="cv-field-group">
            <span className="cv-field-label">Recording Mode</span>
            <CreateVideoModeCards
              selectedMode={selectedMode}
              onSelect={(mode: VideoCreationMode) => onChange({ selectedMode: mode })}
            />
          </div>

          {/* CTA */}
          <div className="cv-cta-wrap">
            <button
              id="cv-continue-btn"
              type="button"
              onClick={canContinue ? onContinue : undefined}
              disabled={!canContinue}
              className="btn-primary btn-wide"
            >
              Review Plan →
            </button>
            {!canContinue && disabledReason && (
              <p className="cv-cta-disabled-reason">{disabledReason}</p>
            )}
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* RIGHT — Summary panel                                             */}
        {/* ---------------------------------------------------------------- */}
        <CreateVideoSummaryPanel setupState={setupState} />
      </div>
    </>
  );
}
