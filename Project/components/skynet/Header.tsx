"use client";

import React from "react";
import { Search, Bell, Monitor, User, ShieldCheck } from "lucide-react";

export default function Header() {
  return (
    <header className="h-16 border-b border-emerald-500/10 flex items-center justify-between px-8 bg-[#0a0f1d]/50 backdrop-blur-md z-40">
      {/* Search Bar */}
      <div className="relative w-96 group">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-emerald-400 transition-colors" />
        <input 
          type="text" 
          placeholder="Search commands, skills, or projects..." 
          className="w-full bg-slate-900/50 border border-slate-800 rounded-lg py-1.5 pl-10 pr-4 text-sm text-slate-200 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all placeholder:text-slate-600"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800 text-[10px] text-slate-500 font-mono">
          /
        </div>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-4">
        {/* Status Badge */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">System Secure</span>
        </div>

        <div className="h-4 w-px bg-slate-800" />

        <div className="flex items-center gap-2">
          <button className="p-2 text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-all relative">
            <Bell className="w-5 h-5" />
            <span className="absolute top-2 right-2 w-2 h-2 bg-emerald-500 rounded-full border-2 border-[#0a0f1d]" />
          </button>
          
          <button className="p-2 text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-all">
            <Monitor className="w-5 h-5" />
          </button>
          
          <div className="h-8 w-px bg-slate-800 mx-2" />

          <button className="flex items-center gap-3 pl-2 pr-1 py-1 rounded-lg hover:bg-slate-800/50 transition-all group">
            <div className="flex flex-col items-end">
              <span className="text-xs font-bold text-slate-200 group-hover:text-emerald-400 transition-colors">Admin Controller</span>
              <span className="text-[10px] text-slate-500 font-mono">0x742d...421e</span>
            </div>
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-sky-600 flex items-center justify-center border-2 border-emerald-500/20 group-hover:border-emerald-500/50 transition-all shadow-[0_0_10px_rgba(16,185,129,0.2)]">
              <User className="w-4 h-4 text-white" />
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}
