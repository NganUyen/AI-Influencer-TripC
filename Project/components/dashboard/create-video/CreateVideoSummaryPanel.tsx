'use client';

import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import type { Persona } from '@/components/customer-dashboard';
import type { CreateVideoSetupState, VideoCreationMode } from '@/types/video-planning';
import {
  getGestureStyleOption,
  getMusicMoodOption,
} from './setup-options';

const MODE_LABELS: Record<VideoCreationMode, string> = {
  ai_auto: 'AI Auto-Record',
  ai_remote: 'AI Remote Recording',
  human_phone: 'Human Phone Recording',
};

interface CreateVideoSummaryPanelProps {
  setupState: CreateVideoSetupState;
  selectedPersonas: Persona[];
  movementPreviewNonce?: number;
  musicPreviewNonce?: number;
}

export function CreateVideoSummaryPanel({
  setupState,
  selectedPersonas,
  movementPreviewNonce = 0,
  musicPreviewNonce = 0,
}: CreateVideoSummaryPanelProps) {
  const {
    sourceUrl,
    urlValidationStatus,
    urlValidationMessage,
    urlValidationDetails,
    selectedPersonaIds,
    selectedMode,
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

  const gestureOption = getGestureStyleOption(selectedMovementStyle);
  const musicOption = getMusicMoodOption(selectedMusicMood);

  const validationLabel =
    urlValidationStatus === 'idle' ? '-' :
      urlValidationStatus === 'validating' ? 'Validating...' :
        urlValidationStatus === 'valid' ? 'Valid' :
          'Invalid';

  const validationClass =
    urlValidationStatus === 'valid' ? 'cv-summary-value--valid' :
      urlValidationStatus === 'invalid' ? 'cv-summary-value--invalid' :
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
            <div className="cv-summary-feature-block">
              <span className="cv-summary-label">Features</span>
              {urlValidationDetails.visibleFeatureCount && urlValidationDetails.visibleFeatureCount > 0 ? (
                <span className="cv-summary-value">
                  {urlValidationDetails.visibleFeatureCount} extracted
                </span>
              ) : (
                <span className="cv-summary-value cv-summary-value--empty">No visible features extracted.</span>
              )}
            </div>
          </>
        )}

        <SummaryRow
          label="Personas"
          value={personaCount === 0 ? '-' : `${personaCount} selected`}
          valueClass={personaCount === 0 ? 'cv-summary-value--empty' : undefined}
        />

        {personaCount > 0 && (
          <div className="cv-summary-persona-list" role="list" aria-label="Selected personas">
            {selectedPersonas.slice(0, 4).map((persona) => {
              const image = persona.selection_image_url || persona.avatar_image_url || '';
              const meta = persona.region_label || persona.language || 'Global';
              return (
                <div key={persona.persona_id} className="cv-summary-persona-chip" role="listitem">
                  {image ? (
                    <img
                      src={image}
                      alt={persona.display_name}
                      className="cv-summary-persona-avatar"
                      loading="lazy"
                      decoding="async"
                    />
                  ) : (
                    <span className="cv-summary-persona-avatar cv-summary-persona-avatar--fallback" aria-hidden="true">
                      {persona.display_name.charAt(0).toUpperCase()}
                    </span>
                  )}
                  <span className="cv-summary-persona-text">
                    <strong>{persona.display_name}</strong>
                    <small>{meta}</small>
                  </span>
                </div>
              );
            })}
            {personaCount > 4 && (
              <span className="cv-summary-persona-more">+{personaCount - 4} more</span>
            )}
          </div>
        )}

        <SummaryRow
          label="Mode"
          value={modeLabel}
        />

        <SummaryRow
          label="Movement"
          value={gestureOption?.label || selectedMovementStyle || '-'}
        />

        <SummaryRow
          label="Gesture"
          value={`${gestureIntensity}%`}
        />

        <SummaryRow
          label="Music"
          value={musicOption?.label || selectedMusicMood || '-'}
        />

        <SummaryRow
          label="Volume"
          value={`${musicVolume}%`}
        />

        <div className="cv-summary-demo-card">
          <div className="cv-summary-demo-header">
            <span className="cv-summary-label">Audio Demo</span>
            <span className="cv-summary-demo-meta">
              {musicOption?.demoDurationLabel || 'No sample'}
            </span>
          </div>
          <p className="cv-summary-demo-title">{musicOption?.demoTitle || 'No soundtrack'}</p>
          {musicOption?.demoSrc ? (
            <AudioPreviewPlayer
              key={[
                musicOption.demoSrc,
                musicOption.demoRate,
                musicOption.demoStartSeconds,
              ].join('|')}
              src={musicOption.demoSrc}
              playbackRate={musicOption.demoRate ?? 1}
              startSeconds={musicOption.demoStartSeconds ?? 0}
              demoDurationLabel={musicOption.demoDurationLabel}
              autoPlayToken={`${selectedMusicMood}::${musicPreviewNonce}`}
            />
          ) : (
            <p className="cv-summary-demo-empty">Select a music mood to preview an audio sample.</p>
          )}
        </div>

        <div className="cv-summary-demo-card">
          <div className="cv-summary-demo-header">
            <span className="cv-summary-label">Gesture Demo</span>
            <span className="cv-summary-demo-meta">
              {gestureOption?.demoDurationLabel || 'No sample'}
            </span>
          </div>
          <p className="cv-summary-demo-title">{gestureOption?.demoTitle || gestureOption?.label || selectedMovementStyle || 'Natural'}</p>
          <GestureDemo
            mode={gestureOption?.previewMode || 'natural'}
            intensity={gestureIntensity}
          />
          {gestureOption?.demoSrc ? (
            <AudioPreviewPlayer
              key={[
                gestureOption.demoSrc,
                gestureOption.demoRate,
                gestureOption.demoStartSeconds,
              ].join('|')}
              src={gestureOption.demoSrc}
              playbackRate={gestureOption.demoRate ?? 1}
              startSeconds={gestureOption.demoStartSeconds ?? 0}
              demoDurationLabel={gestureOption.demoDurationLabel}
              autoPlayToken={`${selectedMovementStyle}::${movementPreviewNonce}`}
            />
          ) : (
            <p className="cv-summary-demo-empty">Select a movement style to preview an audio sample.</p>
          )}
          <p className="cv-summary-demo-note">
            {gestureOption?.summary || 'Preview reflects the selected movement style and gesture intensity.'}
          </p>
        </div>

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

