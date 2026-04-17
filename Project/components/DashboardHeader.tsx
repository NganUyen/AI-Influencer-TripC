"use client";

import { Bell, Search, Menu } from "lucide-react";
import { useRouter } from "next/navigation";
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
  const router = useRouter();
  const displayName = userName || userEmail || "User";
  const initials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const handleLogoClick = () => {
    // Navigate to dashboard home
    router.push("/dashboard");
    
    // Smooth scroll to top
    setTimeout(() => {
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    }, 0);
  };

  return (
    <header className="fixed top-0 z-50 w-full border-b border-brand-outline-variant/20 brand-glass shadow-brand-sm">
      <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between gap-4 px-4 py-3 sm:px-6 md:px-8">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5 select-none cursor-pointer" onClick={handleLogoClick} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && handleLogoClick()} aria-label="Go to dashboard overview">
            {onMobileMenuToggle && (
              <button
                onClick={onMobileMenuToggle}
                className="mr-1 -ml-2 rounded-card p-2 text-brand-on-surface-variant transition-all hover:bg-brand-surface-container active:scale-95 md:hidden"
                aria-label="Open menu"
              >
                <Menu className="w-5 h-5 stroke-[1.75]" />
              </button>
            )}
            <div className="dashboard-card flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden p-0 shadow-brand-sm hover:scale-105 transition-transform">
              <img
                src={tripCLogo.src}
                alt="TripC"
                width={36}
                height={36}
                className="h-full w-full object-cover"
              />
            </div>
            <div className="leading-none hover:text-brand-primary transition-colors">
              <span className="block font-headline text-base font-extrabold tracking-tight text-brand-primary">
                AI-Influencer
              </span>
              <span className="mt-0.5 block text-[10px] font-semibold uppercase tracking-widest text-brand-outline">
                Factory
              </span>
            </div>
          </div>
          <div className="hidden items-center gap-2.5 rounded-full border border-brand-outline-variant/20 bg-brand-surface-container-low px-4 py-2 transition-all focus-within:border-brand-primary/30 focus-within:shadow-brand-sm md:flex">
            <Search className="h-[14px] w-[14px] text-brand-outline stroke-[1.75]" />
            <label className="sr-only" htmlFor="dashboard-workplace-search">
              Search workplace
            </label>
            <input
              id="dashboard-workplace-search"
              name="workplaceSearch"
              className="w-52 border-none bg-transparent text-sm font-body text-brand-on-surface-variant placeholder:text-brand-outline outline-none focus:ring-0"
              placeholder="Search workplace…"
              type="search"
              autoComplete="off"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          {telegramBotUrl && (
            <a
              href={telegramBotUrl}
              target="_blank"
              rel="noreferrer"
              className="hidden items-center gap-2 rounded-full border border-brand-outline-variant/20 bg-brand-surface-container px-3.5 py-2 text-sm font-semibold text-brand-on-surface-variant transition-all hover:bg-brand-surface-container-high hover:text-brand-on-surface active:scale-95 sm:inline-flex"
            >
              <SocialIcon platform="telegram" size={15} />
              Telegram
            </a>
          )}

          <button
            type="button"
            className="dashboard-card flex h-10 w-10 items-center justify-center rounded-full p-0 transition-colors duration-200 hover:bg-brand-surface-container active:scale-95"
            aria-label="Notifications"
          >
            <Bell className="h-[18px] w-[18px] text-brand-on-surface-variant stroke-[1.75]" />
          </button>

          <div className="group relative">
            <button
              type="button"
              className="flex h-9 w-9 select-none items-center justify-center rounded-full bg-brand-primary text-sm font-bold text-brand-on-primary shadow-brand-sm transition-transform hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary/30"
              aria-haspopup="menu"
              aria-label={`${displayName} profile menu`}
            >
              {initials}
            </button>
            <div
              role="menu"
              className="dashboard-card pointer-events-none invisible absolute right-0 top-full mt-2 w-44 py-1 opacity-0 transition-all duration-200 group-hover:pointer-events-auto group-hover:visible group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:visible group-focus-within:opacity-100"
            >
              <div className="border-b border-brand-surface-container-high px-4 py-2">
                <p className="truncate text-xs font-semibold text-brand-on-surface">{displayName}</p>
              </div>
              <button
                type="button"
                onClick={onLogout}
                disabled={isSigningOut}
                role="menuitem"
                className="w-full px-4 py-2 text-left text-sm text-brand-on-surface-variant transition-colors hover:bg-brand-surface-container-low hover:text-brand-primary disabled:opacity-50"
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
