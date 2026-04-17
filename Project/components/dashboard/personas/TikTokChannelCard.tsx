'use client';

import { useState } from 'react';
import type { Persona } from '@/components/customer-dashboard';
import type { TikTokChannelStatusViewModel, TikTokChannelActive, TikTokConnectionState } from '@/types/video-planning';
import { toTikTokChannelStatus } from '@/adapters/tiktok-adapter';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TikTokChannelCardProps {
  persona: Persona;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TikTokChannelCard({ persona }: TikTokChannelCardProps) {
  const [demoBannerVisible, setDemoBannerVisible] = useState(false);
  const [isLoading] = useState(false);
  const [loadError] = useState<string | null>(null);

  // Phase 1: demo fixture; Phase 3: replace with real API call
  const channelStatus: TikTokChannelStatusViewModel = toTikTokChannelStatus(persona);

  const primaryButtonLabel = getPrimaryButtonLabel(
    channelStatus.activeState,
    channelStatus.connectionState,
  );

  const handlePrimaryAction = () => {
    setDemoBannerVisible(true);
  };

  if (isLoading) {
    return <TikTokChannelSkeleton />;
  }

  if (loadError) {
    return (
      <div style={cardStyle}>
        <CardHeader />
        <p
          style={{
            fontSize: '13px',
            color: 'var(--color-error, #f87171)',
            margin: 0,
            padding: '16px 20px',
          }}
        >
          Could not load channel info.
        </p>
      </div>
    );
  }

  return (
    <div style={cardStyle}>
      <CardHeader />

      {/* Demo notice banner */}
      {demoBannerVisible && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
            padding: '12px 20px',
            background: 'rgba(99,102,241,0.08)',
            borderBottom: '1px solid rgba(99,102,241,0.2)',
          }}
        >
          <span
            style={{
              flex: 1,
              fontSize: '12px',
              color: 'var(--color-on-surface-variant, rgba(244,244,245,0.7))',
              lineHeight: 1.6,
            }}
          >
            This action will be available once the backend integration is complete.
          </span>
          <button
            type="button"
            onClick={() => setDemoBannerVisible(false)}
            aria-label="Dismiss"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-on-surface-variant, rgba(244,244,245,0.4))',
              fontSize: '14px',
              padding: '0 4px',
              flexShrink: 0,
              minHeight: '24px',
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Channel info rows */}
      <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <InfoRow label="Status">
          <ActiveStatePill state={channelStatus.activeState} />
        </InfoRow>

        <InfoRow label="Connection">
          <ConnectionStatePill state={channelStatus.connectionState} />
        </InfoRow>

        <InfoRow
          label="Handle"
          value={channelStatus.channelHandle ?? '—'}
        />

        <InfoRow
          label="Display name"
          value={channelStatus.displayName ?? '—'}
        />

        <InfoRow
          label="Last sync"
          value={channelStatus.lastSyncLabel ?? '—'}
        />
      </div>

      {/* Primary action */}
      <div
        style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.06))',
        }}
      >
        <button
          type="button"
          id={`tiktok-action-${persona.persona_id}`}
          onClick={handlePrimaryAction}
          style={{
            padding: '10px 20px',
            borderRadius: '8px',
            border: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.12))',
            background: 'var(--color-surface-secondary, rgba(255,255,255,0.06))',
            color: 'var(--color-on-surface, #f4f4f5)',
            fontSize: '13px',
            fontWeight: 500,
            cursor: 'pointer',
            minHeight: '44px',
            transition: 'background 0.15s ease, border-color 0.15s ease',
          }}
        >
          {primaryButtonLabel}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CardHeader() {
  return (
    <div
      style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.06))',
      }}
    >
      <h4
        style={{
          fontSize: '14px',
          fontWeight: 600,
          color: 'var(--color-on-surface, #f4f4f5)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        {/* TikTok wordmark icon */}
        <span style={{ fontSize: '16px' }}>𝕋</span>
        TikTok Channel
      </h4>
    </div>
  );
}

function InfoRow({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        minHeight: '24px',
      }}
    >
      <span
        style={{
          fontSize: '12px',
          color: 'var(--color-on-surface-variant, rgba(244,244,245,0.5))',
          flexShrink: 0,
          minWidth: '80px',
        }}
      >
        {label}
      </span>
      {children ?? (
        <span
          style={{
            fontSize: '13px',
            color: value && value !== '—'
              ? 'var(--color-on-surface, #f4f4f5)'
              : 'var(--color-on-surface-variant, rgba(244,244,245,0.35))',
            fontWeight: value && value !== '—' ? 500 : 400,
            textAlign: 'right',
          }}
        >
          {value}
        </span>
      )}
    </div>
  );
}

function ActiveStatePill({ state }: { state: TikTokChannelActive }) {
  const isActive = state === 'active';
  return (
    <span
      style={{
        padding: '3px 10px',
        borderRadius: '999px',
        fontSize: '11px',
        fontWeight: 600,
        color: isActive ? '#86efac' : 'rgba(244,244,245,0.45)',
        background: isActive ? 'rgba(34,197,94,0.12)' : 'rgba(255,255,255,0.06)',
      }}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

function ConnectionStatePill({ state }: { state: TikTokConnectionState }) {
  const config: Record<TikTokConnectionState, { label: string; color: string; bg: string }> = {
    connected_demo: { label: 'Connected (demo)', color: '#fde68a', bg: 'rgba(234,179,8,0.12)' },
    not_connected: { label: 'Not connected', color: 'rgba(244,244,245,0.45)', bg: 'rgba(255,255,255,0.06)' },
    needs_reconnect: { label: 'Needs reconnect', color: '#f87171', bg: 'rgba(239,68,68,0.12)' },
  };
  const cfg = config[state];
  return (
    <span
      style={{
        padding: '3px 10px',
        borderRadius: '999px',
        fontSize: '11px',
        fontWeight: 600,
        color: cfg.color,
        background: cfg.bg,
      }}
    >
      {cfg.label}
    </span>
  );
}

function TikTokChannelSkeleton() {
  return (
    <div style={{ ...cardStyle, padding: '20px' }}>
      <CardHeader />
      <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {[100, 80, 120, 90, 60].map((w, i) => (
          <div
            key={i}
            style={{
              height: '14px',
              width: `${w}%`,
              maxWidth: `${w * 2}px`,
              borderRadius: '6px',
              background: 'var(--color-surface-tertiary, rgba(255,255,255,0.07))',
              animation: 'cv-pulse 1.5s ease-in-out infinite',
            }}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getPrimaryButtonLabel(
  activeState: TikTokChannelActive,
  connectionState: TikTokConnectionState,
): string {
  if (activeState === 'inactive') return 'Activate channel';
  if (connectionState === 'not_connected') return 'Connect TikTok';
  if (connectionState === 'needs_reconnect') return 'Reconnect TikTok';
  return 'View connection details';
}

// ---------------------------------------------------------------------------
// Style constants
// ---------------------------------------------------------------------------

const cardStyle: React.CSSProperties = {
  borderRadius: '16px',
  border: '1px solid var(--color-border-tertiary, rgba(255,255,255,0.08))',
  background: 'var(--color-surface-secondary, rgba(255,255,255,0.03))',
  overflow: 'hidden',
};

import React from 'react';
