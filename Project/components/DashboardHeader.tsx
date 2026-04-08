"use client";

import { Bell, Settings, Search } from "lucide-react";

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
  const displayName = userName || userEmail || "User";
  const initials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <header className="fixed top-0 w-full z-50 border-b border-brand-outline-variant/20 brand-glass shadow-brand-sm">
      <div className="flex justify-between items-center px-6 md:px-8 py-3 w-full max-w-[1600px] mx-auto">
        {/* Brand + Search */}
        <div className="flex items-center gap-6">
          {/* Logo */}
          <div className="flex items-center gap-2.5 select-none">
            {/* Icon mark */}
            <div className="w-8 h-8 rounded-xl bg-brand-primary flex items-center justify-center flex-shrink-0 shadow-brand-sm">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 2L10.8 6.6L15.5 7.3L12.2 10.5L13.1 15.2L9 13L4.9 15.2L5.8 10.5L2.5 7.3L7.2 6.6L9 2Z" fill="white" />
              </svg>
            </div>
            {/* Brand text */}
            <div className="leading-none">
              <span className="text-base font-extrabold tracking-tight text-brand-primary font-headline block">
                AI-Influencer
              </span>
              <span className="text-[10px] font-semibold tracking-widest text-brand-outline uppercase block mt-0.5">
                Factory
              </span>
            </div>
          </div>
          <div className="hidden md:flex items-center bg-brand-surface-container-low rounded-full px-4 py-2 gap-2 border border-brand-outline-variant/30 transition-all focus-within:border-brand-primary/30 focus-within:shadow-brand-sm">
            <Search className="h-4 w-4 text-brand-outline" />
            <input
              className="bg-transparent border-none focus:ring-0 text-sm font-body text-brand-on-surface-variant placeholder:text-brand-outline w-52 outline-none"
              placeholder="Search workplace..."
              type="text"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          {telegramBotUrl && (
            <a
              href={telegramBotUrl}
              target="_blank"
              rel="noreferrer"
              className="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-secondary-container text-brand-on-secondary-container text-sm font-semibold transition-all hover:shadow-brand-sm active:scale-95"
            >
              Telegram Bot
            </a>
          )}

          <button className="p-2 rounded-full hover:bg-brand-surface-container transition-colors duration-200 active:scale-95">
            <Bell className="h-5 w-5 text-brand-on-surface-variant" />
          </button>

          <button className="p-2 rounded-full hover:bg-brand-surface-container transition-colors duration-200 active:scale-95">
            < Bell className="h-5 w-5 text-brand-on-surface-variant" />
          </button>

          {/* Avatar */}
          <div className="relative group">
            <div className="w-9 h-9 rounded-full bg-brand-primary flex items-center justify-center text-sm font-bold text-brand-on-primary cursor-pointer select-none shadow-brand-sm">
              {initials}
            </div>
            {/* Dropdown on hover */}
            <div className="absolute right-0 top-full mt-2 w-44 bg-white rounded-2xl shadow-brand-md border border-brand-outline-variant/20 py-1 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200">
              <div className="px-4 py-2 border-b border-brand-surface-container-high">
                <p className="text-xs font-semibold text-brand-on-surface truncate">{displayName}</p>
              </div>
              <button
                onClick={onLogout}
                disabled={isSigningOut}
                className="w-full text-left px-4 py-2 text-sm text-brand-on-surface-variant hover:text-brand-primary hover:bg-brand-surface-container-low transition-colors disabled:opacity-50"
              >
                {isSigningOut ? "Signing out…" : "Sign out"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}