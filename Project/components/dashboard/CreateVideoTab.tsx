'use client';

import '@/app/create-video.css';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Clapperboard, FileCheck2, Play, Settings2, type LucideIcon } from 'lucide-react';
import { toast } from 'react-hot-toast';
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

type Step = 1 | 2 | 3 | 4;

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
  const renderProgressCleanupRef = useRef<(() => void) | null>(null);

  const personaMap = useMemo(
    () => personas.reduce<Record<string, { name: string; avatarUrl?: string }>>((acc, p) => {
      acc[p.persona_id] = {
        name: p.display_name,
        avatarUrl: p.avatar_image_url ?? undefined,
      };
      return acc;
    }, {}),
    [personas],
  );

  const handleSetupChange = useCallback((patch: Partial<CreateVideoSetupState>) => {
    setSetupState((current) => ({ ...current, ...patch }));
  }, []);

  useEffect(() => {
    return () => {
      renderProgressCleanupRef.current?.();
    };
  }, []);

  const stopRenderProgress = useCallback(() => {
    renderProgressCleanupRef.current?.();
    renderProgressCleanupRef.current = null;
  }, []);

  // -------------------------------------------------------------------------
  // Step transitions
  // -------------------------------------------------------------------------

  const goToStep2 = useCallback(() => {
    const cards = toPersonaPlanCards(setupState.selectedPersonaIds, personaMap);
    setPlanCards(cards);
    setCurrentStep(2);
  }, [personaMap, setupState.selectedPersonaIds]);

  const goToStep3 = useCallback(() => {
    const approved = planCards.filter((c) => c.status === 'approved');
    stopRenderProgress();
    setProgressItems([]);
    setCurrentStep(3);
    renderProgressCleanupRef.current = simulateRenderProgress(approved, (items) => {
      setProgressItems(items);
    });
  }, [planCards, stopRenderProgress]);

  const goToStep4 = useCallback(() => {
    stopRenderProgress();
    setCurrentStep(4);
  }, [stopRenderProgress]);

  const goBack = useCallback((toStep: Step) => {
    stopRenderProgress();
    setCurrentStep(toStep);
  }, [stopRenderProgress]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="cv-container">
      {/* Step indicator with new 4-step design */}
      <StepIndicator currentStep={currentStep} />

      {/* Step content with fade-in animation */}
      <div className="cv-step-content">
        {currentStep === 1 && (
          <CreateVideoSetupStep
            setupState={setupState}
            onChange={handleSetupChange}
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
            onContinue={goToStep4}
            onBack={() => goBack(2)}
          />
        )}

        {currentStep === 4 && (
          <PublishStep onBack={() => goBack(3)} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StepIndicator (Enhanced 4-Step Progress Tracker)
// ---------------------------------------------------------------------------

const STEP_CONFIG: Array<{
  label: string;
  detail: string;
  icon: LucideIcon;
}> = [
  {
    label: 'Setup',
    detail: 'Configure source, objective, and persona inputs for generation.',
    icon: Settings2,
  },
  {
    label: 'Review Plan',
    detail: 'Validate storyboard and approve persona-level draft directions.',
    icon: FileCheck2,
  },
  {
    label: 'Render',
    detail: 'Track render progress and monitor timeline status in real time.',
    icon: Clapperboard,
  },
  {
    label: 'Publish',
    detail: 'Finalize channel distribution and push content live.',
    icon: Play,
  },
];

function StepIndicator({ currentStep }: { currentStep: Step }) {
  return (
    <div className="cv-progress-tracker">
      <div className="cv-progress-track" role="progressbar" aria-valuenow={currentStep} aria-valuemin={1} aria-valuemax={4}>
        {STEP_CONFIG.map((step, idx) => {
          const stepNum = (idx + 1) as Step;
          const isCompleted = currentStep > stepNum;
          const isActive = currentStep === stepNum;
          const Icon = step.icon;

          return (
            <div key={step.label} className="cv-progress-step-wrapper">
              {/* Step indicator pill */}
              <div
                className={`cv-progress-step ${isActive ? 'cv-progress-step--active' : ''} ${
                  isCompleted ? 'cv-progress-step--completed' : ''
                }`}
              >
                <Icon className="cv-progress-step-icon" />
                <span className="cv-progress-step-label">{stepNum}. {step.label}</span>
              </div>

              {/* Connector line between steps */}
              {idx < STEP_CONFIG.length - 1 && (
                <div
                  className={`cv-progress-connector ${
                    isCompleted ? 'cv-progress-connector--completed' : ''
                  }`}
                  aria-hidden="true"
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="cv-progress-detail-grid" aria-hidden="true">
        {STEP_CONFIG.map((step, idx) => {
          const stepNum = (idx + 1) as Step;
          const isCurrent = currentStep === stepNum;
          const isCompleted = currentStep > stepNum;
          return (
            <div key={`${step.label}-detail`} className="cv-progress-detail-item">
              <p
                className={`cv-progress-phase ${
                  isCurrent ? 'cv-progress-phase--current' : isCompleted ? 'cv-progress-phase--done' : ''
                }`}
              >
                {isCurrent ? 'Current phase' : isCompleted ? 'Completed' : 'Upcoming'}
              </p>
              <p className="cv-progress-detail-text">{step.detail}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PublishStep (Placeholder for step 4)
// ---------------------------------------------------------------------------

function PublishStep({ onBack }: { onBack: () => void }) {
  return (
    <div className="cv-step-panel">
      <div className="cv-step-content-inner">
        <h2 className="cv-step-title">Ready to Publish</h2>
        <p className="cv-step-subtitle">Your videos are ready to be published to your channels.</p>
        <div className="cv-step-actions">
          <button
            className="btn-primary"
            onClick={() => toast.success('Publish flow is coming soon.')}
          >
            Publish Videos
          </button>
          <button className="btn-secondary" onClick={onBack}>
            Back
          </button>
        </div>
      </div>
    </div>
  );
}
