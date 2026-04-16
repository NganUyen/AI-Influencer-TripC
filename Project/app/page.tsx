"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import aiAvatarImage from "./dashboard/ai-avatar.webp";

import { LandingHeader } from "@/components/layout/LandingHeader";
import { BaseButton } from "@/components/landing/BaseButton";
import { BaseCard } from "@/components/landing/BaseCard";
import { PersonaOptionCard } from "@/components/landing/PersonaOptionCard";
import { StatusBadge } from "@/components/landing/StatusBadge";
import { Footer } from "@/components/landing/Footer";

const personas = [
  {
    id: "basic-american-host",
    img: "https://lh3.googleusercontent.com/aida-public/AB6AXuBfStrPhBXQvwYbJR4cG1oLcOEISkZBiXs7y8agPanzui9q3iyoOCEAZY8p44efWhmT_llXjlpyEnt5te5IsLze_3EOnXjN1H0e53ymZZI9JzCd39QasE-APa0Z9oH_BJhNkGnh_D7enhJzmh9gMVjhYZhezoBFID_Zje5OwdF9zvR4DG4Pl53K1ZhfcqdyaNnO1LXsJsBn_PSvlrqNvEij4I1rg0Me3yzHUP7cy1BHb6iKGktIzJt6tQB5yHzAs7AOZ2qkBYpslOY",
    lang: "English",
    category: "Lifestyle & Tech",
    active: true,
  },
  {
    id: "basic-chinese-host",
    img: "https://lh3.googleusercontent.com/aida-public/AB6AXuAEehgjQNiAYTpI2oJzE5dbujH7PTC-4BkSLcYZdGp5OkEAuoPZpFpXSFVKRdEe5tdWLMD64T7gMQMad0yv1usEqrBiBXoLN9CYQIg7MI0YkQWmgNAKkwhUldxv-aNeFc2JsBgdMIiRptgag0rCgXOljZe2zCYQ_xMKAm5eK40lpjGth1ZzTHKaytkF1ow2gUyp4nHfVZJCv2fwvNCfpt56rTLg6h734Viq6FAq0PImh5P8Qa-S51As6IW2RHhcT5AIpPytwnFyND8",
    lang: "Chinese",
    category: "Gaming & Viral",
  },
  {
    id: "basic-latin-host",
    img: "https://lh3.googleusercontent.com/aida-public/AB6AXuCXjK_FceHz3d4Jb3lbuRK1LMPumbRQ-2VaQ3pqibpICuY-fLLhbpo2xmv5iHMXQE2-0iU_1NnswjTN28ukjiQpIoy4wA6yMB7c6jottg_ztm3wIvsqLl24r2u-sIBLr-UuZ8Qjn6Tp-IQqKJwI8SlqBmkuEphVw4X-DQeoMPs24fUXyHd5IsgH3sZEDi5w3s1EDCFEGEWO8U7I0R6XMwq3WnKKl6F4qxokPKFEt_URo6QvTOwLyHogxEZ4gc4aSiLfqBhweYN12H0",
    lang: "Spanish",
    category: "Travel & Social",
  },
  {
    id: "basic-muslim-host",
    img: "https://lh3.googleusercontent.com/aida-public/AB6AXuB-fvcwqBLACyUyHzbIvUiq7Fmw2RaFhqoQo6MoL4_zcjrRPa5OBswgbfWqhc06jke785Et2bvTXYhjN752lBPQL4zZXHWtgbq_H2EpIVnRxU9G5uUA4EN54Zb7sAoP8iiNM-aTNMW9p1z8bv0z7lkO4LI7TQg8VAOSOMZpjsUVeuoydoCtpUA5CxExHNdDp0wZxabtnFgaJD6S_9ZDIZQU0_OI25vI1e_mJKDRUYe0E1-5DAEpXA5E_gVtdxxqGeTkMv9QLzoFo_k",
    lang: "Arabic",
    category: "Business & Fin",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [sourceUrl, setSourceUrl] = useState("");
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<string[]>(
    personas.filter((persona) => persona.active).map((persona) => persona.id),
  );

  const dashboardNextPath = useMemo(() => {
    const params = new URLSearchParams();
    params.set("dashboard_tab", "create_video");
    if (sourceUrl.trim()) {
      params.set("review_source_url", sourceUrl.trim());
    }
    if (selectedPersonaIds.length > 0) {
      params.set("review_personas", selectedPersonaIds.join(","));
    }
    return `/dashboard?${params.toString()}`;
  }, [selectedPersonaIds, sourceUrl]);

  const handleGenerate = () => {
    router.push(`/auth?next=${encodeURIComponent(dashboardNextPath)}`);
  };

  const handleCreateOwnPersona = () => {
    router.push(
      `/auth?next=${encodeURIComponent("/dashboard?dashboard_tab=skills")}`,
    );
  };

  const handleTogglePersona = (personaId: string) => {
    setSelectedPersonaIds((current) =>
      current.includes(personaId)
        ? current.filter((id) => id !== personaId)
        : [...current, personaId],
    );
  };

  return (
    <div className="surface-page min-h-screen bg-background font-body text-on-background selection:bg-primary-container/20 selection:text-on-primary-container">
      <LandingHeader showCTA={true} />

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 md:py-16 lg:px-8 lg:py-24">
        {/* Hero Section */}
        <div className="mb-16 text-center animate-fade-in">
          <h1 className="mb-6 bg-gradient-to-br from-on-surface to-on-surface-variant bg-clip-text font-headline text-4xl font-extrabold leading-tight tracking-tighter text-transparent sm:text-5xl md:text-6xl">
            Turn any App into a
            <br />
            Global Viral Success
          </h1>
          <p className="mx-auto max-w-2xl text-base leading-relaxed text-on-surface-variant opacity-80 sm:text-lg">
            AI-powered video reviews in 10+ languages. Authentic personas. Instant global reach.
          </p>
        </div>

        {/* CTA Section */}
        <BaseCard padding="xl" className="landing-panel relative z-10 mx-auto mb-20 max-w-3xl">
          <div className="space-y-6">
            {/* URL Input */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-on-surface-variant">App URL</label>
              <div className="flex flex-col gap-3 sm:flex-row sm:gap-3">
                <div className="flex flex-1 items-center gap-3 rounded-lg bg-surface-container px-4 py-3 transition-all duration-300 focus-within:ring-2 focus-within:ring-primary-fixed/20">
                  <span className="material-symbols-outlined shrink-0 text-on-surface-variant">link</span>
                  <input
                    className="min-w-0 flex-1 bg-transparent text-base font-medium text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none sm:text-base"
                    placeholder="Paste App Store or Play Store URL"
                    type="text"
                    value={sourceUrl}
                    onChange={(event) => setSourceUrl(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        handleGenerate();
                      }
                    }}
                  />
                </div>
                <BaseButton
                  variant="primary"
                  size="lg"
                  onClick={handleGenerate}
                  className="shrink-0"
                >
                  Generate
                </BaseButton>
              </div>
            </div>

            {/* Personas Grid */}
            <div className="space-y-3 border-t border-outline-variant/10 pt-6">
              <label className="block text-sm font-medium text-on-surface-variant">Regional Personas</label>
              <div className="grid grid-cols-2 gap-2 xs:grid-cols-2 sm:grid-cols-4">
                {personas.map((persona) => (
                  <PersonaOptionCard
                    key={persona.id}
                    img={persona.img}
                    lang={persona.lang}
                    category={persona.category}
                    active={selectedPersonaIds.includes(persona.id)}
                    onClick={() => handleTogglePersona(persona.id)}
                  />
                ))}
              </div>
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleCreateOwnPersona}
                  className="text-sm font-bold text-primary hover:underline underline-offset-4"
                >
                  Create your own Persona
                </button>
              </div>
            </div>
          </div>
        </BaseCard>

        {/* Features Section */}
        <section className="mb-20">
          <div className="mb-12 text-center">
            <h2 className="mb-4 font-headline text-3xl font-bold text-on-surface sm:text-4xl">
              Why creators choose AI-Influencer
            </h2>
            <p className="mx-auto max-w-lg text-on-surface-variant">
              Everything you need for global viral success
            </p>
          </div>

          <div className="grid gap-6 grid-cols-1 md:grid-cols-3">
            {/* Feature 1 */}
            <BaseCard variant="feature" padding="lg" interactive>
              <div className="space-y-3">
                <span className="material-symbols-outlined fill-1 text-5xl text-primary">psychology</span>
                <h3 className="font-headline text-xl font-bold text-on-surface">Authentic Personas</h3>
                <p className="text-sm leading-relaxed text-on-surface-variant">
                  AI-generated personalities that feel genuinely regional. Micro-expressions, accents, and cultural nuance that resonate with local audiences.
                </p>
              </div>
            </BaseCard>

            {/* Feature 2 */}
            <BaseCard variant="feature" padding="lg" interactive>
              <div className="space-y-3">
                <span className="material-symbols-outlined fill-1 text-5xl text-tertiary">bolt</span>
                <h3 className="font-headline text-xl font-bold text-on-surface">Viral-Ready Scripts</h3>
                <p className="text-sm leading-relaxed text-on-surface-variant">
                  Algorithm-optimized opening hooks analyzed in real-time. The first 3 seconds that stop the scroll and drive engagement.
                </p>
              </div>
            </BaseCard>

            {/* Feature 3 */}
            <BaseCard variant="accent" padding="lg">
              <div className="space-y-3">
                <span className="material-symbols-outlined fill-1 text-5xl">public</span>
                <h3 className="font-headline text-xl font-bold">Instant Distribution</h3>
                <p className="text-sm leading-relaxed text-on-primary/80">
                  Publish to 10+ languages with one click. Global reach from day one. Your app speaks local, everywhere.
                </p>
              </div>
            </BaseCard>
          </div>
        </section>

        {/* Video Preview Section */}
        <section className="mb-24">
          <div className="grid items-center gap-12 lg:gap-16 lg:grid-cols-[1fr_1.1fr]">
            {/* Image Container */}
            <div className="relative mx-auto w-full max-w-sm order-2 lg:order-1 lg:max-w-none">
              <div className="relative overflow-hidden rounded-3xl shadow-2xl">
                {/* Subtle background glow */}
                <div className="absolute -inset-px bg-gradient-to-br from-primary/10 via-transparent to-tertiary/10 rounded-3xl -z-10"></div>

                {/* Main image - minimal styling */}
                <img
                  className="w-full h-auto rounded-3xl object-cover"
                  src={aiAvatarImage.src}
                  alt="Premium AI-Influencer Content Creator"
                  width={aiAvatarImage.width}
                  height={aiAvatarImage.height}
                />

                {/* Subtle top light effect */}
                <div className="absolute inset-0 bg-gradient-to-b from-white/5 via-transparent to-transparent pointer-events-none rounded-3xl"></div>
              </div>
            </div>

            {/* Content Container */}
            <div className="order-1 space-y-8 lg:order-2">
              {/* Enhanced Badge */}
              <div className="flex items-center gap-3">
                <div className="relative">
                  <StatusBadge icon="auto_awesome" tone="primary">
                    Ready to Deploy
                  </StatusBadge>
                  <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-transparent rounded-full blur-xl -z-10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                </div>
              </div>

              {/* Heading & Description */}
              <div className="space-y-4">
                <h2 className="font-headline text-4xl font-bold leading-tight text-on-surface sm:text-5xl lg:text-4xl">
                  From App to Icon
                </h2>
                <p className="text-base text-on-surface-variant leading-relaxed max-w-xl">
                  Transform your product into authentic, culturally resonant video content. Premium regional styles. Algorithm-optimized hooks. Global reach in minutes.
                </p>
              </div>

              {/* CTA Button - Using Landing Page Style */}
              <BaseButton size="lg" variant="primary" fullWidth onClick={() => router.push("/auth")}>
                <span className="material-symbols-outlined">share_windows</span>
                Start Creating
              </BaseButton>
            </div>
          </div>
        </section>
      </main>

      <section className="py-20 md:py-24" id="features">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-16 text-center md:mb-20">
            <h2 className="mb-4 font-headline text-3xl font-bold text-on-surface sm:text-4xl">
              Engineered for Influence
            </h2>
            <p className="mx-auto max-w-xl text-on-surface-variant">
              Built on three core technologies that power authentic global reach.
            </p>
          </div>

          {/* Minimal Numbered Features */}
          <div className="space-y-12 md:space-y-16">
            {/* Feature 1 */}
            <div className="flex gap-6 md:gap-8 lg:gap-12">
              <div className="flex shrink-0 items-start">
                <span className="font-headline text-4xl font-bold text-primary/30">01</span>
              </div>
              <div className="min-w-0 flex-1 pt-1">
                <h3 className="mb-2 font-headline text-xl font-bold text-on-surface md:text-2xl">
                  Digital Soul Engine
                </h3>
                <p className="text-on-surface-variant leading-relaxed">
                  Neural architecture that mirrors micro-expressions, accents, and regional nuance. Every persona feels authentically native to its market.
                </p>
              </div>
            </div>

            {/* Feature 2 */}
            <div className="flex gap-6 md:gap-8 lg:gap-12">
              <div className="flex shrink-0 items-start">
                <span className="font-headline text-4xl font-bold text-secondary/30">02</span>
              </div>
              <div className="min-w-0 flex-1 pt-1">
                <h3 className="mb-2 font-headline text-xl font-bold text-on-surface md:text-2xl">
                  Viral Hooks AI
                </h3>
                <p className="text-on-surface-variant leading-relaxed">
                  Real-time algorithm analysis optimizes the first 3 seconds of every review. The moment that stops the scroll and drives engagement.
                </p>
              </div>
            </div>

            {/* Feature 3 */}
            <div className="flex gap-6 md:gap-8 lg:gap-12">
              <div className="flex shrink-0 items-start">
                <span className="font-headline text-4xl font-bold text-tertiary/30">03</span>
              </div>
              <div className="min-w-0 flex-1 pt-1">
                <h3 className="mb-2 font-headline text-xl font-bold text-on-surface md:text-2xl">
                  Global Distribution
                </h3>
                <p className="text-on-surface-variant leading-relaxed">
                  Publish to 10+ languages instantly. Your content adapts to every market with zero translation friction.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
