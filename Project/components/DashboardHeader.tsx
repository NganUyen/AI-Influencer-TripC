"use client";

import { Bell, Settings, Search, Menu } from "lucide-react";
import { SocialIcon } from "@/components/ui/SocialIcon";
import tripCLogo from "@/app/dashboard/tripc-logo.png";

interface DashboardHeaderProps {
  userName: string | undefined;
  userEmail: string | undefined;
  telegramBotUrl: string | null;
  onLogout: () => void;
  isSigningOut: boolean;
  onMobileMenuToggle?: () => void;
}

export function DashboardHeader({
  userName,
  userEmail,
  telegramBotUrl,
  onLogout,
  isSigningOut,
  onMobileMenuToggle,
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
            {onMobileMenuToggle && (
              <button 
                onClick={onMobileMenuToggle}
                className="md:hidden p-1.5 -ml-2 rounded-lg hover:bg-brand-surface-container active:scale-95 transition-all text-brand-on-surface-variant mr-1"
                aria-label="Open menu"
              >
                <Menu className="w-5 h-5 stroke-[1.75]" />
              </button>
            )}
            {/* Icon mark */}
            <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 shadow-brand-sm overflow-hidden">
              <img 
                src={tripCLogo.src} 
                alt="TripC" 
                className="w-full h-full object-cover"
              />
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
          <div className="hidden md:flex items-center bg-brand-surface-container-low rounded-full px-4 py-2 gap-2.5 border border-brand-outline-variant/30 transition-all focus-within:border-brand-primary/30 focus-within:shadow-brand-sm">
            <Search className="h-[14px] w-[14px] text-brand-outline stroke-[1.75]" />
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
              href={telegramBotUrl as string}
              target="_blank"
              rel="noreferrer"
              className="hidden sm:inline-flex items-center gap-2 px-3.5 py-2 rounded-full bg-brand-surface-container text-brand-on-surface-variant text-sm font-semibold transition-all hover:bg-brand-surface-container-high hover:text-brand-on-surface active:scale-95 border border-brand-outline-variant/20"
            >
              <SocialIcon platform="telegram" size={15} />
              Telegram
            </a>
          )}

          <button className="p-2 rounded-full hover:bg-brand-surface-container transition-colors duration-200 active:scale-95" aria-label="Notifications">
            <Bell className="h-[18px] w-[18px] text-brand-on-surface-variant stroke-[1.75]" />
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