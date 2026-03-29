"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  deriveTelegramBotUsername,
  getClientPublicEnvValue,
} from "@/lib/public-env";
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
  token_type?: string | null;
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
  const router = useRouter();
  const telegramBotUrl = buildTelegramBotUrl();
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
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [localError, setLocalError] = useState<string | null>(null);
  const [linkToken, setLinkToken] = useState<TelegramLinkToken | null>(null);
  const [isGeneratingToken, setIsGeneratingToken] = useState(false);
  const [isAwaitingTelegram, setIsAwaitingTelegram] = useState(false);
  const [isCompletingSession, setIsCompletingSession] = useState(false);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (initialized && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [initialized, isAuthenticated, router]);

  useEffect(() => {
    if (!linkToken) {
      setIsAwaitingTelegram(false);
      setIsCompletingSession(false);
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof window.setTimeout> | null = null;
    const expiresAt = Date.parse(linkToken.expires_at);

    const pollForCompletion = async () => {
      if (cancelled) {
        return;
      }

      if (Number.isFinite(expiresAt) && Date.now() >= expiresAt) {
        setLinkToken(null);
        setIsAwaitingTelegram(false);
        setIsCompletingSession(false);
        setLocalError("Telegram link expired. Generate a new secure link to continue.");
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
          await establishSessionFromAccessToken(payload.access_token);
          if (cancelled) {
            return;
          }
          setLinkToken(null);
          setIsAwaitingTelegram(false);
          setIsCompletingSession(false);
          router.replace("/dashboard");
          return;
        }

        if (payload.status === "expired") {
          setLinkToken(null);
          setIsAwaitingTelegram(false);
          setIsCompletingSession(false);
          setLocalError("Telegram link expired. Generate a new secure link to continue.");
          return;
        }

        timeoutId = window.setTimeout(() => {
          void pollForCompletion();
        }, 2500);
      } catch (requestError) {
        if (cancelled) {
          return;
        }
        setIsAwaitingTelegram(false);
        setIsCompletingSession(false);
        setLocalError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to complete Telegram sign-in",
        );
      }
    };

    void pollForCompletion();

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [
    establishSessionFromAccessToken,
    linkToken?.expires_at,
    linkToken?.start_token,
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
    } catch (requestError) {
      setLocalError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to generate Telegram link",
      );
    } finally {
      setIsGeneratingToken(false);
    }
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#23443d_0%,#0c1220_40%,#07080c_100%)] px-6 py-10 text-stone-100">
      <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-[34px] border border-white/10 bg-white/5 p-8 backdrop-blur">
          <p className="text-xs uppercase tracking-[0.32em] text-emerald-200/80">
            Customer-Facing Automation
          </p>
          <h1 className="mt-4 text-5xl font-semibold leading-tight text-white">
            Turn one login into a guided marketing machine.
          </h1>
          <p className="mt-5 max-w-2xl text-base text-stone-300">
            This workspace is built for real customer accounts: connect official socials,
            brief OpenClaw in-app, review the plan, and launch the Temporal workflow with
            review-first controls.
          </p>

          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            <FeatureCard
              title="Connect Official Accounts"
              description="OAuth-first account linking for LinkedIn, Facebook, X, and YouTube."
            />
            <FeatureCard
              title="Plan With OpenClaw"
              description="Persistent strategy threads and artifacts live inside the workspace."
            />
            <FeatureCard
              title="Review Before Launch"
              description="Approve the campaign in the web app before anything is published."
            />
          </div>

          <p className="mt-8 text-sm text-stone-400">
            Operators still use the internal console at{" "}
            <a className="text-amber-200 underline underline-offset-4" href="/ops/login">
              /ops/login
            </a>
            .
          </p>
        </div>

        <div className="rounded-[34px] border border-white/10 bg-black/25 p-8 backdrop-blur">
          <div className="mb-6 flex rounded-full border border-white/10 bg-white/5 p-1">
            <button
              type="button"
              onClick={() => setMode("signin")}
              className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${
                mode === "signin" ? "bg-emerald-300 text-slate-950" : "text-stone-300"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setMode("signup")}
              className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${
                mode === "signup" ? "bg-emerald-300 text-slate-950" : "text-stone-300"
              }`}
            >
              Create Account
            </button>
          </div>

          <div className="mt-8">
            <h2 className="text-3xl font-semibold text-white">
              {mode === "signin" ? "Welcome back" : "Create your workspace"}
            </h2>
            <p className="mt-2 text-sm text-stone-400">
              {mode === "signin"
                ? "Connect your Telegram to sign in securely."
                : "Link your Telegram account to start building your influencer factory."}
            </p>

            <div className="mt-10 flex flex-col items-center justify-center rounded-3xl border border-white/5 bg-white/5 px-6 py-8 backdrop-blur-sm">
              {linkToken ? (
                <div className="w-full space-y-4">
                  <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/5 p-4 text-center">
                    <p className="text-xs uppercase tracking-[0.18em] text-emerald-200/80">
                      Secure Link Ready
                    </p>
                    <p className="mt-2 text-sm text-stone-200">
                      Open Telegram, tap Start in the bot, and we&apos;ll sign you in
                      automatically here.
                    </p>
                  </div>
                  <a
                    href={`${telegramBotUrl}?start=${linkToken.start_token}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex w-full items-center justify-center gap-2 rounded-full bg-emerald-300 px-5 py-4 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200"
                  >
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.161c-.18 1.897-.962 6.502-1.359 8.627-.168.9-.5 1.201-.82 1.23-.697.064-1.226-.461-1.901-.903-1.056-.692-1.653-1.123-2.678-1.799-1.185-.781-.417-1.21.258-1.911.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.139-5.062 3.345-.479.329-.913.489-1.302.481-.428-.009-1.252-.242-1.865-.442-.751-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.831-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635.099-.002.321.023.465.141.121.099.154.232.17.325.015.094.034.31.019.478z" />
                    </svg>
                    Open Telegram & Sign In
                  </a>
                  <p className="text-center text-[10px] text-stone-500">
                    Link expires at: {new Date(linkToken.expires_at).toLocaleTimeString()}
                  </p>
                  {(isAwaitingTelegram || isCompletingSession) && (
                    <div className="rounded-2xl border border-amber-300/15 bg-amber-300/5 p-4 text-center">
                      <p className="text-xs uppercase tracking-[0.18em] text-amber-200/80">
                        {isCompletingSession ? "Finishing Sign-In" : "Waiting For Telegram"}
                      </p>
                      <p className="mt-2 text-sm text-stone-200">
                        {isCompletingSession
                          ? "Telegram verified. Finalizing your customer session now."
                          : "This page is checking for confirmation and will move you into the dashboard automatically."}
                      </p>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setLinkToken(null);
                      setIsAwaitingTelegram(false);
                      setIsCompletingSession(false);
                      setLocalError(null);
                    }}
                    className="w-full text-center text-xs text-stone-400 transition hover:text-stone-300"
                  >
                    Generate new link
                  </button>
                </div>
              ) : (
                <div className="w-full space-y-4">
                  <div className="text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-300/10">
                      <svg className="h-8 w-8 text-emerald-300" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.161c-.18 1.897-.962 6.502-1.359 8.627-.168.9-.5 1.201-.82 1.23-.697.064-1.226-.461-1.901-.903-1.056-.692-1.653-1.123-2.678-1.799-1.185-.781-.417-1.21.258-1.911.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.139-5.062 3.345-.479.329-.913.489-1.302.481-.428-.009-1.252-.242-1.865-.442-.751-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.831-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635.099-.002.321.023.465.141.121.099.154.232.17.325.015.094.034.31.019.478z" />
                      </svg>
                    </div>
                    <p className="text-sm text-stone-300">
                      We use Telegram for secure, passwordless authentication.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleGenerateTelegramLink()}
                    disabled={isGeneratingToken}
                    className="w-full rounded-full bg-emerald-300 px-5 py-4 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:opacity-50"
                  >
                    {isGeneratingToken ? "Generating Secure Link..." : "Continue with Telegram"}
                  </button>
                </div>
              )}

              {typeof window !== "undefined" && window.location.hostname === "localhost" && (
                <div className="mt-6 w-full border-t border-white/5 pt-6">
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
                    className="w-full rounded-xl border border-amber-200/20 bg-amber-200/10 py-3 text-sm font-medium text-amber-200 transition-all hover:bg-amber-200/20"
                  >
                    Login as Test User (Dev Only)
                  </button>
                </div>
              )}

              <p className="mt-6 px-6 text-center text-xs text-stone-500">
                Logged in via Telegram? We&apos;ll automatically sync your personas and
                media assets.
              </p>
            </div>

            {(localError || error) && (
              <p className="mt-4 text-center text-sm text-rose-300">
                {localError || error}
              </p>
            )}

            <div className="mt-8 border-t border-white/5 pt-6 text-center">
              <p className="text-xs text-stone-500">
                By signing in, you agree to our Terms of Service and Privacy Policy.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-[28px] border border-white/10 bg-black/20 p-5">
      <p className="text-lg font-medium text-white">{title}</p>
      <p className="mt-2 text-sm text-stone-400">{description}</p>
    </div>
  );
}

function buildTelegramBotUrl(): string {
  const explicitUrl = getClientPublicEnvValue("NEXT_PUBLIC_TELEGRAM_BOT_URL").trim();
  if (explicitUrl) {
    return explicitUrl;
  }

  const username =
    getClientPublicEnvValue("NEXT_PUBLIC_TELEGRAM_BOT_USERNAME").trim() ||
    deriveTelegramBotUsername(explicitUrl) ||
    "TripCInternBot";

  return `https://t.me/${username.replace(/^@/, "")}`;
}
