"use client";

import type { DashboardTabId, DashboardTab } from "./customer-dashboard";

interface DashboardSidebarProps {
  tabs: DashboardTab[];
  activeTab: DashboardTabId;
  onTabChange: (tabId: DashboardTabId) => void;
  userEmail?: string;
  telegramBotUrl?: string | null;
}

// Map tab id → Material Symbol icon name fallback (we use Lucide from parent, this is decorative)
const TAB_SUBTITLES: Record<string, string> = {
  overview: "Workspace overview",
  ops: "AI orchestration",
  skills: "Manage personas",
  memory: "Campaigns & data",
  live_feed: "Live activity",
};

export function DashboardSidebar({
  tabs,
  activeTab,
  onTabChange,
  telegramBotUrl,
}: DashboardSidebarProps) {
  return (
    <aside className="hidden md:flex flex-col flex-shrink-0 p-5 space-y-1 bg-brand-surface-variant w-60 rounded-r-2xl sticky top-16 self-start h-[calc(100vh-64px)] z-40 overflow-y-auto">
      {/* Brand tagline */}
      <div className="mb-6 px-3 pt-2">
        <h2 className="text-base font-bold text-brand-on-surface font-headline">AI-Influencer</h2>
        <p className="text-xs text-brand-outline mt-0.5 uppercase tracking-widest">Factory</p>
      </div>

      {/* Nav items */}
      <nav className="flex-1 space-y-1">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              title={TAB_SUBTITLES[tab.id] || tab.label}
              className={`w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 ease-out ${
                isActive
                  ? "bg-white text-brand-primary shadow-brand-sm"
                  : "text-brand-on-surface-variant hover:text-brand-primary hover:bg-white/50"
              }`}
            >
              <Icon
                className={`h-5 w-5 flex-shrink-0 ${
                  isActive ? "text-brand-primary" : "text-brand-outline"
                }`}
              />
              <span className="truncate">{tab.label}</span>
              {isActive && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-primary" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="pt-4 border-t border-brand-outline-variant/30 space-y-1 mt-auto">

        {/* Telegram Bot button */}
        {telegramBotUrl && (
          <a
            href={telegramBotUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-bold bg-[#0088cc]/10 text-[#0088cc] hover:bg-[#0088cc]/20 transition-all group mb-1"
          >
            <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248-2.038 9.589c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.901.632z"/>
            </svg>
            <span>Mở Telegram Bot</span>
            <svg className="w-3.5 h-3.5 ml-auto opacity-50" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
            </svg>
          </a>
        )}

        {/* Help link */}
        <a
          href="#"
          className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm text-brand-on-surface-variant hover:text-brand-primary hover:bg-white/50 transition-all group"
        >
          <span className="w-6 h-6 rounded-full bg-brand-outline-variant/30 flex items-center justify-center text-xs font-bold group-hover:bg-brand-primary group-hover:text-white transition-all">?</span>
          <span>Trợ giúp &amp; Docs</span>
        </a>

        {/* Logout link */}
        <a
          href="/auth"
          className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm text-brand-on-surface-variant hover:text-brand-error hover:bg-brand-error/5 transition-all"
        >
          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M18 12H9m0 0l3-3m-3 3l3 3" />
          </svg>
          <span>Đăng xuất</span>
        </a>
      </div>
    </aside>
  );
}