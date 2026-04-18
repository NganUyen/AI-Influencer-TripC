'use client';

import type { CreateVideoSetupState, VideoCreationMode } from '@/types/video-planning';

const MODE_LABELS: Record<VideoCreationMode, string> = {
  ai_auto: 'AI Auto-Record',
  ai_remote: 'AI Remote Recording',
  human_phone: 'Human Phone Recording',
};

interface CreateVideoSummaryPanelProps {
  setupState: CreateVideoSetupState;
}

export function CreateVideoSummaryPanel({ setupState }: CreateVideoSummaryPanelProps) {
  const {
    sourceUrl,
    urlValidationStatus,
    urlValidationMessage,
    urlValidationDetails,
    selectedPersonaIds,
    selectedMode,
    selectedBackground,
    selectedMovementStyle,
    gestureIntensity,
    selectedMusicMood,
    musicVolume,
    brief,
  } = setupState;

  const domainLabel = extractDomain(sourceUrl) || '-';
  const personaCount = selectedPersonaIds.length;
  const modeLabel = MODE_LABELS[selectedMode] ?? '-';
  const isSourceReady = urlValidationStatus === 'valid';
  const isPersonaReady = personaCount > 0;
  const completedItems = [isSourceReady, isPersonaReady, Boolean(selectedMode)].filter(Boolean).length;
  const readinessLabel = completedItems === 3 ? 'Ready to review' : `${completedItems}/3 complete`;
  const readinessClass = completedItems === 3 ? 'cv-summary-status--ready' : 'cv-summary-status--pending';
  const hintLabel = completedItems === 3
    ? 'Review your plan when the setup feels right.'
    : 'Complete the required source and persona choices.';

  const validationLabel =
    urlValidationStatus === 'idle'       ? '-' :
    urlValidationStatus === 'validating' ? 'Validating...' :
    urlValidationStatus === 'valid'      ? 'Valid' :
                                           'Invalid';

  const validationClass =
    urlValidationStatus === 'valid'      ? 'cv-summary-value--valid' :
    urlValidationStatus === 'invalid'    ? 'cv-summary-value--invalid' :
    urlValidationStatus === 'validating' ? 'cv-summary-value--loading' :
                                           'cv-summary-value--empty';

  return (
    <aside className="cv-summary-panel">
      <div className="cv-summary-header">
        <span className="cv-summary-eyebrow">Create Video</span>
        <h3 className="cv-summary-heading">Setup Summary</h3>
        <div className={`cv-summary-status ${readinessClass}`}>
          <span className="cv-summary-status-dot" aria-hidden="true" />
          <span>{readinessLabel}</span>
        </div>
      </div>

      <div className="cv-summary-progress" aria-label={`${completedItems} of 3 setup items complete`}>
        <span className={isSourceReady ? 'cv-summary-progress-step cv-summary-progress-step--done' : 'cv-summary-progress-step'} />
        <span className={isPersonaReady ? 'cv-summary-progress-step cv-summary-progress-step--done' : 'cv-summary-progress-step'} />
        <span className="cv-summary-progress-step cv-summary-progress-step--done" />
      </div>

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

        {urlValidationStatus === 'valid' && urlValidationDetails && (
          <>
            {urlValidationDetails.pageTitle && (
              <SummaryRow label="Page" value={urlValidationDetails.pageTitle} />
            )}
            <SummaryRow
              label="Features"
              value={`${urlValidationDetails.visibleFeatureCount ?? 0} found`}
            />
          </>
        )}

        <SummaryRow
          label="Personas"
          value={personaCount === 0 ? '-' : `${personaCount} selected`}
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
          label="Gesture"
          value={`${gestureIntensity}%`}
        />

        <SummaryRow
          label="Music"
          value={selectedMusicMood || '—'}
        />

        <SummaryRow
          label="Volume"
          value={`${musicVolume}%`}
        />

        {brief?.trim() && (
          <SummaryRow
            label="Brief"
            value={brief.trim()}
          />
        )}
      </div>

      <hr className="cv-summary-divider" />

      <p className="cv-summary-hint">{hintLabel}</p>
    </aside>
  );
}

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

function extractDomain(url: string): string {
  if (!url) return '';
  try {
    const parsed = new URL(url.startsWith('http') ? url : `https://${url}`);
    return parsed.hostname;
  } catch {
    return url.length > 32 ? `${url.slice(0, 32)}...` : url;
  }
}
