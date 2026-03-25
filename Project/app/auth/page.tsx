"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useCustomerAuthStore } from "@/store/customer-auth-store";

export default function AuthPage() {
  const router = useRouter();
  const {
    login,
    signup,
    isLoading,
    error,
    initialized,
    initialize,
    isAuthenticated,
  } = useCustomerAuthStore((state) => ({
    login: state.login,
    signup: state.signup,
    isLoading: state.isLoading,
    error: state.error,
    initialized: state.initialized,
    initialize: state.initialize,
    isAuthenticated: state.isAuthenticated,
  }));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (initialized && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [initialized, isAuthenticated, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);

    try {
      if (mode === "signin") {
        await login(email, password);
      } else {
        await signup({ email, password, name });
      }
      router.push("/dashboard");
    } catch (submitError) {
      setLocalError(
        submitError instanceof Error ? submitError.message : "Unable to continue",
      );
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
                mode === "signin"
                  ? "bg-emerald-300 text-slate-950"
                  : "text-stone-300"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setMode("signup")}
              className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${
                mode === "signup"
                  ? "bg-emerald-300 text-slate-950"
                  : "text-stone-300"
              }`}
            >
              Create Account
            </button>
          </div>

          <h2 className="text-3xl font-semibold text-white">
            {mode === "signin" ? "Welcome back" : "Create your workspace"}
          </h2>
          <p className="mt-2 text-sm text-stone-400">
            {mode === "signin"
              ? "Sign in with your customer account to continue."
              : "Create a customer account, then finish brand onboarding in the dashboard."}
          </p>

          <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
            {mode === "signup" && (
              <div>
                <label className="mb-2 block text-sm font-medium text-stone-300">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none transition focus:border-emerald-300"
                  placeholder="Alicia Founder"
                />
              </div>
            )}

            <div>
              <label className="mb-2 block text-sm font-medium text-stone-300">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none transition focus:border-emerald-300"
                placeholder="founder@brand.com"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-stone-300">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none transition focus:border-emerald-300"
                placeholder="Use a strong password"
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
              />
            </div>

            {(localError || error) && (
              <p className="text-sm text-rose-200">{localError || error}</p>
            )}

            <button
              type="submit"
              disabled={isLoading || !initialized}
              className="w-full rounded-full bg-emerald-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading
                ? "Working..."
                : mode === "signin"
                  ? "Enter Dashboard"
                  : "Create Account"}
            </button>
          </form>
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
