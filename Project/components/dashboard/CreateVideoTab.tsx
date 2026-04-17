'use client';

import { useEffect, useState } from 'react';
import type { Persona } from '@/components/customer-dashboard';
import type {
  CreateVideoSetupState,
  PersonaPlanCardViewModel,
  CreateVideoProgressViewModel,
} from '@/types/video-planning';
import { DEFAULT_SETUP_STATE } from '@/types/video-planning';
import { toPersonaPlanCards, simulateRenderProgress } from '@/adapters/create-video-adapter';
import { CreateVideoSetupStep } from './create-video/CreateVideoSetupStep';
import { CreateVideoReviewStep } from './create-video/CreateVideoReviewStep';
import { CreateVideoRenderStep } from './create-video/CreateVideoRenderStep';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Step = 1 | 2 | 3;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CreateVideoTabProps {
  personas: Persona[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVideoTab({ personas }: CreateVideoTabProps) {
  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [setupState, setSetupState] = useState<CreateVideoSetupState>(DEFAULT_SETUP_STATE);
  const [planCards, setPlanCards] = useState<PersonaPlanCardViewModel[]>([]);
  const [progressItems, setProgressItems] = useState<CreateVideoProgressViewModel[]>([]);

  // Build a persona lookup map for the adapter
  const personaMap = personas.reduce<Record<string, { name: string; avatarUrl?: string }>>(
    (acc, p) => {
      acc[p.persona_id] = {
        name: p.display_name,
        avatarUrl: p.avatar_image_url ?? undefined,
      };
      return acc;
    },
    {},
  );

  // -------------------------------------------------------------------------
  // Step transitions
  // -------------------------------------------------------------------------

  const goToStep2 = () => {
    const cards = toPersonaPlanCards(setupState.selectedPersonaIds, personaMap);
    setPlanCards(cards);
    setCurrentStep(2);
  };

  const goToStep3 = () => {
    const approved = planCards.filter((c) => c.status === 'approved');
    setProgressItems([]);
    setCurrentStep(3);

    // Start simulated render progress
    const cleanup = simulateRenderProgress(approved, (items) => {
      setProgressItems(items);
    });

    // Cleanup on unmount (not strictly needed for demo but good practice)
    return cleanup;
  };

  const goBack = (toStep: Step) => {
    setCurrentStep(toStep);
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Keyframes for animations */}
      <style>{`
        @keyframes cv-spin {
          to { transform: translateY(-50%) rotate(360deg); }
        }
        @keyframes cv-pulse {
          0%, 100% { box-shadow: 0 0 0 3px rgba(99,102,241,0.25); }
          50% { box-shadow: 0 0 0 6px rgba(99,102,241,0.1); }
        }
      `}</style>

      {/* Step indicator */}
      <StepIndicator currentStep={currentStep} />

      {/* Step content */}
      {currentStep === 1 && (
        <CreateVideoSetupStep
          setupState={setupState}
          onChange={(patch) => setSetupState((s) => ({ ...s, ...patch }))}
          personas={personas}
          onContinue={goToStep2}
        />
      )}

      {currentStep === 2 && (
        <CreateVideoReviewStep
          planCards={planCards}
          onCardsChange={setPlanCards}
          onContinue={goToStep3}
          onBack={() => goBack(1)}
        />
      )}

      {currentStep === 3 && (
        <CreateVideoRenderStep
          progressItems={progressItems}
          onBack={() => goBack(2)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// StepIndicator
// ---------------------------------------------------------------------------

const STEP_LABELS = ['Setup', 'Review Plan', 'Render'];

function StepIndicator({ currentStep }: { currentStep: Step }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0',
      }}
      role="list"
      aria-label="Progress steps"
    >
      {STEP_LABELS.map((label, idx) => {
        const stepNum = (idx + 1) as Step;
        const isCompleted = currentStep > stepNum;
        const isActive = currentStep === stepNum;

        return (
          <div
            key={label}
            role="listitem"
            style={{ display: 'flex', alignItems: 'center', flex: idx < 2 ? 1 : 0 }}
          >
            {/* Step node */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '6px',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '13px',
                  fontWeight: 700,
                  border: isActive
                    ? '2px solid var(--color-primary, #6366f1)'
                    : isCompleted
                      ? '2px solid var(--color-success, #86efac)'
                      : '2px solid var(--color-border-tertiary, rgba(255,255,255,0.15))',
                  background: isActive
                    ? 'var(--color-primary, #6366f1)'
                    : isCompleted
                      ? 'rgba(134,239,172,0.15)'
                      : 'transparent',
                  color: isActive
                    ? '#fff'
                    : isCompleted
                      ? 'var(--color-success, #86efac)'
                      : 'var(--color-on-surface-variant, rgba(244,244,245,0.35))',
                  transition: 'background 0.2s ease, border-color 0.2s ease',
                }}
                aria-current={isActive ? 'step' : undefined}
              >
                {isCompleted ? '✓' : stepNum}
              </div>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive
                    ? 'var(--color-on-surface, #f4f4f5)'
                    : isCompleted
                      ? 'var(--color-success, #86efac)'
                      : 'var(--color-on-surface-variant, rgba(244,244,245,0.35))',
                  whiteSpace: 'nowrap',
                  transition: 'color 0.2s ease',
                }}
              >
                {label}
              </span>
            </div>

            {/* Connector line */}
            {idx < 2 && (
              <div
                aria-hidden="true"
                style={{
                  flex: 1,
                  height: '2px',
                  marginBottom: '18px',
                  marginLeft: '8px',
                  marginRight: '8px',
                  background: isCompleted
                    ? 'var(--color-success, #86efac)'
                    : 'var(--color-border-tertiary, rgba(255,255,255,0.1))',
                  transition: 'background 0.3s ease',
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
