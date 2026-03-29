"use client";

import React from "react";
import { Activity, CheckCircle, XCircle, AlertTriangle, ShieldCheck } from "lucide-react";

interface HealthProps {
  services?: {
    name: string;
    status: string;
    latency: string;
  }[];
  quota?: any;
}

export default function SystemHealthWidget({ services, quota }: HealthProps) {
  const providers = quota?.providers || [
    { label: "OpenAI", status: "ok", usage_value: 45, monthly_limit: 100 },
    { label: "HeyGen", status: "warning", usage_value: 82, monthly_limit: 100 },
  ];

  const orchestrationServices = services || [
    { name: "Gateway API", status: "online", latency: "14ms" },
    { name: "Temporal Worker", status: "online", latency: "2ms" },
    { name: "Cron Scheduler", status: "online", latency: "8ms" },
    { name: "AI Roster Store", status: "online", latency: "3ms" }
  ];

  return (
    <div className="bg-[#0d1526]/50 backdrop-blur-md border border-emerald-500/10 rounded-xl flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-emerald-500/10 flex items-center justify-between bg-emerald-500/5">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Sức khỏe hệ thống</h2>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-0.5 bg-emerald-500/20 rounded border border-emerald-500/30 text-[10px] font-bold text-emerald-400">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
          Live Monitoring
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-5 flex-1">
        {/* Orchestration Services */}
        <div className="space-y-2.5">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold px-1">Orchestration Nodes</p>
          
          <div className="space-y-1.5">
            {orchestrationServices.map((node, i) => {
              const statusKey = node.status === "online" || node.status === "ok" ? "ok" : 
                               node.status === "warning" ? "warning" : "critical";
              return (
                <div key={i} className="flex items-center justify-between p-2 bg-slate-900/60 border border-slate-800/80 rounded-lg group hover:border-emerald-500/30 transition-all">
                  <div className="flex items-center gap-3">
                    {statusKey === "ok" ? 
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400/70 group-hover:text-emerald-400 transition-colors" /> : 
                      statusKey === "warning" ?
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-500/70 group-hover:text-amber-500 transition-colors" /> :
                      <XCircle className="w-3.5 h-3.5 text-rose-500/70 group-hover:text-rose-500 transition-colors" />
                    }
                    <span className="text-xs font-medium text-slate-300 group-hover:text-white transition-colors uppercase tracking-tight">{node.name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-1 w-12 bg-slate-800 rounded-full overflow-hidden">
                      <div className={`h-full ${statusKey === "ok" ? "bg-emerald-500" : statusKey === "warning" ? "bg-amber-500" : "bg-rose-500"} w-[100%]`} />
                    </div>
                    <span className="text-[10px] font-mono text-slate-500">{node.latency}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* API Quota Health */}
        <div className="space-y-3 pt-2">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold px-1">Service Connectivity</p>
          
          <div className="grid grid-cols-1 gap-4">
            {providers.slice(0, 3).map((provider: any, i: number) => {
              const usagePercent = provider.monthly_limit ? (provider.usage_value / provider.monthly_limit) * 100 : 0;
              return (
                <div key={i} className="space-y-1.5">
                  <div className="flex justify-between items-center text-[10px] font-mono">
                    <span className="text-slate-400 font-bold uppercase tracking-wider">{provider.label}</span>
                    <span className={`px-1.5 py-0.5 rounded ${
                      provider.status === "ok" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                    }`}>
                      {provider.status === "ok" ? "Ready" : "Warning"}
                    </span>
                  </div>
                  <div className="h-2 bg-slate-800 rounded-full overflow-hidden flex gap-0.5 border border-slate-700/50">
                    <div 
                      className={`h-full rounded-full transition-all duration-1000 ${
                        provider.status === "ok" ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]" : "bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                      }`} 
                      style={{ width: `${Math.max(usagePercent, 5)}%` }} 
                    />
                    <div className="flex-1" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Bottom Footer Stats */}
        <div className="grid grid-cols-3 gap-2 mt-auto pt-4 border-t border-emerald-500/5">
          <div className="text-center">
            <p className="text-[9px] text-slate-500 uppercase font-bold">Uptime</p>
            <p className="text-xs text-emerald-400 font-mono">99.98%</p>
          </div>
          <div className="text-center border-x border-slate-800">
            <p className="text-[9px] text-slate-500 uppercase font-bold">Latency</p>
            <p className="text-xs text-sky-400 font-mono">24ms</p>
          </div>
          <div className="text-center">
            <p className="text-[9px] text-slate-500 uppercase font-bold">Threats</p>
            <p className="text-xs text-slate-500 font-mono">None</p>
          </div>
        </div>
      </div>
    </div>
  );
}
