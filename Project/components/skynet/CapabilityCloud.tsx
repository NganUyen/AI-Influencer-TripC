"use client";

import React from "react";
import { 
  Lock, 
  BarChart2, 
  Apple, 
  FileText, 
  Github, 
  Layers, 
  MessageSquare, 
  Globe, 
  Shield, 
  Cpu, 
  Search, 
  Mail, 
  Clock, 
  Calendar, 
  Cloud,
  Terminal,
  Zap
} from "lucide-react";
import { motion } from "framer-motion";

const CAPABILITIES = [
  { label: "1password", icon: Lock },
  { label: "analytics", icon: BarChart2 },
  { label: "apple-notes", icon: Apple },
  { label: "arxiv", icon: FileText },
  { label: "assembly-ai", icon: Cpu },
  { label: "bash", icon: Terminal },
  { label: "brave-search", icon: Search },
  { label: "calendar", icon: Calendar },
  { label: "chat-history", icon: MessageSquare },
  { label: "cloud-storage", icon: Cloud },
  { label: "discord", icon: MessageSquare },
  { label: "evernote", icon: FileText },
  { label: "facebook", icon: Globe },
  { label: "github", icon: Github },
  { label: "gmail", icon: Mail },
  { label: "google-maps", icon: Globe },
  { label: "linear", icon: Layers },
  { label: "medium", icon: FileText },
  { label: "message-ops", icon: MessageSquare },
  { label: "openai", icon: Zap },
  { label: "postiz", icon: Zap },
  { label: "security", icon: Shield },
  { label: "slack", icon: MessageSquare },
  { label: "trello", icon: Layers },
];

export default function CapabilityCloud() {
  return (
    <div className="w-full bg-[#0d1526]/50 backdrop-blur-md border border-emerald-500/10 rounded-xl p-4 overflow-hidden relative">
      {/* Background Accent */}
      <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/5 to-transparent opacity-20" />
      
      <div className="flex flex-wrap gap-2 relative z-10">
        <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/20 rounded border border-emerald-500/30 text-[10px] font-bold text-emerald-400 uppercase tracking-widest mr-2">
          <Zap className="w-3 h-3" />
          Active Capabilities
        </div>

        {CAPABILITIES.map((cap, i) => (
          <motion.div
            key={cap.label}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.02 }}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-800/40 hover:bg-emerald-500/10 border border-slate-700/50 hover:border-emerald-500/30 rounded text-[11px] text-slate-400 hover:text-emerald-400 transition-all cursor-default group"
          >
            <cap.icon className="w-3 h-3 text-slate-500 group-hover:text-emerald-400 transition-colors" />
            <span className="font-mono">{cap.label}</span>
          </motion.div>
        ))}
        
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900/80 border border-dashed border-slate-700 rounded text-[11px] text-slate-500 font-mono italic">
          + 42 more...
        </div>
      </div>
    </div>
  );
}
