'use client';

import '@/app/create-video.css';
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
    simulateRenderProgress(approved, (items) => {
      setProgressItems(items);
    });
  };

  const goBack = (toStep: Step) => setCurrentStep(toStep);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
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
    <div className="cv-step-indicator" role="list" aria-label="Progress steps">
      {STEP_LABELS.map((label, idx) => {
        const stepNum = (idx + 1) as Step;
        const isCompleted = currentStep > stepNum;
        const isActive    = currentStep === stepNum;

        const circleClass = [
          'cv-step-circle',
          isActive     ? 'cv-step-circle--active' : '',
          isCompleted  ? 'cv-step-circle--done'   : '',
        ].filter(Boolean).join(' ');

        const labelClass = [
          'cv-step-label',
          isActive    ? 'cv-step-label--active' : '',
          isCompleted ? 'cv-step-label--done'   : '',
        ].filter(Boolean).join(' ');

        return (
          <div key={label} className="cv-step-item" role="listitem">
            {/* Step node */}
            <div className="cv-step-node">
              <div className={circleClass} aria-current={isActive ? 'step' : undefined}>
                {isCompleted ? '✓' : stepNum}
              </div>
              <span className={labelClass}>{label}</span>
            </div>

            {/* Connector line */}
            {idx < 2 && (
              <div
                aria-hidden="true"
                className={`cv-step-connector${isCompleted ? ' cv-step-connector--done' : ''}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
