'use client';

import type { CreateVideoSetupState, VideoCreationMode } from '@/types/video-planning';

// ---------------------------------------------------------------------------
// Mode label map
// ---------------------------------------------------------------------------

const MODE_LABELS: Record<VideoCreationMode, string> = {
  ai_auto: 'AI tự quay',
  ai_remote: 'AI quay từ máy tính',
  human_phone: 'Người quay từ điện thoại',
};

const VALIDATION_LABELS: Record<CreateVideoSetupState['urlValidationStatus'], string> = {
  idle: '—',
  validating: 'Validating...',
  valid: '✓ Valid',
  invalid: '✗ Invalid',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CreateVideoSummaryPanelProps {
  setupState: CreateVideoSetupState;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVideoSummaryPanel({ setupState }: CreateVideoSummaryPanelProps) {
  const {
    sourceUrl,
    urlValidationStatus,
    urlValidationMessage,
    selectedPersonaIds,
    selectedMode,
  } = setupState;

  const domainLabel = extractDomain(sourceUrl) || '—';
  const personaCount = selectedPersonaIds.length;
  const modeLabel = MODE_LABELS[selectedMode] ?? '—';
  const validationLabel = VALIDATION_LABELS[urlValidationStatus];

  return (
    <aside
      style={{
        background: 'var(--color-surface-secondary, rgba(255,255,255,0.04))',
        border: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.08))',
        borderRadius: '16px',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        position: 'sticky',
        top: '24px',
      }}
    >
      {/* Header */}
      <div>
        <h3
          style={{
            fontSize: '13px',
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
            margin: 0,
          }}
        >
          Summary
        </h3>
      </div>

      {/* Fields */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <SummaryRow label="Source" value={domainLabel} />

        <SummaryRow
          label="Validation"
          value={validationLabel}
          valueStyle={{
            color:
              urlValidationStatus === 'valid'
                ? 'var(--color-success, #86efac)'
                : urlValidationStatus === 'invalid'
                  ? 'var(--color-error, #f87171)'
                  : urlValidationStatus === 'validating'
                    ? 'var(--color-warning, #fde68a)'
                    : 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
          }}
        />

        {urlValidationStatus === 'invalid' && urlValidationMessage && (
          <p
            style={{
              fontSize: '11px',
              color: 'var(--color-error, #f87171)',
              margin: '0 0 0 0',
              lineHeight: 1.5,
            }}
          >
            {urlValidationMessage}
          </p>
        )}

        <SummaryRow
          label="Personas"
          value={personaCount === 0 ? '—' : `${personaCount} selected`}
        />

        <SummaryRow label="Mode" value={modeLabel} />
      </div>

      {/* Divider */}
      <hr
        style={{
          border: 'none',
          borderTop: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.08))',
          margin: 0,
        }}
      />

      {/* Next step hint */}
      <p
        style={{
          fontSize: '12px',
          color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
          margin: 0,
          lineHeight: 1.6,
        }}
      >
        Next step: Review your plan
      </p>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Sub-component
// ---------------------------------------------------------------------------

function SummaryRow({
  label,
  value,
  valueStyle,
}: {
  label: string;
  value: string;
  valueStyle?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: '12px',
      }}
    >
      <span
        style={{
          fontSize: '12px',
          color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
          flexShrink: 0,
          minWidth: '72px',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: '12px',
          color: 'var(--color-on-surface, #f4f4f5)',
          fontWeight: 500,
          textAlign: 'right',
          wordBreak: 'break-all',
          ...valueStyle,
        }}
      >
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function extractDomain(url: string): string {
  if (!url) return '';
  try {
    const parsed = new URL(url.startsWith('http') ? url : `https://${url}`);
    return parsed.hostname;
  } catch {
    return url.length > 32 ? `${url.slice(0, 32)}…` : url;
  }
}

// React import needed for CSSProperties type
import React from 'react';
