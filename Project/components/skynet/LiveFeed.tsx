"use client";

import React, { useRef, useEffect } from "react";
import { Terminal, Clock, Share2, Filter, MoreHorizontal } from "lucide-react";

interface LogEntry {
  id: string;
  time: string;
  type: "system" | "user" | "skill" | "error";
  message: string;
  status?: string;
}

const MOCK_LOGS: LogEntry[] = [
  { id: "1", time: "08:42:12", type: "system", message: "Temporal connection established", status: "ok" },
  { id: "2", time: "08:42:15", type: "skill", message: "Persona data sync initialized" },
  { id: "3", time: "08:43:01", type: "user", message: "Campaign 'Summer 2024' approved by controller" },
  { id: "4", time: "08:44:22", type: "system", message: "Gateway latency spike detected (142ms)", status: "warning" },
  { id: "5", time: "08:44:23", type: "system", message: "Gateway stabilized (14ms)", status: "ok" },
  { id: "6", time: "08:45:10", type: "skill", message: "Short Video Workflow started for persona @thuyvy" },
  { id: "7", time: "08:46:05", type: "system", message: "Quota snapshot recorded: OpenAI (Tokens: 14.5k)", status: "ok" },
  { id: "8", time: "08:47:33", type: "user", message: "Model configuration updated: qwen2.5:7b applied" },
];

export default function LiveFeed() {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  return (
    <div className="bg-[#0d1526]/50 backdrop-blur-md border border-emerald-500/10 rounded-xl overflow-hidden flex flex-col h-[400px]">
      {/* Header */}
      <div className="p-4 border-b border-emerald-500/10 flex items-center justify-between bg-emerald-500/5">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Live Feed ThuyVy</h2>
        </div>
        
        <div className="flex items-center gap-2">
          <button className="p-1 px-2 rounded bg-slate-800 hover:bg-slate-700 text-[10px] text-slate-400 transition-colors uppercase font-bold flex items-center gap-1.5 border border-slate-700">
            <Filter className="w-3 h-3" />
            Filter
          </button>
          <button className="p-1 px-2 rounded bg-slate-800 hover:bg-slate-700 text-[10px] text-slate-400 transition-colors uppercase font-bold flex items-center gap-1.5 border border-slate-700">
            <Share2 className="w-3 h-3" />
            Export
          </button>
          <button className="p-1 rounded text-slate-500 hover:text-emerald-400 transition-colors">
            <MoreHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Log Feed */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-hide font-mono text-[11px]"
      >
        {MOCK_LOGS.map((log) => (
          <div key={log.id} className="flex gap-4 group">
            <span className="text-slate-600 shrink-0 select-none">[{log.time}]</span>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className={`uppercase font-bold tracking-tighter ${
                  log.type === "system" ? "text-sky-400" :
                  log.type === "user" ? "text-emerald-400" :
                  log.type === "skill" ? "text-purple-400" :
                  "text-rose-400"
                }`}>
                  {log.type}
                </span>
                {log.status && (
                  <span className={`px-1 py-0 rounded-[2px] text-[8px] font-bold uppercase ${
                    log.status === "ok" ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20" :
                    log.status === "warning" ? "bg-amber-500/10 text-amber-500 border border-amber-500/20" :
                    "bg-rose-500/10 text-rose-500 border border-rose-500/20"
                  }`}>
                    {log.status}
                  </span>
                )}
                <span className="text-slate-300 transition-colors group-hover:text-emerald-200">{log.message}</span>
              </div>
            </div>
          </div>
        ))}
        
        {/* Active Cursor/Indicator */}
        <div className="flex gap-4">
          <span className="text-slate-600 shrink-0 select-none">[{new Date().toLocaleTimeString('en-GB')}]</span>
          <div className="flex items-center gap-2">
            <span className="text-emerald-400/50 animate-pulse font-bold">●</span>
            <span className="text-slate-500 italic">Listening for system events...</span>
          </div>
        </div>
      </div>

      {/* Bottom Bar/Actions */}
      <div className="p-2 px-4 bg-slate-900 border-t border-emerald-500/10 flex items-center gap-4">
        <div className="flex items-center gap-2 text-[10px] text-slate-500">
          <Clock className="w-3 h-3 text-emerald-400" />
          <span>Real-time polling: ACTIVE</span>
        </div>
        <div className="h-3 w-px bg-slate-800" />
        <div className="flex items-center gap-2 text-[10px] text-slate-500">
          <Database className="w-3 h-3 text-emerald-400" />
          <span>Stream ID: 0xFD2A...</span>
        </div>
      </div>
    </div>
  );
}

function Database(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5V19A9 3 0 0 0 21 19V5" />
      <path d="M3 12A9 3 0 0 0 21 12" />
    </svg>
  );
}
