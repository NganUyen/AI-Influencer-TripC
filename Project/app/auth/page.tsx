"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import aiAvatarImage from "../dashboard/ai-avatar.webp";

import { getClientTelegramBotLaunchUrl } from "@/lib/public-env";
import { useCustomerAuthStore } from "@/store/customer-auth-store";
import { LandingHeader } from "@/components/layout/LandingHeader";
import { BaseButton } from "@/components/landing/BaseButton";
import { Footer } from "@/components/landing/Footer";

interface TelegramLinkToken {
  start_token: string;
  expires_at: string;
}

interface TelegramLinkCompleteResponse {
  status: "pending" | "authenticated" | "expired";
  expires_at?: string | null;
  authenticated_at?: string | null;
  access_token?: string | null;
  refresh_token?: string | null;
  token_type?: string | null;
  expires_in?: number | null;
  user?: {
    id: string;
    email: string;
    name?: string | null;
    avatar_url?: string | null;
  } | null;
}

async function customerApiRequest<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(endpoint, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }

  return (await response.json()) as T;
}

export default function AuthPage() {
  return (
    <Suspense fallback={<AuthPageFallback />}>
      <AuthPageContent />
    </Suspense>
  );
}

function AuthPageFallback() {
  return (
    <div className="bg-background text-on-surface min-h-screen flex flex-col items-center selection:bg-primary-container/20">
      <main className="flex-1 w-full max-w-5xl mx-auto pt-32 pb-20 px-6">
        <div className="mx-auto max-w-xl rounded-3xl border border-outline-variant/10 bg-surface/70 p-10 text-center shadow-sm backdrop-blur-xl">
          <p className="text-[10px] font-black uppercase tracking-widest text-primary">AI-Influencer Factory</p>
          <h1 className="mt-4 text-3xl font-headline font-bold tracking-tight text-on-surface">
            Preparing authentication
          </h1>
          <p className="mt-4 text-sm text-on-surface-variant">
            Loading your login options...
          </p>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function AuthPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    establishSessionFromAccessToken,
    loginWithTelegram,
    error,
    initialized,
    initialize,
    isAuthenticated,
  } = useCustomerAuthStore((state) => ({
    establishSessionFromAccessToken: state.establishSessionFromAccessToken,
    loginWithTelegram: state.loginWithTelegram,
    error: state.error,
    initialized: state.initialized,
    initialize: state.initialize,
    isAuthenticated: state.isAuthenticated,
  }));

  const [currentStep, setCurrentStep] = useState<"tiktok" | "telegram">("tiktok");
  const [localError, setLocalError] = useState<string | null>(null);
  const [linkToken, setLinkToken] = useState<TelegramLinkToken | null>(null);
  const [isGeneratingToken, setIsGeneratingToken] = useState(false);
  const [isAwaitingTelegram, setIsAwaitingTelegram] = useState(false);
  const [isCompletingSession, setIsCompletingSession] = useState(false);
  const [showQR, setShowQR] = useState(false);

  const telegramSignInUrl = getClientTelegramBotLaunchUrl(
    linkToken?.start_token,
    "TripCInternBot",
  );
  const nextPath = searchParams.get("next") || "/dashboard";

  const resolveNextPath = (value: string | null) => {
    const fallback = "/dashboard";
    const normalized = (value || "").trim();
    if (!normalized.startsWith("/") || normalized.startsWith("//")) {
      return fallback;
    }
    return normalized;
  };

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (initialized && isAuthenticated) {
      router.replace(resolveNextPath(nextPath));
    }
  }, [initialized, isAuthenticated, nextPath, router]);

  useEffect(() => {
    if (!linkToken) {
      setIsAwaitingTelegram(false);
      setIsCompletingSession(false);
      return;
    }

    let cancelled = false;
    let timeoutId: number | undefined;
    const expiresAt = Date.parse(linkToken.expires_at);

    const pollForCompletion = async () => {
      if (cancelled) return;

      if (Number.isFinite(expiresAt) && Date.now() >= expiresAt) {
        setLinkToken(null);
        setIsAwaitingTelegram(false);
        setIsCompletingSession(false);
        setLocalError("Liên kết Telegram đã hết hạn. Vui lòng thử lại.");
        return;
      }

      setIsAwaitingTelegram(true);

      try {
        const payload = await customerApiRequest<TelegramLinkCompleteResponse>(
          "/api/auth/telegram/link/complete",
          {
            method: "POST",
            body: JSON.stringify({ start_token: linkToken.start_token }),
          },
        );

        if (cancelled) return;

        if (payload.status === "authenticated" && payload.access_token) {
          setIsCompletingSession(true);
          await establishSessionFromAccessToken(
            payload.access_token,
            payload.user || null,
            payload.refresh_token || null,
          );
          if (cancelled) return;
          setLinkToken(null);
          setIsAwaitingTelegram(false);
          setIsCompletingSession(false);
          router.replace(resolveNextPath(nextPath));
          return;
        }

        if (payload.status === "expired") {
          setLinkToken(null);
          setIsAwaitingTelegram(false);
          setIsCompletingSession(false);
          setLocalError("Liên kết Telegram đã hết hạn. Vui lòng thử lại.");
          return;
        }

        timeoutId = window.setTimeout(() => {
          void pollForCompletion();
        }, 2000);
      } catch (requestError) {
        if (cancelled) return;
        setIsAwaitingTelegram(false);
        setIsCompletingSession(false);
        timeoutId = window.setTimeout(() => {
          void pollForCompletion();
        }, 4000);
      }
    };

    void pollForCompletion();

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [establishSessionFromAccessToken, linkToken, router]);

  async function handleGenerateTelegramLink() {
    setIsGeneratingToken(true);
    setLocalError(null);
    setIsAwaitingTelegram(false);
    setIsCompletingSession(false);

    try {
      const payload = await customerApiRequest<TelegramLinkToken>(
        "/api/auth/telegram/link/start",
        {
          method: "POST",
          body: JSON.stringify({ expires_in_minutes: 15 }),
        },
      );
      setLinkToken(payload);
      return payload;
    } catch (requestError) {
      setLocalError(
        requestError instanceof Error
          ? requestError.message
          : "Không thể khởi tạo liên kết Telegram",
      );
      return null;
    } finally {
      setIsGeneratingToken(false);
    }
  }

  const handleActionClick = async () => {
    const payload = await handleGenerateTelegramLink();
    if (payload) {
      const url = getClientTelegramBotLaunchUrl(payload.start_token, "TripCInternBot");
      if (url) {
        window.open(url, "_blank");
      }
    }
  };

  const handleQRClick = async () => {
    if (!linkToken) {
       await handleGenerateTelegramLink();
    }
    setShowQR(true);
  };

  if (currentStep === "tiktok") {
    return (
      <div className="bg-background text-on-surface min-h-screen flex flex-col selection:bg-primary-container/20">
        <LandingHeader showCTA={false} />

        <main className="flex-1 w-full flex items-center justify-center px-4 sm:px-6 py-12">
          {/* Card Container - Premium Minimal */}
          <div className="w-full max-w-md rounded-3xl border border-outline-variant/20 bg-surface shadow-sm overflow-hidden">
            {/* Header with Back Button */}
            <div className="px-8 pt-6 pb-4 border-b border-outline-variant/10 flex items-center justify-between">
              <button
                onClick={() => router.push("/")}
                className="flex items-center justify-center w-10 h-10 rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
                aria-label="Return home"
              >
                <span className="material-symbols-outlined" style={{fontSize: '24px'}}>arrow_back</span>
              </button>
              <div className="text-center flex-1">
                <p className="text-xs font-semibold text-primary uppercase tracking-wide">Step 1 / 2</p>
              </div>
              <div className="w-10"></div>
            </div>

            {/* Image Section - Natural 4:3 Ratio */}
            <div style={{ aspectRatio: '4/3' }} className="relative w-full bg-surface-container overflow-hidden">
              <img
                alt="AI-Influencer Avatar"
                className="w-full h-full object-cover"
                src={aiAvatarImage.src}
                width={aiAvatarImage.width}
                height={aiAvatarImage.height}
              />
            </div>

            {/* Content Section - Centered Stack */}
            <div className="p-8 space-y-6">
              {/* Heading Stack */}
              <div className="space-y-3">
                <h1 className="text-3xl sm:text-4xl font-bold font-headline text-on-surface tracking-tight">
                  Connect your TikTok
                </h1>
                <p className="text-sm text-on-surface-variant leading-relaxed">
                  Authorize publishing access to streamline content distribution from your dashboard.
                </p>
              </div>

              {/* Primary CTA - Emphasized */}
              <div className="pt-2">
                <BaseButton
                  variant="primary"
                  size="lg"
                  fullWidth
                  onClick={() => setCurrentStep("telegram")}
                  className="flex items-center justify-center gap-2 h-14"
                >
                  <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.06-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.03 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.9-.32-1.9-.36-2.81-.12-1.09.28-2.06 1.01-2.61 1.98-.44.75-.58 1.63-.51 2.49.07.9.46 1.76 1.1 2.39.69.72 1.67 1.16 2.67 1.2 1.05.07 2.15-.22 2.97-.89.89-.71 1.34-1.84 1.3-2.97.03-4.32.01-8.64.02-12.96z"></path>
                  </svg>
                  Sign in with TikTok
                </BaseButton>
              </div>

              {/* Trust Indicators - Compact */}
              <div className="space-y-2 pt-2">
                <div className="flex gap-2">
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                    <span className="material-symbols-outlined text-primary" style={{fontSize: '18px'}}>verified</span>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-on-surface">Official OAuth2</p>
                    <p className="text-[11px] text-on-surface-variant">Password never shared</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                    <span className="material-symbols-outlined text-primary" style={{fontSize: '18px'}}>lock</span>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-on-surface">Enterprise Security</p>
                    <p className="text-[11px] text-on-surface-variant">End-to-end encrypted</p>
                  </div>
                </div>
              </div>

              {/* Footer Links */}
              <div className="flex items-center justify-center gap-4 pt-4 border-t border-outline-variant/10 text-center">
                <Link href="/" className="text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors">
                  Return home
                </Link>
                <span className="text-outline-variant/30">•</span>
                <a href="#" className="text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors">
                  Privacy
                </a>
              </div>
            </div>
          </div>
        </main>

        <Footer />
      </div>
    );
  }

  // Telegram Authentication Step (Step 2)
  return (
    <div className="bg-background text-on-surface min-h-screen flex flex-col selection:bg-primary-container/20">
      <LandingHeader showCTA={false} />

      <main className="flex-1 w-full flex items-center justify-center px-4 sm:px-6 py-12">
        {/* Card Container - Consistent with TikTok */}
        <div className="w-full max-w-md rounded-3xl border border-outline-variant/20 bg-surface shadow-sm overflow-hidden">
          {/* Header with Back Button */}
          <div className="px-8 pt-6 pb-4 border-b border-outline-variant/10 flex items-center justify-between">
            <button
              onClick={() => setCurrentStep("tiktok")}
              className="flex items-center justify-center w-10 h-10 rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
              aria-label="Back to TikTok"
            >
              <span className="material-symbols-outlined" style={{fontSize: '24px'}}>arrow_back</span>
            </button>
            <div className="text-center flex-1">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">Step 2 / 2</p>
            </div>
            <div className="w-10"></div>
          </div>

          {/* Content Section - Stacked */}
          <div className="p-8 space-y-5">
            {/* Heading Stack */}
            <div className="space-y-3">
              <h1 className="text-3xl sm:text-4xl font-bold font-headline text-on-surface tracking-tight">
                Connect Telegram
              </h1>
              <p className="text-sm text-on-surface-variant leading-relaxed">
                Receive real-time notifications and manage your creator fleet directly from Telegram.
              </p>
            </div>

            {/* Benefits Grid */}
            {!showQR && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Benefit 1 */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                      <span className="material-symbols-outlined fill-1 text-primary" style={{ fontSize: '18px' }}>bolt</span>
                    </div>
                    <h3 className="text-xs font-semibold text-on-surface">Live Updates</h3>
                  </div>
                  <p className="text-[11px] text-on-surface-variant leading-relaxed">
                    Instant alerts when content goes viral.
                  </p>
                </div>

                {/* Benefit 2 */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                      <span className="material-symbols-outlined fill-1 text-primary" style={{ fontSize: '18px' }}>smart_toy</span>
                    </div>
                    <h3 className="text-xs font-semibold text-on-surface">Fleet Control</h3>
                  </div>
                  <p className="text-[11px] text-on-surface-variant leading-relaxed">
                    Command AI agents via chat.
                  </p>
                </div>
              </div>
            )}

            {/* QR Code or Button Container */}
            {showQR && telegramSignInUrl ? (
              <div className="flex flex-col items-center gap-5 py-6">
                <div className="bg-white p-4 rounded-2xl shadow-lg border border-outline-variant/10">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(telegramSignInUrl)}`}
                    alt="Telegram Login QR"
                    className="w-40 h-40"
                  />
                </div>
                <div className="text-center">
                  <p className="text-xs font-semibold text-on-surface mb-1">Scan with Telegram</p>
                  <p className="text-[11px] text-on-surface-variant mb-4">Open Telegram to scan and sign in</p>
                  <BaseButton
                    variant="ghost"
                    onClick={() => setShowQR(false)}
                  >
                    Back to button method
                  </BaseButton>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <BaseButton
                  variant="primary"
                  size="lg"
                  fullWidth
                  disabled={isGeneratingToken || isAwaitingTelegram}
                  onClick={handleActionClick}
                  className="flex items-center justify-center gap-2 h-14"
                >
                  <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.14-.368.36-.753.36-.49 0-.403-.345-.568-.611l-1.265-4.386-3.12-.961c-.684-.213-.685-.684.15-.984l12.2-4.703c.576-.213 1.074.144.898.942z"/>
                  </svg>
                  {isGeneratingToken ? "Processing..." : "Continue with Telegram"}
                </BaseButton>

                <BaseButton
                  variant="secondary"
                  size="lg"
                  fullWidth
                  onClick={handleQRClick}
                >
                  Scan QR Code Instead
                </BaseButton>

                {/* Trust Footer */}
                <p className="text-[11px] text-on-surface-variant text-center pt-2 px-2 leading-relaxed">
                  By continuing, you agree to receive automated messages. Disable anytime in settings.
                </p>
              </div>
            )}

            {/* Loading State */}
            {(isAwaitingTelegram || isCompletingSession) && (
              <div className="p-2 rounded-lg bg-primary/5 border border-primary/10 text-center">
                <div className="flex items-center justify-center gap-2 mb-1">
                  <div className="w-1 h-1 rounded-full bg-primary animate-pulse"></div>
                  <p className="text-xs font-semibold text-primary">
                    {isCompletingSession ? "Authenticating..." : "Waiting for Telegram"}
                  </p>
                </div>
                <p className="text-[11px] text-on-surface-variant">
                  Press <span className="font-semibold">Start</span> in the Telegram bot.
                </p>
              </div>
            )}

            {/* Error State */}
            {(localError || error) && (
              <div className="p-2 rounded-lg bg-error/10 border border-error/20">
                <p className="text-xs text-error font-semibold">{localError || (error as string)}</p>
              </div>
            )}

            {/* Dev Mode */}
            {process.env.NODE_ENV === "development" && (
              <div className="pt-2 border-t border-outline-variant/10">
                <BaseButton
                  variant="surface"
                  fullWidth
                  onClick={() => {
                    void loginWithTelegram({
                      id: 12345678,
                      first_name: "Dev",
                      last_name: "Tester",
                      username: "dev_tester",
                      auth_date: Math.floor(Date.now() / 1000),
                      hash: "__MOCK_DEV_LOGIN__",
                    });
                  }}
                >
                  Dev: Skip to Dashboard
                </BaseButton>
              </div>
            )}

            {/* Back Button */}
            <div className="text-center pt-2">
              <BaseButton
                variant="ghost"
                onClick={() => setCurrentStep("tiktok")}
                className="flex items-center justify-center gap-1 mx-auto text-sm"
              >
                <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>arrow_back</span>
                Back to TikTok
              </BaseButton>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
