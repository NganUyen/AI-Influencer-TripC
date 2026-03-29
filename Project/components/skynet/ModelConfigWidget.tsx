"use client";

import React from "react";
import { Cpu, Zap, Hash, Database, Sliders, ChevronDown } from "lucide-react";
import { motion } from "framer-motion";

interface ModelConfigProps {
  settings?: {
    access_mode: string;
    customer_api: {
      api_url: string | null;
      has_api_key: boolean;
    };
    workspace_default: {
      api_url: string;
    };
    effective_status: {
      ready: boolean;
      message: string;
    };
    primary_model?: string;
    fallback_model?: string;
    context_tokens?: number;
    max_concurrent?: number;
  } | null;
}

export default function ModelConfigWidget({ settings }: ModelConfigProps) {
  const mode = settings?.access_mode || "workspace_default";
  const primaryModel = settings?.primary_model || "gpt-4o";
  const fallbackModel = settings?.fallback_model || "gpt-3.5-turbo";
  const contextTokens = settings?.context_tokens || 128000;
  const maxConcurrent = settings?.max_concurrent || 5;
  const statusMessage = settings?.effective_status.message || "Initializing...";

  return (
    <div className="bg-[#0d1526]/50 backdrop-blur-md border border-emerald-500/10 rounded-xl overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-emerald-500/10 flex items-center justify-between bg-emerald-500/5">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Cấu hình model</h2>
        </div>
        <div className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest ${
          mode === "platform_managed" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-sky-500/20 text-sky-400 border border-sky-500/30"
        }`}>
          {mode.replace("_", " ")}
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4 flex-1">
        {/* Primary Model */}
        <div className="space-y-1.5">
          <label className="text-[10px] text-slate-500 uppercase tracking-widest font-bold flex items-center gap-1.5">
            <Zap className="w-3 h-3 text-emerald-400" />
            Primary (ollama)
          </label>
          <div className="flex items-center justify-between p-2 bg-slate-900/80 border border-slate-700/50 rounded-lg group cursor-pointer hover:border-emerald-500/30 transition-all">
            <span className="text-sm font-mono text-slate-200">{primaryModel}</span>
            <ChevronDown className="w-4 h-4 text-slate-500 group-hover:text-emerald-400" />
          </div>
        </div>

        {/* Fallback Model */}
        <div className="space-y-1.5 opacity-60 hover:opacity-100 transition-opacity">
          <label className="text-[10px] text-slate-500 uppercase tracking-widest font-bold flex items-center gap-1.5">
            <Database className="w-3 h-3" />
            Fallback (remote)
          </label>
          <div className="flex items-center justify-between p-2 bg-slate-900/40 border border-slate-800 rounded-lg text-sm font-mono text-slate-400">
            <span>{fallbackModel}</span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <div className="p-3 bg-slate-900/80 border border-slate-700/50 rounded-lg space-y-1 group">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500 uppercase tracking-widest font-bold group-hover:text-emerald-400 transition-colors">
              <Hash className="w-3 h-3" />
              Context
            </div>
            <div className="text-xl font-bold text-slate-200 font-mono tracking-tight">
              {(contextTokens / 1000).toFixed(0)}K
            </div>
          </div>
          
          <div className="p-3 bg-slate-900/80 border border-slate-700/50 rounded-lg space-y-1 group">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500 uppercase tracking-widest font-bold group-hover:text-emerald-400 transition-colors">
              <Sliders className="w-3 h-3" />
              Concurrent
            </div>
            <div className="text-xl font-bold text-slate-200 font-mono tracking-tight">
              {maxConcurrent}x
            </div>
          </div>
        </div>

        {/* Visual Waveform Accent or similar */}
        <div className="h-12 w-full mt-4 bg-slate-900/50 rounded-lg border border-slate-800/50 overflow-hidden relative group">
          <div className="absolute inset-0 flex items-center justify-around px-2 opacity-30 group-hover:opacity-60 transition-opacity">
            {[...Array(20)].map((_, i) => {
              const height = (Math.sin(i * 0.5) + 1.5) * 15;
              return (
                <motion.div 
                  key={i}
                  animate={{ height: [height, height * 1.5, height] }}
                  transition={{ repeat: Infinity, duration: 1.5, delay: i * 0.1 }}
                  className="w-1 bg-emerald-500 rounded-full" 
                  style={{ height: `${height}%` }}
                />
              );
            })}
          </div>
          <div className="absolute inset-x-0 bottom-0 h-px bg-emerald-500/20" />
        </div>
      </div>
    </div>
  );
}