function AudioPreviewPlayer({
  src,
  playbackRate,
  startSeconds,
  demoDurationLabel,
  autoPlayToken,
}: {
  src: string;
  playbackRate: number;
  startSeconds: number;
  demoDurationLabel?: string;
  autoPlayToken?: string;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const hasInitializedRef = useRef(false);
  const lastAutoPlayTokenRef = useRef<string | undefined>(undefined);
  const [activeSourceIndex, setActiveSourceIndex] = useState(0);
  const [metadataDuration, setMetadataDuration] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const sourceCandidates = useMemo(() => {
    const candidates = [src];
    if (typeof window !== 'undefined' && src.startsWith('/')) {
      const nextData = (window as Window & {
        __NEXT_DATA__?: { assetPrefix?: string };
      }).__NEXT_DATA__;
      const assetPrefix = String(nextData?.assetPrefix || '').trim();
      if (assetPrefix && assetPrefix !== '/') {
        candidates.push(`${assetPrefix}${src}`);
      }
      const firstPathSegment = window.location.pathname.split('/').filter(Boolean)[0];
      if (firstPathSegment) {
        candidates.push(`/${firstPathSegment}${src}`);
      }
    }
    return Array.from(new Set(candidates));
  }, [src]);

  const activeSource = sourceCandidates[Math.min(activeSourceIndex, sourceCandidates.length - 1)] || src;
  const activeSourceWithVersion = `${activeSource}${activeSource.includes('?') ? '&' : '?'}v=20260420b`;

  useEffect(() => {
    setActiveSourceIndex(0);
    setMetadataDuration(null);
    setLoadError(null);
  }, [src]);

  useEffect(() => {
    const token = String(autoPlayToken || '').trim().toLowerCase();
    if (!hasInitializedRef.current) {
      hasInitializedRef.current = true;
      lastAutoPlayTokenRef.current = token;
      return;
    }
    if (!token || token === lastAutoPlayTokenRef.current) {
      return;
    }
    lastAutoPlayTokenRef.current = token;
    const audio = audioRef.current;
    if (!audio) {
      return;
    }

    const tryPlay = () => {
      audio.playbackRate = Math.max(0.8, Math.min(1.25, playbackRate));
      if (startSeconds > 0) {
        try {
          audio.currentTime = startSeconds;
        } catch {
          // Keep current time if seek is not available yet.
        }
      }
      void audio.play().catch(() => {
        // Browser autoplay policy can still block in some contexts.
      });
    };

    if (audio.readyState >= 2) {
      tryPlay();
      return;
    }
    const onCanPlay = () => {
      tryPlay();
    };
    audio.addEventListener('canplay', onCanPlay, { once: true });
    return () => {
      audio.removeEventListener('canplay', onCanPlay);
    };
  }, [autoPlayToken, playbackRate, startSeconds]);

  return (
    <>
      <audio
        ref={audioRef}
        controls
        preload="metadata"
        src={activeSourceWithVersion}
        className="cv-summary-audio-player"
        playsInline
        onLoadedMetadata={() => {
          const audio = audioRef.current;
          if (!audio) {
            return;
          }
          audio.playbackRate = Math.max(0.8, Math.min(1.25, playbackRate));
          if (Number.isFinite(audio.duration) && audio.duration > 0) {
            setMetadataDuration(audio.duration);
            setLoadError(null);
          }
          if (startSeconds > 0) {
            try {
              audio.currentTime = startSeconds;
            } catch {
              // Ignore metadata timing races.
            }
          }
        }}
        onPlay={() => {
          const audio = audioRef.current;
          if (!audio) {
            return;
          }
          audio.playbackRate = Math.max(0.8, Math.min(1.25, playbackRate));
          if (startSeconds > 0 && audio.currentTime < 0.1) {
            try {
              audio.currentTime = startSeconds;
            } catch {
              // Keep playback at current position if seeking is not available yet.
            }
          }
        }}
        onError={() => {
          if (activeSourceIndex < sourceCandidates.length - 1) {
            setActiveSourceIndex((prev) => prev + 1);
            return;
          }
          setLoadError('Unable to load audio preview from current source.');
        }}
      />
      {loadError ? (
        <p className="cv-summary-demo-empty">
          {loadError}
          {' '}
          Please refresh after the demo files finish syncing.
        </p>
      ) : (
        <p className="cv-summary-demo-empty">
          Demo length:
          {' '}
          {metadataDuration && metadataDuration > 0
            ? formatAudioTime(metadataDuration)
            : (demoDurationLabel || 'loading...')}
        </p>
      )}
    </>
  );
}

function GestureDemo({
  mode,
  intensity,
}: {
  mode: NonNullable<ReturnType<typeof getGestureStyleOption>>['previewMode'];
  intensity: number;
}) {
  const normalized = Math.min(1, Math.max(0.2, intensity / 100));
  const rotate = 2 + (6 * normalized);
  const lift = 1 + (4 * normalized);
  const armSwing = 5 + (15 * normalized);
  const style = {
    '--cv-gesture-rotate': `${rotate.toFixed(2)}deg`,
    '--cv-gesture-rotate-neg': `${(-rotate).toFixed(2)}deg`,
    '--cv-gesture-lift': `${lift.toFixed(2)}px`,
    '--cv-gesture-lift-neg': `${(-lift).toFixed(2)}px`,
    '--cv-gesture-arm-swing': `${armSwing.toFixed(2)}deg`,
    '--cv-gesture-arm-swing-neg': `${(-armSwing).toFixed(2)}deg`,
  } as CSSProperties;

  return (
    <div className={`cv-gesture-demo-stage cv-gesture-demo-stage--${mode}`} style={style} aria-label={`${mode} gesture demo`}>
      <span className="cv-gesture-demo-body" aria-hidden="true">
        <span className="cv-gesture-demo-head" />
        <span className="cv-gesture-demo-arms">
          <span className="cv-gesture-demo-arm cv-gesture-demo-arm--left" />
          <span className="cv-gesture-demo-arm cv-gesture-demo-arm--right" />
        </span>
        <span className="cv-gesture-demo-torso" />
      </span>
    </div>
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

function formatAudioTime(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
