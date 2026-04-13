"use client";

import { useRouter } from "next/navigation";
import { BaseButton } from "@/components/landing/BaseButton";

interface LandingHeaderProps {
  showCTA?: boolean;
  ctaLabel?: string;
  onCtaClick?: () => void;
}

export function LandingHeader({
  showCTA = true,
  ctaLabel = "Get Started",
  onCtaClick,
}: LandingHeaderProps) {
  const router = useRouter();

  const handleCtaClick = () => {
    if (onCtaClick) {
      onCtaClick();
    } else {
      router.push("/auth");
    }
  };

  return (
    <nav className="sticky top-0 z-50 border-b border-outline-variant/10 bg-surface/70 shadow-sm backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-6 lg:gap-8">
          <span className="font-headline text-xl font-bold tracking-tighter text-on-surface sm:text-2xl">
            AI-Influencer
          </span>
          <div className="hidden gap-6 md:flex">
            <a
              className="font-headline text-sm font-medium tracking-tight text-on-surface-variant transition-colors duration-200 hover:text-primary"
              href="#features"
            >
              Features
            </a>
            <a
              className="font-headline text-sm font-medium tracking-tight text-on-surface-variant transition-colors duration-200 hover:text-primary"
              href="#workflow"
            >
              How it Works
            </a>
          </div>
        </div>
        {showCTA && (
          <BaseButton className="shrink-0" onClick={handleCtaClick}>
            {ctaLabel}
          </BaseButton>
        )}
      </div>
    </nav>
  );
}
