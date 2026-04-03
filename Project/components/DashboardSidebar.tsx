"use client";

import type { DashboardTabId, DashboardTab } from "./customer-dashboard";

interface DashboardSidebarProps {
  tabs: DashboardTab[];
  activeTab: DashboardTabId;
  onTabChange: (tabId: DashboardTabId) => void;
}

export function DashboardSidebar({
  tabs,
  activeTab,
  onTabChange,
}: DashboardSidebarProps) {
  return (
    <aside className="fixed left-0 top-16 h-[calc(100vh-64px)] w-64 border-r border-white/[0.08] bg-zinc-950/50 backdrop-blur-xl pt-6 px-4">
      <div className="space-y-1">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={`w-full flex items-center gap-3 rounded-[12px] px-4 py-3 text-sm font-medium transition-all duration-200 ease-out ${
                isActive
                  ? "bg-gradient-to-r from-emerald-500/20 to-emerald-500/10 border border-emerald-500/30 text-white shadow-lg shadow-emerald-500/10"
                  : "text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-300"
              }`}
            >
              <tab.icon className="h-5 w-5 flex-shrink-0" />
              <span className="truncate">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}