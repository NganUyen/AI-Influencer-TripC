'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'react-hot-toast';
import type {
  CreateVideoSetupState,
  PageReviewPayload,
  ValidationFeatureViewModel,
  VideoCreationMode,
} from '@/types/video-planning';
import type { Persona } from '@/components/customer-dashboard';
import { CreateVideoModeCards } from './CreateVideoModeCards';
import { CreateVideoSummaryPanel } from './CreateVideoSummaryPanel';
import { customerApiRequest } from '@/lib/customer-api';
import { resolveCountryCode } from '@/lib/country-mapping';
import {
  applyAudioLibraryPreviewOverrides,
  GESTURE_STYLE_OPTIONS,
  MUSIC_MOOD_OPTIONS,
  type ReviewEngineAudioLibrary,
} from './setup-options';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CreateVideoSetupStepProps {
  setupState: CreateVideoSetupState;
  onChange: (patch: Partial<CreateVideoSetupState>) => void;
  personas: Persona[];
  systemPersonaOptions?: Persona[];
  customPersonaOptions?: Persona[];
  isSubmitting?: boolean;
  onContinue: () => void;
}

function isProviderLimitMessage(message: string): boolean {
  const normalized = message.trim().toLowerCase();
  return normalized.includes('rate limit')
    || normalized.includes('quota exhausted')
    || normalized.includes('too many requests');
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
  isSubmitting = false,
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
    selectedMovementStyle,
    gestureIntensity,
    selectedMusicMood,
    musicVolume,
  } = setupState;

  const [isBriefExpanded, setIsBriefExpanded] = useState(false);
  const [isFeatureModalOpen, setIsFeatureModalOpen] = useState(false);
  const [musicPreviewNonce, setMusicPreviewNonce] = useState(0);
  const [audioLibrary, setAudioLibrary] = useState<ReviewEngineAudioLibrary | null>(null);
  const [expandedPersonaGroups, setExpandedPersonaGroups] = useState({
    system: true,
    custom: true,
  });
  const validationAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let isCancelled = false;
    (async () => {
      try {
        const result = await customerApiRequest<ReviewEngineAudioLibrary>(
          '/api/customer/review-engine/audio-library',
        );
        if (!isCancelled) {
          setAudioLibrary(result);
        }
      } catch {
        if (!isCancelled) {
          setAudioLibrary(null);
        }
      }
    })();

    return () => {
      isCancelled = true;
    };
  }, []);

  const selectedPersonaSet = useMemo(
    () => new Set(selectedPersonaIds),
    [selectedPersonaIds],
  );

  const { gestureOptions, musicOptions } = useMemo(
    () =>
      applyAudioLibraryPreviewOverrides(
        GESTURE_STYLE_OPTIONS,
        MUSIC_MOOD_OPTIONS,
        audioLibrary,
      ),
    [audioLibrary],
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

  const selectedPersonas = useMemo(
    () =>
      [...systemPersonas, ...customPersonas].filter((persona) =>
        selectedPersonaSet.has(persona.persona_id),
      ),
    [customPersonas, selectedPersonaSet, systemPersonas],
  );

  const getPersonaCountryCode = useCallback((persona: Persona): string | null => {
    return resolveCountryCode(persona.region_label || persona.market_default);
  }, []);

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
        page_review_data?: PageReviewPayload;
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

      const normalizedFeatures = (result.visible_features ?? [])
        .map(coerceValidationFeature)
        .filter((feature): feature is ValidationFeatureViewModel => feature !== null)
        .slice(0, 12);

      onChange({
        urlValidationStatus: 'valid',
        urlValidationMessage: result.page_title
          ? `Source validated: ${result.page_title}`
          : `Source validated: ${validatedUrl}`,
        urlValidationDetails: {
          normalizedUrl: validatedUrl,
          pageTitle: result.page_title,
          suggestedObjective: result.suggested_objective,
          visibleFeatureCount: normalizedFeatures.length,
          visibleFeatures: normalizedFeatures,
          pageReviewData: result.page_review_data || {
            target_url: url,
            normalized_url: validatedUrl,
            page_title: result.page_title,
            suggested_objective: result.suggested_objective,
            visible_features: normalizedFeatures.map((feature) => ({
              label: feature.label,
              summary: feature.summary || '',
              source_url: feature.sourceUrl,
              evidence: feature.evidence || [],
            })),
          },
        },
        objective:
          objective.trim().length > 0
            ? objective
            : result.suggested_objective || objective,
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : 'Validation failed';
      if (isProviderLimitMessage(msg)) {
        toast.error(msg);
      }
      onChange({
        urlValidationStatus: 'invalid',
        urlValidationMessage: msg,
        urlValidationDetails: undefined,
      });
    }
  }, [objective, onChange, sourceUrl]);

  function coerceValidationFeature(item: unknown): ValidationFeatureViewModel | null {
    if (!item || typeof item !== 'object') return null;

    const raw = item as Record<string, unknown>;
    const label = typeof raw.label === 'string'
      ? raw.label.trim()
      : typeof raw.name === 'string'
        ? raw.name.trim()
        : typeof raw.title === 'string'
          ? raw.title.trim()
          : '';
    const summary = typeof raw.summary === 'string'
      ? raw.summary.trim()
      : typeof raw.description === 'string'
        ? raw.description.trim()
        : typeof raw.details === 'string'
          ? raw.details.trim()
          : typeof raw.text === 'string'
            ? raw.text.trim()
            : '';
    const sourceUrl = typeof raw.source_url === 'string'
      ? raw.source_url.trim()
      : typeof raw.sourceUrl === 'string'
        ? raw.sourceUrl.trim()
        : typeof raw.url === 'string'
          ? raw.url.trim()
        : '';

    if (!label && !summary) return null;

    const evidence = Array.isArray(raw.evidence)
      ? raw.evidence.filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
      : undefined;

    return {
      label: label || summary,
      summary: summary || undefined,
      sourceUrl: sourceUrl || undefined,
      evidence,
    };
  }

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
    const countryCode = getPersonaCountryCode(persona);

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
          <span className="cv-persona-meta-line">
            {countryCode ? (
              <span className="cv-persona-country-chip" title={regionLabel} aria-label={regionLabel}>
                <img
                  src={`https://flagcdn.com/${countryCode.toLowerCase()}.svg`}
                  alt=""
                  aria-hidden="true"
                  className="cv-persona-country-flag"
                  loading="lazy"
                  decoding="async"
                />
                <span>{regionLabel}</span>
              </span>
            ) : (
              regionLabel
            )}
          </span>
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
  }, [getPersonaCountryCode, selectedPersonaSet, togglePersona]);

  // -------------------------------------------------------------------------
  // Continue guard
  // -------------------------------------------------------------------------

  const canContinue = urlValidationStatus === 'valid' && selectedPersonaIds.length > 0;
  const visibleFeatures = urlValidationDetails?.visibleFeatures || [];

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
      <div className={`cv-field-form${isSubmitting ? ' cv-field-form--submitting' : ''}`} aria-busy={isSubmitting}>

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
                    {
                      setIsFeatureModalOpen(false);
                      onChange({
                        sourceUrl: e.target.value,
                        urlValidationStatus: 'idle',
                        urlValidationMessage: undefined,
                        urlValidationDetails: undefined,
                      });
                    }
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
                      <div className="cv-validation-feature-panel">
                        <strong>Visible features</strong>
                        {urlValidationDetails.visibleFeatureCount && urlValidationDetails.visibleFeatureCount > 0 ? (
                          <div className="cv-validation-feature-summary-row">
                            <span className="cv-validation-feature-count">
                              {urlValidationDetails.visibleFeatureCount} features extracted
                            </span>
                            <button
                              type="button"
                              className="cv-persona-action-btn"
                              onClick={() => setIsFeatureModalOpen(true)}
                            >
                              View details
                            </button>
                          </div>
                        ) : (
                          <span className="cv-validation-feature-empty">No visible features extracted.</span>
                        )}
                      </div>
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
              {gestureOptions.map((style) => (
                <button
                  key={style.value}
                  type="button"
                  className={`cv-gesture-chip${selectedMovementStyle === style.value ? ' cv-gesture-chip--selected' : ''}`}
                  onClick={() => {
                    onChange({ selectedMovementStyle: style.value });
                    toast.success(`Movement style: ${style.label}`);
                  }}
                >
                  {style.label}
                </button>
              ))}
            </div>

            <p className="cv-field-label" style={{ fontSize: '13px', color: '#5c5c58', marginTop: '12px' }}>
              Gesture Intensity
            </p>
            <div className="cv-input-wrap">
              <input
                type="range"
                min="0"
                max="100"
                value={gestureIntensity}
                onChange={(event) =>
                  onChange({ gestureIntensity: Number(event.target.value) })
                }
                className="cv-slider"
              />
              <span className="cv-char-count">{gestureIntensity}%</span>
            </div>
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
              {musicOptions.map((mood) => (
                <button
                  key={mood.value}
                  type="button"
                  className={`cv-bgm-mood-card${selectedMusicMood === mood.value ? ' cv-bgm-mood-card--selected' : ''}`}
                  onClick={() => {
                    onChange({ selectedMusicMood: mood.value });
                    setMusicPreviewNonce((prev) => prev + 1);
                    toast.success(`Music mood: ${mood.label}`);
                  }}
                  aria-label={`${mood.label} music mood${selectedMusicMood === mood.value ? ' (selected)' : ''}`}
                  aria-pressed={selectedMusicMood === mood.value}
                  title={mood.label}
                >
                  <span className="cv-bgm-mood-icon" aria-hidden="true">♪</span>
                  <span className="cv-bgm-mood-label">{mood.label}</span>
                </button>
              ))}
            </div>

            <p className="cv-field-label" style={{ fontSize: '13px', color: '#5c5c58', marginTop: '12px' }}>
              Volume
            </p>
            <div className="cv-input-wrap">
              <input
                type="range"
                min="0"
                max="100"
                value={musicVolume}
                onChange={(event) =>
                  onChange({ musicVolume: Number(event.target.value) })
                }
                className="cv-slider"
              />
              <span className="cv-char-count">{musicVolume}%</span>
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
            disabled={!canContinue || isSubmitting}
            className={`btn-primary btn-wide cv-review-plan-btn${isSubmitting ? ' cv-review-plan-btn--loading' : ''}`}
          >
            <span className="cv-review-plan-btn__label">
              {isSubmitting ? 'Creating Plans…' : 'Review Plan →'}
            </span>
            {isSubmitting && (
              <span className="cv-review-plan-btn__loader" aria-hidden="true">
                <span className="cv-review-plan-btn__dot" />
                <span className="cv-review-plan-btn__dot" />
                <span className="cv-review-plan-btn__dot" />
              </span>
            )}
          </button>
          {isSubmitting && (
            <p className="cv-cta-loading-hint">Building persona review plans and syncing backend state...</p>
          )}
          {!canContinue && disabledReason && (
            <p className="cv-cta-disabled-reason">{disabledReason}</p>
          )}
        </div>

      </div>

      {/* ===== RIGHT COLUMN: Summary Sidebar (Sticky) ===== */}
      <CreateVideoSummaryPanel
        setupState={setupState}
        selectedPersonas={selectedPersonas}
        musicPreviewNonce={musicPreviewNonce}
        gestureStyleOptions={gestureOptions}
        musicMoodOptions={musicOptions}
      />

      {isFeatureModalOpen && visibleFeatures.length > 0 && (
        <>
          <div
            className="cv-delete-modal-backdrop"
            onClick={() => setIsFeatureModalOpen(false)}
            aria-hidden="true"
          />
          <div
            className="cv-delete-modal-shell"
            role="dialog"
            aria-modal="true"
            aria-label="Visible features details"
          >
            <div className="cv-delete-modal-card">
              <div className="cv-delete-modal-header">
                <div>
                  <h4 className="cv-delete-modal-title">Extracted visible features</h4>
                  <p className="cv-delete-modal-subtitle">
                    {visibleFeatures.length} feature{visibleFeatures.length > 1 ? 's' : ''} detected from the validated source.
                  </p>
                </div>
                <button
                  type="button"
                  className="cv-delete-modal-close"
                  onClick={() => setIsFeatureModalOpen(false)}
                  aria-label="Close features modal"
                >
                  ×
                </button>
              </div>

              <div className="cv-delete-modal-body">
                <div className="cv-validation-feature-list">
                  {visibleFeatures.map((feature) => (
                    <div className="cv-validation-feature-item" key={`${feature.label}-${feature.sourceUrl ?? feature.summary ?? ''}`}>
                      <span className="cv-validation-feature-name">{feature.label}</span>
                      {feature.summary && (
                        <span className="cv-validation-feature-summary">{feature.summary}</span>
                      )}
                      {feature.evidence && feature.evidence.length > 0 && (
                        <div className="cv-validation-feature-evidence">
                          {feature.evidence.slice(0, 3).map((entry, index) => (
                            <span key={`${feature.label}-evidence-${index}`}>{entry}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="cv-delete-modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setIsFeatureModalOpen(false)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </>
      )}
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
    persona.persona_id?.startsWith('global-') ||
    !persona.user_id ||
    persona.user_id === SYSTEM_PERSONA_USER_ID ||
    Boolean(persona.is_preset_catalog)
  );
}
