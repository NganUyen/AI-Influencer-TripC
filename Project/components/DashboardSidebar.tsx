"use client";

import { useState } from "react";
import { X, ChevronLeft, ChevronRight, HelpCircle, LogOut, ExternalLink } from "lucide-react";
import { SocialIcon } from "@/components/ui/SocialIcon";
import { cn } from "@/lib/utils";
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
  onMobileClose = () => { },
}: DashboardSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const sidebarClasses = cn(
    "fixed inset-y-0 left-0 z-50 flex h-full shrink-0 flex-col overflow-y-auto border-r border-brand-outline-variant/18 bg-brand-surface-variant p-5 shadow-brand-xl transition-all duration-300 ease-in-out",
    "md:sticky md:top-16 md:z-40 md:h-[calc(100vh-64px)] md:rounded-r-panel md:shadow-none",
    isMobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
    isCollapsed ? "md:w-20" : "w-64 md:w-60",
  );

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
        <div className={`mb-6 px-3 pt-2 flex items-center justify-between ${isCollapsed ? "md:justify-center md:px-0" : ""}`}>
          <div className={`${isCollapsed ? "md:hidden" : ""}`}>
            <h2 className="text-base font-bold text-brand-on-surface font-headline">AI-Influencer</h2>
            <p className="text-xs text-brand-outline mt-0.5 uppercase tracking-widest">Factory</p>
          </div>

          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={`hidden md:flex w-7 h-7 rounded-full bg-white/95 border border-brand-outline-variant/40 items-center justify-center text-brand-on-surface-variant hover:text-brand-primary hover:bg-white shadow-brand-md transition-all duration-300 ease-in-out z-[70] backdrop-blur-sm flex-shrink-0 ${isCollapsed
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
            className="-mr-2 flex h-11 w-11 items-center justify-center rounded-card text-brand-outline-variant hover:bg-brand-surface-container md:hidden"
            aria-label="Close menu"
          >
            <X className="w-5 h-5 stroke-[1.75]" />
          </button>
        </div>

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
                className={cn(
                  "group relative flex w-full min-h-[44px] items-center rounded-card px-4 py-3 text-sm font-medium transition-all duration-200 ease-out",
                  isCollapsed ? "md:justify-center" : "gap-3",
                  isActive
                    ? "dashboard-card bg-white text-brand-primary shadow-brand-sm"
                    : "text-brand-on-surface-variant hover:bg-white/60 hover:text-brand-primary",
                )}
              >
                <Icon
                  className={`h-[18px] w-[18px] shrink-0 stroke-[1.75] transition-colors ${isActive ? "text-brand-primary" : "text-brand-outline group-hover:text-brand-primary"
                    }`}
                />
                <span className={`truncate font-semibold ${isCollapsed ? "md:hidden" : ""}`}>{tab.label}</span>
                {isActive && !isCollapsed && (
                  <span className="ml-auto w-2 h-2 rounded-full bg-brand-primary" />
                )}

                {isCollapsed && (
                  <div className="dashboard-card pointer-events-none absolute left-full z-50 ml-4 hidden whitespace-nowrap px-2 py-1 text-xs text-brand-on-surface opacity-0 transition-opacity group-hover:opacity-100 md:block">
                    {TAB_SUBTITLES[tab.id] || tab.label}
                  </div>
                )}
              </button>
            );
          })}
        </nav>

        <div className="pt-4 border-t border-brand-outline-variant/30 space-y-1 mt-auto">
          {telegramBotUrl && (
            <a
              href={telegramBotUrl}
              target="_blank"
              rel="noreferrer"
              title="Telegram Bot"
              className={`group relative flex items-center min-h-[44px] rounded-card text-sm font-semibold text-brand-on-surface-variant hover:text-brand-primary hover:bg-white/50 transition-all cursor-pointer ${isCollapsed ? "md:justify-center md:px-0 py-3" : "px-4 py-3 gap-3"
                } mb-1`}
            >
              <SocialIcon platform="telegram" size={18} className="shrink-0" />
              <span className={`${isCollapsed ? "md:hidden" : ""}`}>Open Telegram Bot</span>
              <ExternalLink className={`w-3.5 h-3.5 ml-auto opacity-40 stroke-[1.75] ${isCollapsed ? "md:hidden" : ""}`} />

              {isCollapsed && (
                <div className="dashboard-card pointer-events-none absolute left-full z-50 ml-4 hidden whitespace-nowrap px-2 py-1 text-xs text-brand-on-surface opacity-0 transition-opacity group-hover:opacity-100 md:block">
                  Open Telegram Bot
                </div>
              )}
            </a>
          )}

          <a
            href="/help"
            title="Help & Docs"
            className={`group relative flex items-center min-h-[44px] rounded-card text-sm text-brand-on-surface-variant hover:text-brand-primary hover:bg-white/50 transition-all cursor-pointer ${isCollapsed ? "md:justify-center md:px-0 py-2.5" : "px-4 py-2.5 gap-3"
              }`}
          >
            <HelpCircle className="w-[18px] h-[18px] shrink-0 stroke-[1.75] text-brand-outline group-hover:text-brand-primary transition-colors" />
            <span className={`${isCollapsed ? "md:hidden" : ""}`}>Help &amp; Docs</span>

            {isCollapsed && (
              <div className="dashboard-card pointer-events-none absolute left-full z-50 ml-4 hidden whitespace-nowrap px-2 py-1 text-xs text-brand-on-surface opacity-0 transition-opacity group-hover:opacity-100 md:block">
                Help & Docs
              </div>
            )}
          </a>

          <a
            href="/auth"
            title="Sign out"
            className={`group relative flex items-center min-h-[44px] rounded-card text-sm text-brand-on-surface-variant hover:text-brand-error hover:bg-brand-error/5 transition-all cursor-pointer ${isCollapsed ? "md:justify-center md:px-0 py-2.5" : "px-4 py-2.5 gap-3"
              }`}
          >
            <LogOut className="w-[18px] h-[18px] shrink-0 stroke-[1.75] text-brand-outline group-hover:text-brand-error transition-colors" />
            <span className={`${isCollapsed ? "md:hidden" : ""}`}>Sign out</span>

            {isCollapsed && (
              <div className="dashboard-card pointer-events-none absolute left-full z-50 ml-4 hidden whitespace-nowrap px-2 py-1 text-xs text-brand-on-surface opacity-0 transition-opacity group-hover:opacity-100 md:block">
                Sign out
              </div>
            )}
          </a>
        </div>
      </aside>
    </>
  );
}
