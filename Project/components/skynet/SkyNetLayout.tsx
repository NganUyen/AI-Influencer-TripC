"use client";

import React, { ReactNode } from "react";
import Sidebar from "@/components/skynet/Sidebar";
import Header from "@/components/skynet/Header";

interface SkyNetLayoutProps {
  children: ReactNode;
  activeTab?: string;
  onTabChange?: (tab: string) => void;
}

export default function SkyNetLayout({ children, activeTab, onTabChange }: SkyNetLayoutProps) {
  return (
    <div className="flex h-screen w-full bg-[#0a0f1d] text-slate-300 font-sans selection:bg-emerald-500/30 overflow-hidden">
      {/* Sidebar - Fixed width */}
      <Sidebar activeTab={activeTab} onTabChange={onTabChange} />

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden relative">
        {/* Background Grid Accent */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-20 pointer-events-none" />
        
        <Header />

        <main className="flex-1 overflow-y-auto p-6 relative">
          <div className="max-w-[1600px] mx-auto space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
