"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { getClientTelegramBotLaunchUrl } from "@/lib/public-env";
import { useCustomerAuthStore } from "@/store/customer-auth-store";
import { Footer } from "@/components/layout/Footer";

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
          <p className="text-[10px] font-black uppercase tracking-widest text-primary">Aura Influencer</p>
          <h1 className="mt-4 text-3xl font-headline font-bold tracking-tight text-on-surface">
            Preparing authentication
          </h1>
          <p className="mt-4 text-sm text-on-surface-variant">
            Loading your login options...
          </p>
        </div>
      </main>
      <Footer variant="page" />
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
      <div className="bg-background text-on-surface min-h-screen flex flex-col items-center selection:bg-primary-container/20">
        <nav className="fixed top-0 left-0 right-0 z-50 bg-surface/70 backdrop-blur-2xl shadow-sm border-b border-outline-variant/10">
          <div className="flex justify-between items-center w-full px-8 py-4 max-w-7xl mx-auto">
            <div className="text-2xl font-bold bg-gradient-to-r from-primary to-primary-container bg-clip-text text-transparent font-headline tracking-tighter">
              Aura Influencer
            </div>
            <div className="hidden md:flex items-center gap-8">
              <Link href="/" className="text-on-surface/60 font-headline font-semibold tracking-tight hover:text-primary transition-all px-3 py-1 rounded-full">Trang chủ</Link>
              <a className="text-on-surface/60 font-headline font-semibold tracking-tight hover:text-primary transition-all px-3 py-1 rounded-full" href="#">Creators</a>
              <a className="text-on-surface/60 font-headline font-semibold tracking-tight hover:text-primary transition-all px-3 py-1 rounded-full" href="#">Community</a>
            </div>
            <div className="w-10 h-10 rounded-full border-2 border-primary-fixed overflow-hidden bg-surface-container">
               <span className="material-symbols-outlined text-on-surface-variant flex items-center justify-center h-full">person</span>
            </div>
          </div>
        </nav>

        <main className="flex-1 w-full max-w-5xl mx-auto pt-32 pb-20 px-6">
          <div className="flex flex-col lg:flex-row gap-12 items-center lg:items-stretch">
            {/* Persona Preview Section */}
            <div className="w-full lg:w-5/12 flex flex-col">
              <div className="relative w-full aspect-[4/5] rounded-xl overflow-hidden shadow-2xl group border border-outline-variant/5">
                <img 
                  alt="Persona imagery" 
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" 
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuDoI-4UWj9wonx_1HEZUxb4h_H2LFWZZGaBSJ-VztevBW1-h_EiqPO1OCTc-A3SiCk6M6qp1ZZLwYGoqaviKBPSY8Hl1OqFV9Mb4TPz0SaFom5jyM8VJMDezGDdXv6VA_NmiVT7pJB7ptr-KVsgJ2Cw55jBI1en9CZgqZ9MJhIEidxJKoWXhNEHhNqQzCfkLB8c4348KsdbauqHYkbFclQooGnfow39ceBNm5UuzppDWrNJYU_Gmdf2o0_ft8uRYl3SiU8QHMDD3Zw" 
                />
                <div className="absolute bottom-0 left-0 right-0 p-8 m-4 rounded-lg bg-surface/70 backdrop-blur-2xl border border-white/20">
                  <div className="flex justify-between items-end">
                    <div>
                      <span className="text-xs font-bold text-primary uppercase tracking-widest font-headline">Ready to Publish</span>
                      <h3 className="text-2xl font-extrabold text-on-surface font-headline mt-1">Elena V.</h3>
                      <p className="text-sm text-on-surface-variant">Lifestyle & Minimalist Aesthetics</p>
                    </div>
                    <div className="flex flex-col items-end">
                      <span className="text-xs text-on-surface-variant font-medium">Platform Reach</span>
                      <span className="text-lg font-bold text-on-surface">124k Est.</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-8 p-6 bg-surface-container-low rounded-lg border border-outline-variant/5">
                <div className="flex items-start gap-4">
                  <span className="material-symbols-outlined text-primary-fixed mt-1 fill-1">auto_awesome</span>
                  <div>
                    <h4 className="font-bold text-on-surface font-headline">AI Generation Ready</h4>
                    <p className="text-sm text-on-surface-variant mt-1 leading-relaxed">The "Publish" action will automatically format and upload Elena's latest content sequence to your linked TikTok profile.</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Authentication Action Card */}
            <div className="w-full lg:w-7/12 flex flex-col justify-center animate-fade-in">
              <div className="bg-surface-container-lowest p-10 lg:p-14 rounded-xl shadow-2xl relative overflow-hidden border border-outline-variant/10">
                <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary-container/10 rounded-full blur-3xl"></div>
                <div className="relative z-10">
                  <header className="mb-10">
                    <h1 className="text-4xl lg:text-5xl font-extrabold text-on-surface font-headline mb-4 tracking-tight leading-tight">TikTok Authentication</h1>
                    <p className="text-lg text-on-surface-variant max-w-md">Connect your professional TikTok account to authorize direct publishing from the Aura Influencer dashboard.</p>
                  </header>

                  <div className="space-y-6">
                    <button 
                      onClick={() => setCurrentStep("telegram")}
                      className="w-full py-5 px-8 rounded-full bg-gradient-to-r from-primary to-primary-container text-on-primary flex items-center justify-center gap-4 transition-all scale-100 hover:scale-[0.98] active:scale-[0.95] shadow-lg group"
                    >
                      <svg className="w-6 h-6 fill-current" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.06-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.03 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.9-.32-1.9-.36-2.81-.12-1.09.28-2.06 1.01-2.61 1.98-.44.75-.58 1.63-.51 2.49.07.9.46 1.76 1.1 2.39.69.72 1.67 1.16 2.67 1.2 1.05.07 2.15-.22 2.97-.89.89-.71 1.34-1.84 1.3-2.97.03-4.32.01-8.64.02-12.96z"></path>
                      </svg>
                      <span className="font-bold text-lg font-headline">Sign in with TikTok</span>
                    </button>
                    <div className="flex items-center gap-3 p-4 bg-surface-container rounded-lg border border-outline-variant/10">
                      <span className="material-symbols-outlined text-tertiary">verified_user</span>
                      <span className="text-sm text-on-surface-variant font-medium">Encrypted Oauth2 connection. Aura never sees your password.</span>
                    </div>
                  </div>

                  <div className="mt-12 flex items-center justify-between">
                    <Link href="/" className="text-on-surface-variant hover:text-primary transition-colors text-sm font-semibold flex items-center gap-2">
                      <span className="material-symbols-outlined text-lg">arrow_back</span>
                      Return to Designer
                    </Link>
                    <div className="flex gap-4">
                      <a className="text-xs text-on-surface-variant underline hover:text-on-surface transition-all" href="#">Privacy</a>
                      <a className="text-xs text-on-surface-variant underline hover:text-on-surface transition-all" href="#">Terms</a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Telegram Authentication Step (Step 2)
  return (
    <div className="bg-background text-on-surface min-h-screen flex flex-col selection:bg-primary-container/20 overflow-x-hidden">
      <main className="flex-grow flex flex-col items-center justify-center px-6 py-12 relative overflow-hidden">
        {/* Organic Background Elements */}
        <div className="absolute top-[-10%] right-[-10%] w-[40rem] h-[40rem] rounded-full bg-primary-container/10 blur-[100px] pointer-events-none"></div>
        <div className="absolute bottom-[-5%] left-[-5%] w-[30rem] h-[30rem] rounded-full bg-secondary-container/10 blur-[80px] pointer-events-none"></div>

        {/* Progress Indicator */}
        <div className="w-full max-w-md mb-12 flex items-center justify-center gap-4 z-10">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-full bg-tertiary text-on-tertiary flex items-center justify-center shadow-lg">
              <span className="material-symbols-outlined fill-1">check</span>
            </div>
            <span className="text-sm font-label text-on-surface-variant">TikTok</span>
          </div>
          <div className="h-[2px] w-12 bg-surface-container-highest"></div>
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-full bg-primary text-on-primary flex items-center justify-center shadow-lg ring-4 ring-primary-container/20">
              <span className="text-sm font-bold">2</span>
            </div>
            <span className="text-sm font-label text-on-surface font-bold">Telegram</span>
          </div>
          <div className="h-[2px] w-12 bg-surface-container-highest"></div>
          <div className="flex items-center gap-2 opacity-40">
            <div className="w-10 h-10 rounded-full bg-surface-container-high text-on-surface-variant flex items-center justify-center">
              <span className="text-sm font-bold">3</span>
            </div>
            <span className="text-sm font-label text-on-surface-variant">Done</span>
          </div>
        </div>

        {/* Authentication Card */}
        <div className="w-full max-w-2xl bg-surface-container-lowest rounded-xl shadow-2xl overflow-hidden flex flex-col md:flex-row relative z-10 border border-outline-variant/10">
          {/* Visual Side */}
          <div className="w-full md:w-5/12 relative h-64 md:h-auto min-h-[300px]">
            <div 
              className="absolute inset-0 bg-cover bg-center" 
              style={{ backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuBSU8ftoyiZGJD3H_GkLrTdl-W-Ig4pHyCN7LHttEGPbQvntO07CiLVSvpn-fwr1dS8fl4mTzc6aqbhaCFdhDgE9q5LLKPRHS5TMOPVyHl4AnDlDsRFUTzJJeX-yRq-DKKUrRiFKfRvfGJjmssJtmutw_DbIvLyVN2ExUsYaF4meKTQbPOINuOLk1u3PAhKEeF11IQKBcnol4XHDh2ckQSwFUAjOSJAj0r9JwjAB1TukqWdeQY8-MXkpFaTbWJ2HtO1x0OvxDXNXl0')" }}
            ></div>
            <div className="absolute inset-0 bg-gradient-to-t from-primary/60 to-transparent"></div>
            <div className="absolute bottom-8 left-8 right-8 backdrop-blur-xl bg-surface/70 p-6 rounded-lg border border-white/20">
              <div className="flex items-center gap-4 mb-3">
                <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-primary-container">
                  <img 
                    alt="Persona" 
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuAgEZ7IBStwuciRq0xKBirYD89vzAGZZIjr6rjAp94yXGwUW3w20LQjAdXcnLLkDafouNsFOXMIyDTGoVtoCQEiO7jmDON9S1nIYA_oHzVDe3JHG6advnRI1YV3diOAw2hV5ogFVzsLopC9-6ZKNzi_uC5CQ3HQ1VR3zJIVSMnCRMBz1S91hk1wvxeuCPB8s69PwOhVLWUPQXR-YSGu5Yyj9kHF80HQLfUiC97EDs-P_qjofJ4_gWksa9Thu-rlCMp2d21yXIA8eQI" 
                  />
                </div>
                <div>
                  <p className="text-on-surface font-headline font-bold text-lg leading-tight">Aura AI</p>
                  <p className="text-on-surface-variant text-xs font-label">Assistant Mode Active</p>
                </div>
              </div>
              <p className="text-sm text-on-surface-variant leading-relaxed">"I'll be your direct line for performance alerts and automated fleet commands."</p>
            </div>
          </div>

          {/* Content Side */}
          <div className="w-full md:w-7/12 p-10 flex flex-col justify-center animate-fade-in">
            <h1 className="text-3xl md:text-4xl font-headline font-extrabold text-on-surface tracking-tight mb-4">Telegram Authentication</h1>
            <p className="text-on-surface-variant mb-8 leading-relaxed">Enable automated posting and notifications to keep your creator factory running 24/7.</p>

            {showQR && telegramSignInUrl ? (
              <div className="space-y-6">
                <div className="flex flex-col items-center gap-5 p-6 bg-surface-container rounded-xl border border-outline-variant/10 w-full">
                  <div className="bg-white p-4 rounded-xl shadow-xl shadow-primary/5 border border-outline-variant/10 transition-transform hover:scale-[1.02]">
                    <img 
                      src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(telegramSignInUrl)}`} 
                      alt="Telegram Login QR"
                      className="w-40 h-40"
                    />
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-on-surface font-black uppercase tracking-widest editorial-headline">Quét mã QR</p>
                    <p className="text-[10px] text-on-surface-variant font-medium mt-1">Mở Telegram và quét để đăng nhập</p>
                  </div>
                  <button onClick={() => setShowQR(false)} className="text-primary text-xs font-bold uppercase tracking-widest hover:underline px-4 py-2">Quay lại</button>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Why Section */}
                <div className="space-y-6 mb-10">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 shrink-0 rounded-lg bg-surface-container flex items-center justify-center text-primary border border-outline-variant/5">
                      <span className="material-symbols-outlined fill-1">bolt</span>
                    </div>
                    <div>
                      <h3 className="font-headline font-bold text-on-surface">Live Production Updates</h3>
                      <p className="text-sm text-on-surface-variant">Get instant pings when your personas go viral or need manual approval.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 shrink-0 rounded-lg bg-surface-container flex items-center justify-center text-primary border border-outline-variant/5">
                      <span className="material-symbols-outlined fill-1">group_work</span>
                    </div>
                    <div>
                      <h3 className="font-headline font-bold text-on-surface">Manage Your Fleet</h3>
                      <p className="text-sm text-on-surface-variant">Issue commands to multiple AI agents directly through your secure chat.</p>
                    </div>
                  </div>
                </div>

                {/* Login Button */}
                <div className="space-y-4">
                  <button 
                    disabled={isGeneratingToken || isAwaitingTelegram}
                    onClick={handleActionClick}
                    className="w-full py-4 px-8 bg-gradient-to-r from-primary to-primary-container text-on-primary font-headline font-bold rounded-full flex items-center justify-center gap-3 shadow-lg hover:scale-[0.98] transition-all active:scale-95 group disabled:opacity-50"
                  >
                    <span className="material-symbols-outlined fill-1" style={{ fontSize: '20px' }}>send</span>
                    {isGeneratingToken ? "Đang xử lý..." : "Continue with Telegram"}
                    <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">arrow_forward</span>
                  </button>
                  <button onClick={handleQRClick} className="w-full text-center text-xs text-on-surface-variant hover:text-primary transition-colors font-bold uppercase tracking-widest">
                    Hoặc dùng mã QR
                  </button>
                  <p className="text-center text-[10px] text-on-surface-variant opacity-60 px-4">
                    By connecting, you agree to receive automated messages. You can mute or disconnect at any time in settings.
                  </p>
                </div>
              </div>
            )}

            {/* Status & Errors */}
            {(isAwaitingTelegram || isCompletingSession) && (
              <div className="mt-6 p-4 rounded-xl bg-primary/5 border border-primary/10 text-center animate-pulse-slow">
                <div className="flex items-center justify-center gap-2 mb-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce"></div>
                  <p className="text-[10px] font-black uppercase tracking-widest text-primary">
                    {isCompletingSession ? "Đang xác thực..." : "Đang chờ Telegram"}
                  </p>
                </div>
                <p className="text-xs text-on-surface-variant">
                  Bạn sẽ tự động chuyển hướng sau khi nhấn <b>Start</b> trong bot.
                </p>
              </div>
            )}

            {localError || error ? (
              <div className="mt-4 p-4 rounded-lg bg-error-container/10 border border-error-container/20 text-center">
                <p className="text-xs text-error font-bold">{localError || (error as string)}</p>
              </div>
            ) : null}

            {/* Dev Mode Bypass */}
            {process.env.NODE_ENV === "development" && (
              <div className="mt-8 pt-6 border-t border-outline-variant/10">
                <button
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
                  className="w-full rounded-full border border-primary/10 bg-primary/5 py-3 text-[10px] font-black uppercase tracking-widest text-primary transition-all hover:bg-primary/10"
                >
                  Skip for now (Dev Mode)
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Secondary Actions */}
        <div className="mt-12 flex items-center gap-8 z-10">
          <button 
            onClick={() => setCurrentStep("tiktok")}
            className="text-on-surface-variant hover:text-primary font-label text-sm transition-colors flex items-center gap-2 group"
          >
            <span className="material-symbols-outlined text-lg group-hover:-translate-x-1 transition-transform">arrow_back</span>
            Back to TikTok Login
          </button>
        </div>
      </main>

      <footer className="w-full max-w-7xl mx-auto px-8 py-8 flex flex-col md:flex-row justify-between items-center opacity-60 border-t border-outline-variant/10">
        <div className="text-xs font-label text-on-surface-variant mb-4 md:mb-0">
          © 2026 Aura Influencer Factory. All rights reserved.
        </div>
        <div className="flex gap-6">
          <a className="text-xs font-label text-on-surface-variant hover:text-primary underline" href="#">Privacy Protocol</a>
          <a className="text-xs font-label text-on-surface-variant hover:text-primary underline" href="#">Terms of Production</a>
        </div>
      </footer>

      <Footer variant="page" />
    </div>
  );
}
