"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuthStore } from "@/store/auth-store";

export default function OpsLoginPage() {
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(email, token);
      router.push("/ops");
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Unable to sign in",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-stone-100 flex items-center justify-center px-6">
      <div className="w-full max-w-md rounded-[28px] border border-white/10 bg-white/5 p-8 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.28em] text-amber-200/80">
          Internal Operator Access
        </p>
        <h1 className="mt-3 text-3xl font-semibold text-white">
          Sign in to the ops console
        </h1>
        <p className="mt-3 text-sm text-stone-400">
          This route keeps the shared admin-token console separate from the customer-facing workspace.
        </p>

        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-stone-400">
              Operator Email
            </span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-amber-300"
              placeholder="ops@yourdomain.com"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-stone-400">
              Admin Access Token
            </span>
            <input
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-amber-300"
              placeholder="Enter the shared admin token"
            />
          </label>

          {error && <p className="text-sm text-rose-200">{error}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-full bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Signing In..." : "Enter Ops Console"}
          </button>
        </form>
      </div>
    </div>
  );
}
