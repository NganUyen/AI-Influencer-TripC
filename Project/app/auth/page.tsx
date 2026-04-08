"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { getClientTelegramBotLaunchUrl } from "@/lib/public-env";
import { useCustomerAuthStore } from "@/store/customer-auth-store";

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
      if (cancelled) {
        return;
      }

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

        if (cancelled) {
          return;
        }

        if (payload.status === "authenticated" && payload.access_token) {
          setIsCompletingSession(true);
          await establishSessionFromAccessToken(
            payload.access_token,
            payload.user || null,
            payload.refresh_token || null,
          );
          if (cancelled) {
            return;
          }
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
        if (cancelled) {
          return;
        }
        setIsAwaitingTelegram(false);
        setIsCompletingSession(false);
        // Silently retry complex network errors during polling
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
  }, [
    establishSessionFromAccessToken,
    linkToken?.expires_at,
    linkToken?.start_token,
    nextPath,
    router,
  ]);

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

  return (
    <div className="bg-[#f8f7f0] font-[Lexend] text-[#2e2f2c] min-h-screen flex flex-col items-center overflow-x-hidden selection:bg-[#a03929]/10 selection:text-[#a03929]">
      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Lexend:wght@300;400;500;600&display=swap');
        
        h1, h2, h3 { font-family: 'Plus Jakarta Sans', sans-serif; }
        .material-symbols-outlined {
          font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        }
        .gradient-text {
          background: linear-gradient(to right, #a03929, #fd7d68);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .aura-premium-shadow {
          box-shadow: 0 20px 40px rgba(46, 47, 44, 0.08), 0 10px 15px rgba(160, 57, 41, 0.04);
        }
        .animate-fade-in {
          animation: fadeIn 0.5s ease-out forwards;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-pulse-slow {
          animation: pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
      `}</style>

      {/* Decorative Background Elements */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-[#a03929]/5 rounded-full blur-[100px]"></div>
        <div className="absolute top-1/2 -right-48 w-[500px] h-[500px] bg-[#fd7d68]/5 rounded-full blur-[120px]"></div>
      </div>

      <header className="w-full max-w-7xl px-8 py-8 flex justify-between items-center z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#a03929] rounded-xl flex items-center justify-center shadow-lg shadow-[#a03929]/20">
            <span className="material-symbols-outlined text-white text-2xl">auto_awesome</span>
          </div>
          <span className="text-2xl font-bold tracking-tighter text-[#2e2f2c]">AURA</span>
        </div>
        <div className="hidden md:flex items-center gap-6">
          <span className="text-[#2e2f2c]/60 font-medium text-sm">Hệ thống vận hành thông minh</span>
          <div className="h-4 w-px bg-[#2e2f2c]/10"></div>
          <a href="/" className="text-[#a03929] font-bold text-sm hover:underline">Trang chủ</a>
        </div>
      </header>

      <main className="flex-grow w-full max-w-7xl px-8 flex flex-col lg:flex-row items-center justify-center gap-12 lg:gap-20 py-12 z-10">
        {/* Left Side: Hero Text Section */}
        <div className="w-full lg:w-3/5 space-y-10 text-center lg:text-left">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full text-[#a03929] font-bold text-sm tracking-wide border border-[#a03929]/10 shadow-sm">
            <span className="material-symbols-outlined text-base">verified</span>
            <span>TƯƠNG LAI CỦA TIẾP THỊ SỐ</span>
          </div>
          <h1 className="text-5xl lg:text-7xl font-extrabold tracking-tight leading-[1.1] text-[#2e2f2c]">
            Hóa thân <span className="gradient-text">Influencer</span><br/> 
            chỉ với một lần chạm.
          </h1>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 text-left">
            <FeatureCard 
              icon="hub" 
              title="Kết nối" 
              description="Đồng bộ đa nền tảng chỉ trong vài giây." 
            />
            <FeatureCard 
              icon="psychology" 
              title="Trí tuệ" 
              description="Tối ưu nội dung cùng sức mạnh AI." 
            />
            <FeatureCard 
              icon="schema" 
              title="Tự động" 
              description="Vận hành 24/7 qua hệ thống workflow." 
            />
          </div>
        </div>

        {/* Right Side: Login Card */}
        <div className="w-full lg:w-2/5 max-w-md">
          <div className="bg-white aura-premium-shadow rounded-lg p-10 flex flex-col items-center text-center border border-[#2e2f2c]/5 relative overflow-hidden">
            {/* Tonal detail */}
            <div className="absolute top-0 left-0 w-full h-2 bg-[#a03929]/10"></div>
            
            <div className="w-20 h-20 bg-[#f8f7f0] rounded-xl flex items-center justify-center mb-8 rotate-3 shadow-sm border border-[#2e2f2c]/5">
              <span className="material-symbols-outlined text-[#a03929] text-4xl">lock_open</span>
            </div>
            
            <h2 className="text-3xl font-bold mb-3 text-[#2e2f2c] tracking-tight">
              Đăng nhập AI-Influencer
            </h2>
            <p className="text-[#2e2f2c]/60 mb-10 text-sm font-medium">
                Sử dụng Telegram để truy cập nhanh không gian làm việc của bạn.
            </p>

            <div className="w-full space-y-4">
              {showQR && telegramSignInUrl ? (
                <div className="flex flex-col items-center gap-5 p-8 bg-[#f8f7f0] rounded-xl border border-[#2e2f2c]/5 w-full animate-fade-in">
                    <div className="bg-white p-4 rounded-xl shadow-xl shadow-[#a03929]/5 border border-[#2e2f2c]/10">
                        <img 
                          src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(telegramSignInUrl)}`} 
                          alt="Telegram Login QR"
                          className="w-40 h-40"
                        />
                    </div>
                    <div className="space-y-1">
                        <p className="text-xs text-[#2e2f2c] font-black uppercase tracking-widest">
                            Quét mã QR
                        </p>
                        <p className="text-[10px] text-[#2e2f2c]/60 font-medium">
                            Mở Telegram và quét mã để đăng nhập
                        </p>
                    </div>
                    <button 
                        onClick={() => setShowQR(false)}
                        className="text-[#a03929] text-xs font-black uppercase tracking-widest hover:bg-[#a03929]/10 rounded-full px-6 py-3 transition-colors mt-2"
                    >
                        Quay lại
                    </button>
                </div>
              ) : (
                <>
                  <button 
                    disabled={isGeneratingToken || isAwaitingTelegram}
                    onClick={handleActionClick}
                    className="w-full flex items-center justify-center gap-4 bg-gradient-to-br from-[#a03929] to-[#fd7d68] text-white py-5 px-8 rounded-full font-bold text-lg aura-premium-shadow transition-all active:scale-95 duration-200 hover:shadow-lg hover:shadow-[#a03929]/20 disabled:opacity-50 group"
                  >
                    <span className="material-symbols-outlined group-hover:rotate-12 transition-transform" style={{ fontVariationSettings: "'FILL' 1" }}>send</span>
                    {isGeneratingToken ? "Đang xử lý..." : "Tiếp tục với Telegram"}
                  </button>

                  <div className="pt-6">
                    <div className="flex items-center gap-3 w-full mb-6">
                      <div className="h-px bg-[#2e2f2c]/10 flex-grow"></div>
                      <span className="text-[10px] uppercase tracking-widest text-[#2e2f2c]/40 font-bold">Hoặc dùng mã QR</span>
                      <div className="h-px bg-[#2e2f2c]/10 flex-grow"></div>
                    </div>
                    
                    <div className="grid grid-cols-1 gap-4">
                      <button 
                        onClick={handleQRClick}
                        className="flex items-center justify-center gap-2 py-4 px-4 bg-[#f8f7f0] rounded-full text-[#2e2f2c] text-sm font-bold hover:bg-white transition-all hover:text-[#a03929] active:scale-[0.98] border border-[#2e2f2c]/5 shadow-sm"
                      >
                        <span className="material-symbols-outlined text-lg">qr_code_2</span>
                        {isGeneratingToken ? "Đang khởi tạo..." : "Hiện mã QR Đăng nhập"}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* Status Messages */}
              {(isAwaitingTelegram || isCompletingSession) && (
                 <div className="mt-4 p-6 rounded-xl bg-[#a03929]/5 border border-[#a03929]/10 text-center shadow-sm animate-pulse-slow">
                    <div className="flex items-center justify-center gap-2 mb-3">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#a03929] animate-bounce"></div>
                        <p className="text-[10px] font-black uppercase tracking-widest text-[#a03929]">
                            {isCompletingSession ? "Đang xác thực..." : "Đang chờ bot"}
                        </p>
                    </div>
                    <p className="text-xs text-[#2e2f2c]/61 font-medium leading-relaxed">
                        Bạn sẽ tự động chuyển hướng khi nhấn <b>Start</b> trong bot Telegram.
                    </p>
                 </div>
              )}

              {linkToken && !showQR && (
                <div className="mt-4 animate-fade-in">
                     <a 
                      href={telegramSignInUrl!}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[#a03929] text-[11px] font-bold underline underline-offset-4 hover:text-[#fd7d68] block text-center p-2"
                    >
                      Bot không tự mở? Nhấn vào đây để tiếp tục
                    </a>
                </div>
              )}

              {localError || error ? (
                <div className="mt-4 p-4 rounded-lg bg-red-50 border border-red-100 text-center">
                    <p className="text-xs text-red-600 font-bold">
                        {localError || (error as string)}
                    </p>
                </div>
              ) : null}

              {/* Dev Mode Mock Login */}
              {process.env.NODE_ENV === "development" && !showQR && (
                <div className="mt-8 w-full pt-6 border-t border-[#2e2f2c]/10">
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
                    className="w-full rounded-full border border-[#a03929]/10 bg-[#a03929]/5 py-3 text-[10px] font-black uppercase tracking-widest text-[#a03929] transition-all hover:bg-[#a03929]/10"
                  >
                    Bỏ qua (Chế độ phát triển)
                  </button>
                </div>
              )}
            </div>

            <div className="mt-12 pt-8 border-t border-[#2e2f2c]/10 w-full opacity-40">
              <p className="text-[9px] text-[#2e2f2c] leading-relaxed font-bold uppercase tracking-wider">
                AI-Influencer Factory 2026. Premium AI Social Network Engine.
              </p>
            </div>
          </div>
        </div>
      </main>

      <footer className="w-full max-w-7xl px-8 py-12 flex flex-col md:flex-row justify-between items-center gap-6 z-10 border-t border-[#2e2f2c]/5">
        <div className="flex flex-col items-center md:items-start text-[10px] font-bold text-[#2e2f2c]/40 uppercase tracking-widest">
          <p>Privacy First AI Operations</p>
        </div>
        <div className="flex items-center gap-8">
          <a className="text-[#2e2f2c]/60 text-sm font-bold hover:text-[#a03929] transition-colors" href="#">Hỗ trợ</a>
          <div className="w-1 h-1 bg-[#2e2f2c]/20 rounded-full"></div>
          <a className="group flex items-center gap-2 px-6 py-3 bg-[#2e2f2c] text-white rounded-full text-[10px] font-black uppercase tracking-widest transition-all hover:bg-[#a03929] hover:scale-105 shadow-md" href="/ops/login">
            <span className="material-symbols-outlined text-base">admin_panel_settings</span>
            Operator Console
          </a>
        </div>
      </footer>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={null}>
      <AuthPageContent />
    </Suspense>
  );
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="p-8 bg-white/40 backdrop-blur-sm rounded-xl space-y-4 border border-white shadow-sm transition-all hover:translate-y-[-4px] hover:shadow-lg cursor-default group">
      <div className="w-12 h-12 rounded-lg bg-[#a03929]/5 flex items-center justify-center transition-colors group-hover:bg-[#a03929]/10">
        <span className="material-symbols-outlined text-[#a03929] text-2xl transition-transform group-hover:scale-110">{icon}</span>
      </div>
      <div className="space-y-1">
        <h3 className="font-bold text-lg text-[#2e2f2c]">{title}</h3>
        <p className="text-[#2e2f2c]/60 text-xs leading-relaxed font-medium">{description}</p>
      </div>
    </div>
  );
}
