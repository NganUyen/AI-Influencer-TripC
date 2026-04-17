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
    selectedBackground,
    selectedMovementStyle,
    selectedMusicMood,
  } = setupState;

  const domainLabel = extractDomain(sourceUrl) || '—';
  const personaCount = selectedPersonaIds.length;
  const modeLabel = MODE_LABELS[selectedMode] ?? '—';

  const validationLabel =
    urlValidationStatus === 'idle'       ? '—' :
    urlValidationStatus === 'validating' ? 'Validating...' :
    urlValidationStatus === 'valid'      ? '✓ Valid' :
                                           '✗ Invalid';

  const validationClass =
    urlValidationStatus === 'valid'      ? 'cv-summary-value--valid' :
    urlValidationStatus === 'invalid'    ? 'cv-summary-value--invalid' :
    urlValidationStatus === 'validating' ? 'cv-summary-value--loading' :
                                           'cv-summary-value--empty';

  return (
    <aside className="cv-summary-panel">
      {/* Header */}
      <h3 className="cv-summary-heading">Summary</h3>

      {/* Fields */}
      <div className="cv-summary-rows">
        <SummaryRow label="Source" value={domainLabel} />

        <SummaryRow
          label="Validation"
          value={validationLabel}
          valueClass={validationClass}
        />

        {urlValidationStatus === 'invalid' && urlValidationMessage && (
          <p className="cv-validation-msg cv-validation-msg--invalid">{urlValidationMessage}</p>
        )}

        <SummaryRow
          label="Personas"
          value={personaCount === 0 ? '—' : `${personaCount} selected`}
          valueClass={personaCount === 0 ? 'cv-summary-value--empty' : undefined}
        />

        <SummaryRow
          label="Mode"
          value={modeLabel}
        />

        <SummaryRow
          label="Background"
          value={selectedBackground || '—'}
        />

        <SummaryRow
          label="Movement"
          value={selectedMovementStyle || '—'}
        />

        <SummaryRow
          label="Music"
          value={selectedMusicMood || '—'}
        />
      </div>

      <hr className="cv-summary-divider" />

      <p className="cv-summary-hint">Next step: Review your plan</p>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Sub-component
// ---------------------------------------------------------------------------

function SummaryRow({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="cv-summary-row">
      <span className="cv-summary-label">{label}</span>
      <span className={`cv-summary-value ${valueClass ?? ''}`}>{value}</span>
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
