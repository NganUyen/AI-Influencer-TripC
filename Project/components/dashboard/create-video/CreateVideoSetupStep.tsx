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
  systemPersonaOptions?: Persona[];
  customPersonaOptions?: Persona[];
  onContinue: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVideoSetupStep({
  setupState,
  onChange,
  personas,
  systemPersonaOptions,
  customPersonaOptions,
  onContinue,
}: CreateVideoSetupStepProps) {
  const {
    sourceUrl,
    urlValidationStatus,
    urlValidationMessage,
    urlValidationDetails,
    selectedPersonaIds,
    objective,
    brief,
    selectedMode,
    selectedBackground,
    selectedMovementStyle,
    selectedMusicMood,
  } = setupState;

  const backgroundOptions = [
    { id: 'studio-soft', label: 'Studio Soft Light' },
    { id: 'office-modern', label: 'Modern Office' },
    { id: 'minimal-white', label: 'Minimal White' },
    { id: 'tech-gradient', label: 'Tech Gradient' },
    { id: 'lifestyle-home', label: 'Lifestyle Home' },
    { id: 'city-night', label: 'City Night' },
  ];

  const [isBriefExpanded, setIsBriefExpanded] = useState(false);
  const [expandedPersonaGroups, setExpandedPersonaGroups] = useState({
    system: true,
    custom: true,
  });
  const validationAbortRef = useRef<AbortController | null>(null);

  const selectedPersonaSet = useMemo(
    () => new Set(selectedPersonaIds),
    [selectedPersonaIds],
  );

  const systemPersonas = useMemo(
    () => systemPersonaOptions ?? personas.filter(isSystemPersona),
    [personas, systemPersonaOptions],
  );

  const customPersonas = useMemo(
    () => customPersonaOptions ?? personas.filter((p) => !isSystemPersona(p)),
    [customPersonaOptions, personas],
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

  const selectedSystemCount = useMemo(
    () => systemPersonaIds.filter((id) => selectedPersonaSet.has(id)).length,
    [selectedPersonaSet, systemPersonaIds],
  );

  const selectedCustomCount = useMemo(
    () => customPersonaIds.filter((id) => selectedPersonaSet.has(id)).length,
    [customPersonaIds, selectedPersonaSet],
  );

  // -------------------------------------------------------------------------
  // URL validation on blur
  // -------------------------------------------------------------------------

  const handleUrlBlur = useCallback(async () => {
    const url = sourceUrl.trim();
    if (!url) {
      onChange({
        urlValidationStatus: 'idle',
        urlValidationMessage: undefined,
        urlValidationDetails: undefined,
      });
      return;
    }

    validationAbortRef.current?.abort();
    const controller = new AbortController();
    validationAbortRef.current = controller;

    onChange({
      urlValidationStatus: 'validating',
      urlValidationMessage: undefined,
      urlValidationDetails: undefined,
    });

    try {
      const result = await customerApiRequest<{
        normalized_url?: string;
        page_title?: string;
        suggested_objective?: string | null;
        visible_features?: unknown[];
      }>(
        '/api/customer/review-engine/source/validate',
        { method: 'POST', body: JSON.stringify({ source_url: url }) },
      );

      if (controller.signal.aborted) return;

      const validatedUrl = result.normalized_url || url;
      if (!result.normalized_url && !result.page_title) {
        onChange({
          urlValidationStatus: 'invalid',
          urlValidationMessage: 'This URL could not be validated.',
          urlValidationDetails: undefined,
        });
        return;
      }

      onChange({
        urlValidationStatus: 'valid',
        urlValidationMessage: result.page_title
          ? `Source validated: ${result.page_title}`
          : `Source validated: ${validatedUrl}`,
        urlValidationDetails: {
          normalizedUrl: validatedUrl,
          pageTitle: result.page_title,
          suggestedObjective: result.suggested_objective,
          visibleFeatureCount: result.visible_features?.length ?? 0,
        },
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : 'Validation failed';
      onChange({
        urlValidationStatus: 'invalid',
        urlValidationMessage: msg,
        urlValidationDetails: undefined,
      });
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

  const togglePersonaGroup = useCallback((group: 'system' | 'custom') => {
    setExpandedPersonaGroups((current) => ({
      ...current,
      [group]: !current[group],
    }));
  }, []);

  const renderPersonaOption = useCallback((persona: Persona) => {
    const selected = selectedPersonaSet.has(persona.persona_id);
    const imageUrl = persona.selection_image_url || persona.avatar_image_url;
    const regionLabel = persona.region_label || formatMarketLabel(persona.market_default) || 'Global';
    const languageLabel = persona.language || 'Language not set';
    const voiceLabel = persona.tts_voice || 'Voice not set';
    const statusLabel = persona.status || 'draft';
    const toneLabel = persona.tone_default ? formatMarketLabel(persona.tone_default) : null;

    return (
      <button
        key={persona.persona_id}
        type="button"
        onClick={() => togglePersona(persona.persona_id)}
        aria-pressed={selected}
        className={`cv-persona-option${selected ? ' cv-persona-option--selected' : ''}`}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={persona.display_name}
            className="cv-persona-avatar"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <div className="cv-persona-avatar-fallback">
            {persona.display_name.charAt(0).toUpperCase()}
          </div>
        )}

        <span className="cv-persona-body">
          <span className="cv-persona-title-row">
            <span className={`cv-persona-name${selected ? ' cv-persona-name--selected' : ''}`}>
              {persona.display_name}
            </span>
            <span className={`cv-persona-status${statusLabel === 'ready' ? ' cv-persona-status--ready' : ''}`}>
              {formatMarketLabel(statusLabel)}
            </span>
          </span>
          <span className="cv-persona-meta-line">{regionLabel}</span>
          <span className="cv-persona-detail-grid">
            <span>{languageLabel}</span>
            <span>{voiceLabel}</span>
            <span>{persona.video_count || 0} videos</span>
            {toneLabel && <span>{toneLabel}</span>}
          </span>
        </span>

        {selected && (
          <span className="cv-persona-check" aria-hidden="true">✓</span>
        )}
      </button>
    );
  }, [selectedPersonaSet, togglePersona]);

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
                    onChange({
                      sourceUrl: e.target.value,
                      urlValidationStatus: 'idle',
                      urlValidationMessage: undefined,
                      urlValidationDetails: undefined,
                    })
                  }
                  onBlur={handleUrlBlur}
                  className="cv-input"
                />
                {urlValidationStatus === 'validating' && (
                  <span className="cv-spinner" aria-label="Validating" />
                )}
              </div>
              {urlValidationStatus === 'valid' && urlValidationMessage && (
                <div className="cv-validation-details">
                  <p className="cv-validation-msg cv-validation-msg--valid">✓ {urlValidationMessage}</p>
                  {urlValidationDetails && (
                    <div className="cv-validation-detail-grid">
                      {urlValidationDetails.normalizedUrl && (
                        <span><strong>Normalized URL</strong>{urlValidationDetails.normalizedUrl}</span>
                      )}
                      {urlValidationDetails.pageTitle && (
                        <span><strong>Page title</strong>{urlValidationDetails.pageTitle}</span>
                      )}
                      <span>
                        <strong>Visible features</strong>
                        {urlValidationDetails.visibleFeatureCount ?? 0} found
                      </span>
                      {urlValidationDetails.suggestedObjective && (
                        <span><strong>Suggested objective</strong>{urlValidationDetails.suggestedObjective}</span>
                      )}
                    </div>
                  )}
                </div>
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
                <div className="cv-persona-group">
                  <div className="cv-persona-group-header">
                    <button
                      type="button"
                      className="cv-persona-group-toggle"
                      onClick={() => togglePersonaGroup('system')}
                      aria-expanded={expandedPersonaGroups.system}
                      aria-controls="cv-system-personas"
                    >
                      <span className={`cv-toggle-chevron${expandedPersonaGroups.system ? ' cv-toggle-chevron--open' : ''}`}>▼</span>
                      <span>
                        <span className="cv-persona-group-title">System Personas</span>
                        <span className="cv-persona-group-subtitle">
                          {systemPersonas.length} available · {selectedSystemCount} selected
                        </span>
                      </span>
                    </button>
                    <button
                      type="button"
                      className="cv-persona-action-btn"
                      disabled={systemPersonas.length === 0}
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
                  {expandedPersonaGroups.system && (
                    <div id="cv-system-personas" className="cv-persona-list">
                      {systemPersonas.length > 0 ? (
                        systemPersonas.map(renderPersonaOption)
                      ) : (
                        <div className="cv-empty-box">No system personas available.</div>
                      )}
                    </div>
                  )}
                </div>

                <div className="cv-persona-group">
                  <div className="cv-persona-group-header">
                    <button
                      type="button"
                      className="cv-persona-group-toggle"
                      onClick={() => togglePersonaGroup('custom')}
                      aria-expanded={expandedPersonaGroups.custom}
                      aria-controls="cv-custom-personas"
                    >
                      <span className={`cv-toggle-chevron${expandedPersonaGroups.custom ? ' cv-toggle-chevron--open' : ''}`}>▼</span>
                      <span>
                        <span className="cv-persona-group-title">Customer Personas</span>
                        <span className="cv-persona-group-subtitle">
                          {customPersonas.length} available · {selectedCustomCount} selected
                        </span>
                      </span>
                    </button>
                    <button
                      type="button"
                      className="cv-persona-action-btn"
                      disabled={customPersonas.length === 0}
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
                  {expandedPersonaGroups.custom && (
                    <div id="cv-custom-personas" className="cv-persona-list">
                      {customPersonas.length > 0 ? (
                        customPersonas.map(renderPersonaOption)
                      ) : (
                        <div className="cv-empty-box">
                          No customer personas yet. Create one in the Personas tab.
                        </div>
                      )}
                    </div>
                  )}
                </div>
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
                  className={`cv-gesture-chip${selectedMovementStyle === style ? ' cv-gesture-chip--selected' : ''}`}
                  onClick={() => {
                    onChange({ selectedMovementStyle: style });
                    toast.success(`Movement style: ${style}`);
                  }}
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
                  className={`cv-bgm-mood-card${selectedMusicMood === mood ? ' cv-bgm-mood-card--selected' : ''}`}
                  onClick={() => {
                    onChange({ selectedMusicMood: mood });
                    toast.success(`Music mood: ${mood}`);
                  }}
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

        {/* ============== SECTION 6: Persona Background (Optional) ============== */}
        <div className="cv-section-card">
          <div className="cv-section-header">
            <h3 className="cv-section-title">
              Persona Background
              <span className="cv-section-badge cv-section-badge--optional">Optional</span>
            </h3>
          </div>
          <div className="cv-section-content">
            <p className="cv-field-label" style={{ fontSize: '13px', color: '#5c5c58', marginBottom: '8px' }}>
              Choose background style behind persona
            </p>
            <div className="cv-gesture-chips">
              {backgroundOptions.map((bg) => (
                <button
                  key={bg.id}
                  type="button"
                  className={`cv-gesture-chip${selectedBackground === bg.id ? ' cv-gesture-chip--selected' : ''}`}
                  onClick={() => {
                    onChange({ selectedBackground: bg.id });
                    toast.success(`Persona background: ${bg.label}`);
                  }}
                >
                  {bg.label}
                </button>
              ))}
            </div>
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

function formatMarketLabel(value?: string | null): string {
  const cleaned = String(value || '').trim();
  if (!cleaned) return '';
  return cleaned
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

const SYSTEM_PERSONA_USER_ID = '00000000-0000-0000-0000-000000000001';

function isSystemPersona(persona: Persona): boolean {
  return (
    !persona.user_id ||
    persona.user_id === SYSTEM_PERSONA_USER_ID ||
    Boolean(persona.is_preset_catalog)
  );
}
