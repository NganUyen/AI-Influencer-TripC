"use client";

import React from "react";
import { 
  BarChart3, 
  Cpu, 
  Database, 
  ExternalLink, 
  Activity, 
  Layers, 
  Terminal, 
  LayoutDashboard, 
  Settings, 
  Bot, 
  Zap, 
  History 
} from "lucide-react";
import { motion } from "framer-motion";

const NAV_ITEMS = [
  { id: "overview", label: "Tổng quan", icon: LayoutDashboard, status: "ok" },
  { id: "onyx", label: "Onyx Command", icon: Zap, status: "ok" },
  { id: "ops", label: "AI vận hành", icon: Bot, status: "warning" },
  { id: "cron", label: "Cron & Runtime", icon: History, status: "ok" },
  { id: "skills", label: "Skills hệ sinh thái", icon: Layers, status: "ok" },
  { id: "monetization", label: "Danh mục kiếm tiền", icon: BarChart3, status: "ok" },
  { id: "memory", label: "Dự án & Memory", icon: Database, status: "ok" },
  { id: "live_feed", label: "Live Feed", icon: Terminal, status: "active" },
];

interface SidebarProps {
  activeTab?: string;
  onTabChange?: (tab: string) => void;
}

export default function Sidebar({ activeTab = "overview", onTabChange }: SidebarProps) {
  return (
    <div className="w-64 h-full bg-[#0d1526]/80 backdrop-blur-xl border-r border-emerald-500/10 flex flex-col z-50">
      {/* Header */}
      <div className="p-6 border-b border-emerald-500/10">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30">
            <Activity className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wider uppercase">
              SkyNet <span className="text-emerald-400">Control</span>
            </h1>
          </div>
        </div>

        <div className="space-y-1">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Workspace Access</p>
          <div className="flex flex-col gap-1 text-xs">
            <span className="text-emerald-400/80 font-mono">CEO: <span className="text-white">OpenClaw</span></span>
            <span className="text-emerald-400/80 font-mono">Assistant: <span className="text-white">ThuyVy</span></span>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-4 py-6 scrollbar-hide">
        <div className="space-y-1 mb-10">
          {NAV_ITEMS.map((item) => (
            <motion.button
              key={item.id}
              onClick={() => onTabChange?.(item.id)}
              whileHover={{ x: 4 }}
              className={`flex items-center justify-between w-full px-3 py-2.5 rounded-lg transition-colors group ${
                activeTab === item.id 
                  ? "bg-emerald-500/10 text-emerald-400" 
                  : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center gap-3">
                <item.icon className={`w-4 h-4 ${activeTab === item.id ? "text-emerald-400" : "text-slate-500 group-hover:text-emerald-400"}`} />
                <span className="text-sm font-medium">{item.label}</span>
              </div>
              
              {/* Status Indicator */}
              <div className={`w-1.5 h-1.5 rounded-full ${
                item.status === "ok" ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] shadow-emerald-500/50" :
                item.status === "warning" ? "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)] shadow-amber-500/50" :
                item.status === "active" ? "bg-sky-500 shadow-[0_0_8px_rgba(14,165,233,0.5)] shadow-sky-500/50 animate-pulse" :
                "bg-slate-700"
              }`} />
            </motion.button>
          ))}
        </div>

        {/* Quick Links */}
        <div className="space-y-4 mb-6">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold px-3">Liên kết nhanh</p>
          <div className="space-y-1">
            <button className="flex items-center gap-2 px-3 py-1.5 w-full text-xs text-slate-400 hover:text-emerald-400 transition-colors">
              <ExternalLink className="w-3 h-3" />
              <span>Health API</span>
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 w-full text-xs text-slate-400 hover:text-emerald-400 transition-colors">
              <ExternalLink className="w-3 h-3" />
              <span>Monitor JSON</span>
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 w-full text-xs text-slate-400 hover:text-emerald-400 transition-colors">
              <ExternalLink className="w-3 h-3" />
              <span>Dashboard Link</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Resource Monitors */}
      <div className="p-4 border-t border-emerald-500/10 space-y-4">
        <div className="space-y-3">
          {/* CPU / GPU */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] font-mono text-slate-500">
              <span>CPU/GPU UTIL</span>
              <span className="text-emerald-400">42%</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 w-[42%]" />
            </div>
          </div>

          {/* Context Monitor */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] font-mono text-slate-500">
              <span>CONTX 128K</span>
              <span className="text-emerald-400">12.4k</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 w-[10%]" />
            </div>
          </div>

          <div className="p-2 bg-emerald-500/5 rounded border border-emerald-500/10">
            <div className="flex items-center gap-2">
              <Cpu className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] font-mono text-slate-400 truncate">ollama/qwen2.5:7b</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
