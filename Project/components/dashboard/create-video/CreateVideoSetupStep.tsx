'use client';

import { useCallback, useMemo, useRef, useState } from 'react';
import { toast } from 'react-hot-toast';
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

  const selectedPersonaSet = useMemo(
    () => new Set(selectedPersonaIds),
    [selectedPersonaIds],
  );

  const systemPersonas = useMemo(
    () => personas.filter((p) => !p.user_id || p.is_preset_catalog),
    [personas],
  );

  const customPersonas = useMemo(
    () => personas.filter((p) => p.user_id && !p.is_preset_catalog),
    [personas],
  );

  const systemPersonaIds = useMemo(
    () => systemPersonas.map((p) => p.persona_id),
    [systemPersonas],
  );

  const customPersonaIds = useMemo(
    () => customPersonas.map((p) => p.persona_id),
    [customPersonas],
  );

  const areAllSystemPersonasSelected = useMemo(
    () => systemPersonaIds.every((id) => selectedPersonaSet.has(id)),
    [selectedPersonaSet, systemPersonaIds],
  );

  const areAllCustomPersonasSelected = useMemo(
    () => customPersonaIds.every((id) => selectedPersonaSet.has(id)),
    [customPersonaIds, selectedPersonaSet],
  );

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

  const togglePersona = useCallback((id: string) => {
    const next = selectedPersonaSet.has(id)
      ? selectedPersonaIds.filter((p) => p !== id)
      : [...selectedPersonaIds, id];
    onChange({ selectedPersonaIds: next });
  }, [onChange, selectedPersonaIds, selectedPersonaSet]);

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
    <div className="cv-setup-grid">
      {/* ===== LEFT COLUMN: Form Sections (Stacked Cards) ===== */}
      <div className="cv-field-form">

        {/* ============== SECTION 1: Recording Mode ============== */}
        <div className="cv-section-card">
          <div className="cv-section-header">
            <h3 className="cv-section-title">
              Recording Mode
              <span className="cv-section-badge cv-section-badge--required">Required</span>
            </h3>
          </div>
          <div className="cv-section-content">
            <CreateVideoModeCards
              selectedMode={selectedMode}
              onSelect={(mode: VideoCreationMode) => onChange({ selectedMode: mode })}
            />
          </div>
        </div>

        {/* ============== SECTION 2: Source & Objective ============== */}
        <div className="cv-section-card">
          <div className="cv-section-header">
            <h3 className="cv-section-title">
              Source & Objective
              <span className="cv-section-badge cv-section-badge--required">Required</span>
            </h3>
          </div>
          <div className="cv-section-content">
            {/* Source URL */}
            <div className="cv-field-group">
              <label htmlFor="cv-source-url" className="cv-field-label">
                Source URL
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

            {/* Video Objective */}
            <div className="cv-field-group">
              <label htmlFor="cv-objective" className="cv-field-label">
                Video Objective
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
          </div>
        </div>

        {/* ============== SECTION 3: Personas ============== */}
        <div className="cv-section-card">
          <div className="cv-section-header">
            <h3 className="cv-section-title">
              Personas
              <span className="cv-section-badge cv-section-badge--required">Required</span>
            </h3>
            <span className="cv-persona-count">
              {selectedPersonaIds.length > 0 && `${selectedPersonaIds.length} selected`}
            </span>
          </div>
          <div className="cv-section-content">
            {personas.length === 0 ? (
              <div className="cv-empty-box">
                No personas available — create one in the <strong>Personas</strong> tab.
              </div>
            ) : (
              <>
                {/* System Personas */}
                {systemPersonas.length > 0 && (
                  <div className="cv-persona-group">
                    <div className="cv-persona-group-header">
                      <h4 className="cv-persona-group-title">System Personas</h4>
                      <button
                        type="button"
                        className="cv-persona-action-btn"
                        onClick={() => {
                          const systemIds = new Set(systemPersonaIds);
                          const newSelected = areAllSystemPersonasSelected
                            ? selectedPersonaIds.filter((id) => !systemIds.has(id))
                            : [...new Set([...selectedPersonaIds, ...systemPersonaIds])];
                          onChange({ selectedPersonaIds: newSelected });
                        }}
                      >
                        {areAllSystemPersonasSelected ? 'Deselect All' : 'Select All'}
                      </button>
                    </div>
                    <div className="cv-persona-list">
                      {systemPersonas.map((p) => {
                        const selected = selectedPersonaSet.has(p.persona_id);
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
                                loading="lazy"
                                decoding="async"
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
                  </div>
                )}

                {/* Custom Personas */}
                {customPersonas.length > 0 && (
                  <div className="cv-persona-group">
                    <div className="cv-persona-group-header">
                      <h4 className="cv-persona-group-title">Custom Personas</h4>
                      <button
                        type="button"
                        className="cv-persona-action-btn"
                        onClick={() => {
                          const customIds = new Set(customPersonaIds);
                          const newSelected = areAllCustomPersonasSelected
                            ? selectedPersonaIds.filter((id) => !customIds.has(id))
                            : [...new Set([...selectedPersonaIds, ...customPersonaIds])];
                          onChange({ selectedPersonaIds: newSelected });
                        }}
                      >
                        {areAllCustomPersonasSelected ? 'Deselect All' : 'Select All'}
                      </button>
                    </div>
                    <div className="cv-persona-list">
                      {customPersonas.map((p) => {
                        const selected = selectedPersonaSet.has(p.persona_id);
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
                                loading="lazy"
                                decoding="async"
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
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* ============== SECTION 4: Movement & Gesture (Optional) ============== */}
        <div className="cv-section-card">
          <div className="cv-section-header">
            <h3 className="cv-section-title">
              Movement & Gesture
              <span className="cv-section-badge cv-section-badge--optional">Optional</span>
            </h3>
          </div>
          <div className="cv-section-content">
            <p className="cv-field-label" style={{ fontSize: '13px', color: '#5c5c58' }}>
              Gesture Style
            </p>
            <div className="cv-gesture-chips">
              {['Natural', 'Expressive', 'Minimal', 'Energetic', 'Professional', 'Casual', 'Storytelling', 'Calm'].map((style) => (
                <button
                  key={style}
                  type="button"
                  className="cv-gesture-chip"
                  onClick={() => toast.success(`Gesture style: ${style}`)}
                >
                  {style}
                </button>
              ))}
            </div>

            <p className="cv-field-label" style={{ fontSize: '13px', color: '#5c5c58', marginTop: '12px' }}>
              Gesture Intensity
            </p>
            <input type="range" min="0" max="100" defaultValue="50" className="cv-slider" />
          </div>
        </div>

        {/* ============== SECTION 5: Background Music (Optional) ============== */}
        <div className="cv-section-card">
          <div className="cv-section-header">
            <h3 className="cv-section-title">
              Background Music
              <span className="cv-section-badge cv-section-badge--optional">Optional</span>
            </h3>
          </div>
          <div className="cv-section-content">
            <div className="cv-bgm-mood-cards">
              {['None', 'Upbeat', 'Corporate', 'Ambient', 'Cinematic', 'Lo-fi'].map((mood) => (
                <button
                  key={mood}
                  type="button"
                  className="cv-bgm-mood-card"
                  onClick={() => toast.success(`Background mood: ${mood}`)}
                >
                  <span className="cv-bgm-mood-icon">♪</span>
                  <span className="cv-bgm-mood-label">{mood}</span>
                </button>
              ))}
            </div>

            <p className="cv-field-label" style={{ fontSize: '13px', color: '#5c5c58', marginTop: '12px' }}>
              Volume
            </p>
            <input type="range" min="0" max="100" defaultValue="70" className="cv-slider" />
          </div>
        </div>

        {/* ============== OPTIONAL: Brief ============== */}
        <div className="cv-section-card">
          <button
            type="button"
            className="cv-section-header cv-section-header--toggle"
            onClick={() => setIsBriefExpanded((v) => !v)}
          >
            <h3 className="cv-section-title">
              Brief
              <span className="cv-section-badge cv-section-badge--optional">Optional</span>
            </h3>
            <span className={`cv-toggle-chevron${isBriefExpanded ? ' cv-toggle-chevron--open' : ''}`}>▼</span>
          </button>
          {isBriefExpanded && (
            <div className="cv-section-content">
              <div className="cv-field-group">
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
              </div>
            </div>
          )}
        </div>

        {/* ============== CTA ============== */}
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

      {/* ===== RIGHT COLUMN: Summary Sidebar (Sticky) ===== */}
      <CreateVideoSummaryPanel setupState={setupState} />
    </div>
  );
}
