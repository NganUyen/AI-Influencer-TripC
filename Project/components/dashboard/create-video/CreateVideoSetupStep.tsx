'use client';

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

    // Cancel any in-flight validation
    validationAbortRef.current?.abort();
    const controller = new AbortController();
    validationAbortRef.current = controller;

    onChange({ urlValidationStatus: 'validating', urlValidationMessage: undefined });

    try {
      const result = await customerApiRequest<{ valid: boolean; message?: string; domain?: string }>(
        '/api/customer/review-engine/source/validate',
        {
          method: 'POST',
          body: JSON.stringify({ url }),
        },
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
  // Persona selection
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

  const canContinue =
    urlValidationStatus === 'valid' && selectedPersonaIds.length > 0;

  const getDisabledReason = () => {
    if (urlValidationStatus !== 'valid' && selectedPersonaIds.length === 0) {
      return 'Enter a valid source URL and select at least one persona to continue.';
    }
    if (urlValidationStatus !== 'valid') {
      return 'Enter a valid source URL to continue.';
    }
    if (selectedPersonaIds.length === 0) {
      return 'Select at least one persona to continue.';
    }
    return null;
  };

  const disabledReason = getDisabledReason();

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 320px',
        gap: '32px',
        alignItems: 'start',
      }}
      className="create-video-setup-grid"
    >
      {/* ------------------------------------------------------------------ */}
      {/* LEFT — Form                                                          */}
      {/* ------------------------------------------------------------------ */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>

        {/* Source URL */}
        <FieldGroup label="Source URL" required>
          <div style={{ position: 'relative' }}>
            <input
              type="url"
              id="cv-source-url"
              placeholder="https://example.com/product"
              value={sourceUrl}
              onChange={(e) => onChange({ sourceUrl: e.target.value, urlValidationStatus: 'idle', urlValidationMessage: undefined })}
              onBlur={handleUrlBlur}
              style={inputStyle}
            />
            {urlValidationStatus === 'validating' && (
              <span style={inlineSpinnerStyle} aria-label="Validating" />
            )}
          </div>

          {/* Inline validation feedback */}
          {urlValidationStatus === 'valid' && urlValidationMessage && (
            <p style={{ ...validationMsgStyle, color: 'var(--color-success, #86efac)' }}>
              ✓ {urlValidationMessage}
            </p>
          )}
          {urlValidationStatus === 'invalid' && urlValidationMessage && (
            <p style={{ ...validationMsgStyle, color: 'var(--color-error, #f87171)' }}>
              ✗ {urlValidationMessage}
            </p>
          )}
          {urlValidationStatus === 'validating' && (
            <p style={{ ...validationMsgStyle, color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))' }}>
              Validating source...
            </p>
          )}
        </FieldGroup>

        {/* Personas */}
        <FieldGroup label="Personas" required>
          {personas.length === 0 ? (
            <EmptyPersonas />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {personas.map((p) => {
                const selected = selectedPersonaIds.includes(p.persona_id);
                return (
                  <button
                    key={p.persona_id}
                    type="button"
                    onClick={() => togglePersona(p.persona_id)}
                    aria-pressed={selected}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: selected
                        ? '2px solid var(--color-border-info, #3b82f6)'
                        : '1px solid var(--color-border-tertiary, rgba(255,255,255,0.1))',
                      background: selected
                        ? 'var(--color-surface-info-subtle, rgba(59,130,246,0.08))'
                        : 'var(--color-surface-secondary, rgba(255,255,255,0.04))',
                      cursor: 'pointer',
                      textAlign: 'left',
                      minHeight: '44px',
                      transition: 'border-color 0.15s ease, background 0.15s ease',
                    }}
                  >
                    {/* Avatar */}
                    {p.avatar_image_url ? (
                      <img
                        src={p.avatar_image_url}
                        alt={p.display_name}
                        style={{ width: 28, height: 28, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                      />
                    ) : (
                      <div
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: '50%',
                          background: 'var(--color-surface-tertiary, rgba(255,255,255,0.1))',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '12px',
                          fontWeight: 600,
                          color: 'var(--color-on-surface-variant, rgba(244,244,245,0.6))',
                          flexShrink: 0,
                        }}
                      >
                        {p.display_name.charAt(0).toUpperCase()}
                      </div>
                    )}

                    <span
                      style={{
                        fontSize: '13px',
                        fontWeight: selected ? 500 : 400,
                        color: 'var(--color-on-surface, #f4f4f5)',
                        flex: 1,
                      }}
                    >
                      {p.display_name}
                    </span>

                    {/* Check indicator */}
                    {selected && (
                      <span
                        style={{
                          width: 16,
                          height: 16,
                          borderRadius: '50%',
                          background: 'var(--color-border-info, #3b82f6)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          fontSize: '10px',
                          color: '#fff',
                        }}
                        aria-hidden="true"
                      >
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </FieldGroup>

        {/* Objective */}
        <FieldGroup label="Video Objective" required>
          <div style={{ position: 'relative' }}>
            <textarea
              id="cv-objective"
              placeholder="Describe the goal of this video (e.g. drive signups, showcase a feature…)"
              value={objective}
              onChange={(e) =>
                onChange({ objective: e.target.value.slice(0, 200) })
              }
              rows={3}
              style={{ ...inputStyle, resize: 'vertical', minHeight: '80px' }}
            />
            <CharCounter current={objective.length} max={200} />
          </div>
        </FieldGroup>

        {/* Brief — collapsible */}
        <FieldGroup
          label={
            <button
              type="button"
              onClick={() => setIsBriefExpanded((v) => !v)}
              style={{
                background: 'none',
                border: 'none',
                padding: 0,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                color: 'var(--color-on-surface-variant, rgba(244,244,245,0.7))',
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              Brief
              <span
                style={{
                  display: 'inline-block',
                  fontSize: '10px',
                  transition: 'transform 0.15s ease',
                  transform: isBriefExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                }}
              >
                ▼
              </span>
              <span style={{ fontSize: '11px', opacity: 0.5, fontWeight: 400 }}>(optional)</span>
            </button>
          }
        >
          {isBriefExpanded && (
            <div style={{ position: 'relative' }}>
              <textarea
                id="cv-brief"
                placeholder="Any additional context, brand guidelines, or tone requirements…"
                value={brief ?? ''}
                onChange={(e) => onChange({ brief: e.target.value.slice(0, 500) })}
                rows={4}
                style={{ ...inputStyle, resize: 'vertical', minHeight: '96px' }}
              />
              <CharCounter current={(brief ?? '').length} max={500} />
            </div>
          )}
        </FieldGroup>

        {/* Mode */}
        <FieldGroup label="Recording Mode">
          <CreateVideoModeCards
            selectedMode={selectedMode}
            onSelect={(mode: VideoCreationMode) => onChange({ selectedMode: mode })}
          />
        </FieldGroup>

        {/* CTA */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button
            type="button"
            id="cv-continue-btn"
            onClick={canContinue ? onContinue : undefined}
            disabled={!canContinue}
            style={{
              padding: '14px 24px',
              borderRadius: '10px',
              border: 'none',
              background: canContinue
                ? 'var(--color-primary, #6366f1)'
                : 'var(--color-surface-disabled, rgba(255,255,255,0.08))',
              color: canContinue
                ? '#fff'
                : 'var(--color-on-surface-variant, rgba(244,244,245,0.3))',
              fontSize: '14px',
              fontWeight: 600,
              cursor: canContinue ? 'pointer' : 'not-allowed',
              minHeight: '44px',
              transition: 'background 0.15s ease, color 0.15s ease',
              letterSpacing: '0.01em',
            }}
          >
            Review Plan →
          </button>

          {/* Inline disabled reason */}
          {!canContinue && disabledReason && (
            <p
              style={{
                fontSize: '12px',
                color: 'var(--color-on-surface-variant, rgba(244,244,245,0.45))',
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              {disabledReason}
            </p>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* RIGHT — Summary panel                                               */}
      {/* ------------------------------------------------------------------ */}
      <CreateVideoSummaryPanel setupState={setupState} />

      {/* Responsive breakpoint */}
      <style>{`
        @media (max-width: 768px) {
          .create-video-setup-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FieldGroup({
  label,
  required,
  children,
}: {
  label: React.ReactNode;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <label
        style={{
          fontSize: '13px',
          fontWeight: 500,
          color: 'var(--color-on-surface-variant, rgba(244,244,245,0.7))',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
        }}
      >
        {label}
        {required && (
          <span style={{ color: 'var(--color-error, #f87171)', fontSize: '12px' }}>*</span>
        )}
      </label>
      {children}
    </div>
  );
}

function CharCounter({ current, max }: { current: number; max: number }) {
  const nearLimit = current >= max * 0.8;
  return (
    <span
      style={{
        position: 'absolute',
        bottom: '8px',
        right: '10px',
        fontSize: '11px',
        color: nearLimit
          ? 'var(--color-warning, #fde68a)'
          : 'var(--color-on-surface-variant, rgba(244,244,245,0.35))',
        pointerEvents: 'none',
      }}
    >
      {current}/{max}
    </span>
  );
}

function EmptyPersonas() {
  return (
    <div
      style={{
        padding: '24px',
        borderRadius: '10px',
        border: '1px dashed var(--color-border-tertiary, rgba(255,255,255,0.1))',
        textAlign: 'center',
        color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
        fontSize: '13px',
        lineHeight: 1.6,
      }}
    >
      No personas available — create one in the <strong>Personas</strong> tab.
    </div>
  );
}

// ---------------------------------------------------------------------------
// Style constants
// ---------------------------------------------------------------------------

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 14px',
  borderRadius: '10px',
  border: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.1))',
  background: 'var(--color-surface-secondary, rgba(255,255,255,0.04))',
  color: 'var(--color-on-surface, #f4f4f5)',
  fontSize: '14px',
  lineHeight: 1.5,
  outline: 'none',
  boxSizing: 'border-box',
  minHeight: '44px',
  fontFamily: 'inherit',
  transition: 'border-color 0.15s ease',
};

const validationMsgStyle: React.CSSProperties = {
  fontSize: '12px',
  margin: '4px 0 0',
  lineHeight: 1.5,
};

const inlineSpinnerStyle: React.CSSProperties = {
  position: 'absolute',
  right: '12px',
  top: '50%',
  transform: 'translateY(-50%)',
  width: '14px',
  height: '14px',
  border: '2px solid var(--color-border-tertiary, rgba(255,255,255,0.1))',
  borderTopColor: 'var(--color-on-surface-variant, rgba(244,244,245,0.6))',
  borderRadius: '50%',
  animation: 'cv-spin 0.6s linear infinite',
  display: 'inline-block',
};

import React from 'react';
