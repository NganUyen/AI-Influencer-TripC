"use client";

import type { CSSProperties } from "react";

interface DashboardHeaderProps {
  userName: string | undefined;
  userEmail: string | undefined;
  telegramBotUrl: string | null;
  onLogout: () => void;
  isSigningOut: boolean;
}

export function DashboardHeader({
  userName,
  userEmail,
  telegramBotUrl,
  onLogout,
  isSigningOut,
}: DashboardHeaderProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-white/[0.08] bg-zinc-950/95 backdrop-blur-xl px-8 py-4">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-300">
            Customer Workspace
          </p>
          <h1 className="text-xl font-semibold text-white">Dashboard</h1>
        </div>

        <div className="flex items-center gap-4">
          {telegramBotUrl && (
            <a
              href={telegramBotUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 transition-all duration-200 ease-out hover:bg-emerald-400 hover:shadow-emerald-500/30 active:scale-[0.98]"
            >
              Telegram Bot
            </a>
          )}

          <div className="rounded-[12px] border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl px-3 py-2 text-xs text-zinc-400">
            {userName || userEmail}
          </div>

          <button
            type="button"
            onClick={onLogout}
            disabled={isSigningOut}
            className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm font-semibold text-stone-100 transition-all duration-200 ease-out hover:border-white/25 hover:bg-white/10 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSigningOut ? "Signing out..." : "Sign out"}
          </button>
        </div>
      </div>
    </header>
  );
}