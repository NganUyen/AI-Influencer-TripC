"use client";

import React from "react";
import { Edit2, Download, Send, RotateCcw } from "lucide-react";

interface OverviewTabProps {
  campaigns: any[];
  approvals: any[];
  content: any[];
  personas: any[];
  systemSummary: any;
  onTabChange: (tabId: any) => void;
  activityItems: any[];
  quotaWarnings: any[];
}

export function OverviewTab({
  campaigns,
  approvals,
  content,
  personas,
  systemSummary,
  onTabChange,
  activityItems,
  quotaWarnings,
}: OverviewTabProps) {
  return (
    <div className="space-y-8 animate-fade-in relative">
      <section className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
        {/* 1. Production Queue (Vertical List) */}
        <div className="xl:col-span-4 flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold tracking-tight text-on-surface font-headline">Production Queue</h2>
            <span className="dashboard-pill dashboard-pill-muted text-[11px] uppercase tracking-wider">
              Active ({activityItems.length || 0})
            </span>
          </div>

          <div className="space-y-4">
            {activityItems.length > 0 ? (
              activityItems.slice(0, 5).map((item, index) => (
                <article
                  key={item.id || index}
                  className="dashboard-card flex items-center gap-4 p-5"
                >
                  <div className="relative">
                    <img
                      alt="Persona"
                      className="w-12 h-12 rounded-full object-cover ring-2 ring-background shadow-md"
                      src={item.personaImage || "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=128&h=128&auto=format&fit=crop"}
                      width={48}
                      height={48}
                    />
                    <div className="absolute -bottom-1 -right-1 bg-surface-container-lowest p-1 rounded-full shadow-sm">
                      <img
                        alt="App"
                        className="w-4 h-4 rounded-sm"
                        src={item.appIcon || "https://cdn-icons-png.flaticon.com/512/124/124010.png"}
                        width={16}
                        height={16}
                      />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-end mb-2">
                      <p className="text-sm font-bold text-on-surface truncate">{item.title || "New Task"}</p>
                      <span className={`text-[10px] font-bold ${item.tone === 'success' ? 'text-tertiary' : item.tone === 'warning' ? 'text-secondary' : 'text-primary'}`}>
                        {item.detail?.split('•')[0] || "Active"}
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-surface-container rounded-full overflow-hidden">
                      <div 
                        className={`h-full bg-gradient-to-r ${item.tone === 'success' ? 'from-tertiary to-tertiary-container' : 'from-primary to-primary-container'} transition-all duration-1000`} 
                        style={{ width: `${item.progress || (item.detail?.includes('%') ? parseInt(item.detail.match(/(\d+)%/)?.[1] || '0') : (70 - index * 10))}%` }}
                      ></div>
                    </div>
                  </div>
                  <div className="text-xs font-semibold text-on-surface-variant w-12 text-right">
                    {item.timeLabel || "08:42"}
                  </div>
                </article>
              ))
            ) : (
               <div className="dashboard-panel-soft flex flex-col items-center justify-center border-2 border-dashed border-surface-container py-12 text-on-surface-variant/40">
                 <span className="material-symbols-outlined text-4xl mb-2">movie_filter</span>
                 <p className="text-sm font-medium text-center">No active production tasks</p>
               </div>
            )}

            {/* Mock Completion item if there are no items or just to show the style */}
            <div className="dashboard-card-muted flex items-center gap-4 border-transparent p-5 opacity-70">
              <div className="relative">
                <div className="w-12 h-12 rounded-full bg-surface-container flex items-center justify-center ring-2 ring-background shadow-md overflow-hidden">
                  <img
                    alt="Persona"
                    className="w-full h-full object-cover"
                    src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=128&h=128&auto=format&fit=crop"
                    width={48}
                    height={48}
                  />
                </div>
                <div className="absolute -bottom-1 -right-1 bg-surface-container-lowest p-1 rounded-full shadow-sm text-tertiary">
                  <span className="material-symbols-outlined text-xs" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                </div>
              </div>
              <div className="flex-1">
                <div className="flex justify-between items-end mb-1">
                  <p className="text-sm font-bold text-on-surface">Minh - VN Review</p>
                  <span className="text-[10px] font-bold text-on-surface-variant">Completed</span>
                </div>
                <div className="text-[10px] text-on-surface-variant uppercase font-bold tracking-tight opacity-60">Published 14m ago</div>
              </div>
              <div className="text-xs font-semibold text-on-surface-variant w-12 text-right">Final</div>
            </div>
          </div>
        </div>

        {/* 2. Live Result Feed (Masonry Style Grid) */}
        <div className="xl:col-span-8 flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold tracking-tight text-on-surface font-headline">Live Result Feed</h2>
            <div className="flex gap-2">
              <button className="dashboard-pill dashboard-pill-muted text-[11px] text-on-surface hover:bg-surface-container-highest">All Regions</button>
              <button className="dashboard-pill text-[11px] font-bold text-on-surface-variant hover:bg-surface-container-low">US Only</button>
            </div>
          </div>

          <div className="columns-1 md:columns-2 gap-6 space-y-6">
            {content.length > 0 ? (
              content.map((video, index) => (
                <div 
                  key={video.id || index}
                  className="dashboard-panel break-inside-avoid group relative overflow-hidden p-0 shadow-lg shadow-on-surface/5"
                >
                  <div className={`relative ${index % 3 === 0 ? 'aspect-[9/16]' : 'aspect-[4/5]'} overflow-hidden`}>
                    <img 
                      alt="Result"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                      src={video.thumbnail || `https://images.unsplash.com/photo-1621609764095-b32bbe35cf3a?q=80&w=800&auto=format&fit=crop`}
                      width={800}
                      height={index % 3 === 0 ? 1422 : 1000}
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-60 group-hover:opacity-80 transition-opacity"></div>
                    
                    <div className="absolute top-4 left-4 px-2 py-1 bg-black/40 backdrop-blur-md rounded-lg text-[10px] font-bold text-white uppercase tracking-widest flex items-center gap-1.5 border border-white/10">
                      <span className={`w-1.5 h-1.5 ${index % 2 === 0 ? 'bg-red-500 animate-pulse' : 'bg-green-500'} rounded-full`}></span> 
                      {video.region || 'US'} • {video.category || 'TECH'}
                    </div>

                    <div className="absolute bottom-4 left-4 right-4 space-y-3">
                      <p className="text-white font-bold leading-tight line-clamp-2 text-sm">
                        {video.title || "Untitled Production"}
                      </p>
                      <div className="flex flex-wrap gap-2 transform translate-y-2 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-300">
                        <button className="flex-1 py-2 bg-white/20 backdrop-blur-xl hover:bg-white/30 text-white rounded-full text-[10px] font-bold flex items-center justify-center gap-1 transition-all border border-white/10">
                          <Edit2 className="w-3 h-3" /> Edit Script
                        </button>
                        <button className="w-10 h-10 bg-white/20 backdrop-blur-xl hover:bg-white/30 text-white rounded-full flex items-center justify-center transition-all border border-white/10">
                          <Download className="w-4 h-4" />
                        </button>
                        <button className="w-full py-2.5 bg-primary-fixed text-on-primary-fixed font-black text-[11px] rounded-full flex items-center justify-center gap-2 shadow-lg shadow-primary/20">
                          <Send className="w-4 h-4" /> PUBLISH TO SOCIALS
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            ) : (
               <div className="dashboard-panel-soft col-span-full flex flex-col items-center justify-center border-2 border-dashed border-surface-container bg-surface-container-low py-24 text-on-surface-variant/40">
                <span className="material-symbols-outlined text-6xl mb-4">video_library</span>
                <p className="text-lg font-bold">No published content yet</p>
                <p className="text-sm">Start your first production in the Video Engine</p>
                <button 
                  onClick={() => onTabChange("ops")}
                  className="mt-6 bg-primary text-on-primary px-8 py-3 rounded-full font-bold shadow-lg shadow-primary/20 hover:scale-105 active:scale-95 transition-all"
                >
                  Create New Video
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 3. Floating System Health Panel */}
      <div className="dashboard-panel-soft relative mt-8 w-full overflow-hidden border border-surface-container animate-slide-up group xl:fixed xl:bottom-8 xl:right-8 xl:mt-0 xl:w-80">
        <div className="p-5 border-b border-surface-container flex items-center justify-between bg-surface-container-low/50">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-tertiary rounded-full animate-pulse"></span>
            <h3 className="font-bold text-sm tracking-tight text-on-surface">System Health</h3>
          </div>
          <span className="text-[10px] font-black text-on-surface-variant opacity-60">
            {systemSummary?.services?.length || 10} / 10 ACTIVE
          </span>
        </div>
        
        <ul className="p-4 space-y-3 max-h-64 overflow-y-auto scrollbar-hide">
          {(systemSummary?.services || [
            { name: "@techreview_us", status: "online", image: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?q=80&w=128&h=128&auto=format&fit=crop" },
            { name: "@londondiaries_uk", status: "online", image: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=128&h=128&auto=format&fit=crop" },
            { name: "@vietnam_daily", status: "online", image: "https://images.unsplash.com/photo-1607746882042-944635dfe10e?q=80&w=128&h=128&auto=format&fit=crop" },
            { name: "@paris_vibes", status: "warning", image: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?q=80&w=128&h=128&auto=format&fit=crop" }
          ]).map((service: any, idx: number) => (
            <li
              key={service.name || idx} 
              className={`flex items-center justify-between rounded-lg p-2 ${service.status === 'warning' ? 'bg-secondary-container/10' : 'bg-transparent'}`}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center overflow-hidden border border-surface-container">
                  <img alt="acct" className="w-full h-full object-cover" src={service.image} width={32} height={32} />
                </div>
                <span className={`text-xs font-bold ${service.status === 'warning' ? 'text-secondary-dim' : 'text-on-surface'}`}>
                  {service.name}
                </span>
              </div>
              {service.status === 'warning' ? (
                <RotateCcw className="w-4 h-4 text-secondary animate-spin-slow" />
              ) : (
                <span className="material-symbols-outlined text-tertiary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
              )}
            </li>
          ))}
        </ul>
        
        <div className="p-3 bg-surface-container text-center">
          <button className="text-[10px] font-black text-on-surface-variant hover:text-primary transition-all tracking-wider uppercase">
            MANAGE CONNECTIONS
          </button>
        </div>
      </div>
    </div>
  );
}
