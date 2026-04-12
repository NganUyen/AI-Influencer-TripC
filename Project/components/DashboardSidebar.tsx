"use client";

import { useState } from "react";
import { X, ChevronLeft, ChevronRight, HelpCircle, LogOut, ExternalLink } from "lucide-react";
import { SocialIcon } from "@/components/ui/SocialIcon";
import type { DashboardTabId, DashboardTab } from "./customer-dashboard";

interface DashboardSidebarProps {
  tabs: DashboardTab[];
  activeTab: DashboardTabId;
  onTabChange: (tabId: DashboardTabId) => void;
  userEmail?: string;
  telegramBotUrl?: string | null;
  isMobileOpen?: boolean;
  onMobileClose?: () => void;
}

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
  isMobileOpen = false,
  onMobileClose = () => {},
}: DashboardSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const sidebarClasses = `
    flex flex-col shrink-0 bg-brand-surface-variant overflow-y-auto transition-all duration-300 ease-in-out
    fixed inset-y-0 left-0 z-50 h-full p-5 shadow-brand-xl
    md:sticky md:top-16 md:h-[calc(100vh-64px)] md:z-40 md:rounded-r-2xl md:shadow-none
    ${isMobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
    ${isCollapsed ? "md:w-20" : "md:w-60 w-64"}
  `;

  return (
    <>
      {/* Mobile overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden backdrop-blur-sm transition-opacity"
          onClick={onMobileClose}
        />
      )}

      <aside className={sidebarClasses}>
        {/* Brand tagline */}
        <div className={`mb-6 px-3 pt-2 flex items-center justify-between ${isCollapsed ? "md:justify-center md:px-0" : ""}`}>
          <div className={`${isCollapsed ? "md:hidden" : ""}`}>
            <h2 className="text-base font-bold text-brand-on-surface font-headline">AI-Influencer</h2>
            <p className="text-xs text-brand-outline mt-0.5 uppercase tracking-widest">Factory</p>
          </div>

          {/* Desktop expand/collapse toggle */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={`hidden md:flex w-7 h-7 rounded-full bg-white/95 border border-brand-outline-variant/40 items-center justify-center text-brand-on-surface-variant hover:text-brand-primary hover:bg-white shadow-brand-md transition-all duration-300 ease-in-out z-[70] backdrop-blur-sm flex-shrink-0 ${
              isCollapsed 
                ? "absolute top-6 left-1/2 -translate-x-1/2 p-1" 
                : ""
            }`}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed
              ? <ChevronRight className="w-3.5 h-3.5 stroke-[2.5]" />
              : <ChevronLeft className="w-3.5 h-3.5 stroke-[2.5]" />}
          </button>

          <button
            onClick={onMobileClose}
            className="md:hidden p-1.5 -mr-2 rounded-lg hover:bg-brand-surface-container text-brand-outline-variant"
            aria-label="Close menu"
          >
            <X className="w-5 h-5 stroke-[1.75]" />
          </button>
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
                onClick={() => {
                  onTabChange(tab.id);
                  onMobileClose();
                }}
                className={`group relative w-full flex items-center rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 ease-out ${
                  isCollapsed ? "md:justify-center" : "gap-3"
                } ${
                  isActive
                    ? "bg-white text-brand-primary shadow-brand-sm border-l-4 border-brand-primary pl-2"
                    : "text-brand-on-surface-variant hover:text-brand-primary hover:bg-white/50 border-l-4 border-transparent"
                }`}
              >
                <Icon
                  className={`h-[18px] w-[18px] shrink-0 stroke-[1.75] transition-colors ${
                    isActive ? "text-brand-primary" : "text-brand-outline group-hover:text-brand-primary"
                  }`}
                />
                <span className={`truncate font-semibold ${isCollapsed ? "md:hidden" : ""}`}>{tab.label}</span>
                {isActive && !isCollapsed && (
                  <span className="ml-auto w-2 h-2 rounded-full bg-brand-primary" />
                )}

                {/* Tooltip for collapsed state */}
                {isCollapsed && (
                  <div className="absolute left-full ml-4 px-2 py-1 bg-brand-surface-container-high text-brand-on-surface text-xs rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 hidden md:block shadow-brand-sm border border-brand-outline-variant/20">
                    {TAB_SUBTITLES[tab.id] || tab.label}
                  </div>
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
              title="Telegram Bot"
              className={`group relative flex items-center rounded-xl text-sm font-semibold text-brand-on-surface-variant hover:text-brand-primary hover:bg-white/50 transition-all ${
                isCollapsed ? "md:justify-center md:px-0 py-3" : "px-4 py-3 gap-3"
              } mb-1`}
            >
              <SocialIcon platform="telegram" size={18} className="shrink-0" />
              <span className={`${isCollapsed ? "md:hidden" : ""}`}>Open Telegram Bot</span>
              <ExternalLink className={`w-3.5 h-3.5 ml-auto opacity-40 stroke-[1.75] ${isCollapsed ? "md:hidden" : ""}`} />

              {isCollapsed && (
                <div className="absolute left-full ml-4 px-2 py-1 bg-brand-surface-container-high text-brand-on-surface text-xs rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 hidden md:block shadow-brand-sm border border-brand-outline-variant/20">
                  Open Telegram Bot
                </div>
              )}
            </a>
          )}

          {/* Help link */}
          <a
            href="#"
            title="Help & Docs"
            className={`group relative flex items-center rounded-xl text-sm text-brand-on-surface-variant hover:text-brand-primary hover:bg-white/50 transition-all ${
              isCollapsed ? "md:justify-center md:px-0 py-2.5" : "px-4 py-2.5 gap-3"
            }`}
          >
            <HelpCircle className="w-[18px] h-[18px] shrink-0 stroke-[1.75] text-brand-outline group-hover:text-brand-primary transition-colors" />
            <span className={`${isCollapsed ? "md:hidden" : ""}`}>Help &amp; Docs</span>

            {isCollapsed && (
              <div className="absolute left-full ml-4 px-2 py-1 bg-brand-surface-container-high text-brand-on-surface text-xs rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 hidden md:block shadow-brand-sm border border-brand-outline-variant/20">
                Help & Docs
              </div>
            )}
          </a>

          {/* Logout link */}
          <a
            href="/auth"
            title="Sign out"
            className={`group relative flex items-center rounded-xl text-sm text-brand-on-surface-variant hover:text-brand-error hover:bg-brand-error/5 transition-all ${
              isCollapsed ? "md:justify-center md:px-0 py-2.5" : "px-4 py-2.5 gap-3"
            }`}
          >
            <LogOut className="w-[18px] h-[18px] shrink-0 stroke-[1.75] text-brand-outline group-hover:text-brand-error transition-colors" />
            <span className={`${isCollapsed ? "md:hidden" : ""}`}>Sign out</span>

            {isCollapsed && (
              <div className="absolute left-full ml-4 px-2 py-1 bg-brand-surface-container-high text-brand-on-surface text-xs rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 hidden md:block shadow-brand-sm border border-brand-outline-variant/20">
                Sign out
              </div>
            )}
          </a>


        </div>
      </aside>
    </>
  );
}
