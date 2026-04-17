"use client";

import React from "react";
import { 
  Send, 
  Clock, 
  CheckCircle2, 
  AlertCircle, 
  ExternalLink,
  Share2,
  Calendar,
  Globe,
  Filter,
  Search
} from "lucide-react";
import { cn } from "@/lib/utils";
import { type ReviewEngineJob } from "@/lib/review-engine";

interface PublishingTabProps {
  jobs: ReviewEngineJob[];
}

export function PublishingTab({ jobs }: PublishingTabProps) {
  const [searchTerm, setSearchTerm] = React.useState("");

  const publishingJobs = jobs.filter(j => 
      j.publish?.requested || j.publish?.status === "published" || j.publish?.status === "failed" || j.publish?.status === "scheduled" || j.publish?.status === "auth_required"
  );

  const filteredContent = publishingJobs.filter(item => 
    (item.content?.title || item.page_title || "App Review").toLowerCase().includes(searchTerm.toLowerCase()) ||
    (item.target_platform || "tiktok").toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusIcon = (status?: string | null) => {
    switch (status?.toLowerCase()) {
      case "published":
        return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
      case "scheduled":
      case "ready_to_publish":
        return <Clock className="w-4 h-4 text-aura-primary" />;
      case "failed":
      case "auth_required":
        return <AlertCircle className="w-4 h-4 text-rose-500" />;
      default:
        return <Send className="w-4 h-4 text-aura-on-surface-variant" />;
    }
  };

  const getStatusColor = (status?: string | null) => {
    switch (status?.toLowerCase()) {
      case "published":
        return "bg-emerald-50 text-emerald-700 border-emerald-100";
      case "scheduled":
      case "ready_to_publish":
        return "bg-aura-primary/10 text-aura-primary border-aura-primary/10";
      case "failed":
      case "auth_required":
        return "bg-rose-50 text-rose-700 border-rose-100";
      default:
        return "bg-aura-surface-container text-aura-on-surface-variant border-aura-outline/10";
    }
  };

  return (
    <div className="space-y-10 animate-fade-in pb-20">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-4xl font-extrabold text-aura-on-surface font-headline tracking-tight">Post Publishing</h1>
          <p className="text-aura-on-surface-variant max-w-2xl text-lg font-body">
            Manage your global content distribution. Monitor scheduled posts, track published performance, and resolve delivery issues across all platforms.
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-aura-on-surface-variant group-focus-within:text-aura-primary transition-colors" />
            <input 
              type="text"
              placeholder="Search content..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-11 pr-6 py-3 bg-white border border-aura-outline-variant/15 rounded-full text-sm font-medium text-aura-on-surface shadow-aura-sm focus:ring-2 focus:ring-aura-primary/10 transition-all outline-none w-64"
            />
          </div>
          <button className="p-3 bg-white border border-aura-outline-variant/15 rounded-full shadow-aura-sm hover:bg-aura-surface-container transition-colors">
            <Filter className="w-4 h-4 text-aura-on-surface-variant" />
          </button>
        </div>
      </header>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="dashboard-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 flex items-center justify-center text-emerald-500">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-bold text-aura-on-surface-variant uppercase tracking-widest font-label">Published</p>
            <p className="text-3xl font-black text-aura-on-surface font-headline">{publishingJobs.filter(c => c.publish?.status === "published").length}</p>
          </div>
        </div>
        <div className="dashboard-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-2xl bg-aura-primary/10 flex items-center justify-center text-aura-primary">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-bold text-aura-on-surface-variant uppercase tracking-widest font-label">Scheduled</p>
            <p className="text-3xl font-black text-aura-on-surface font-headline">{publishingJobs.filter(c => c.publish?.status === "scheduled" || c.publish?.status === "ready_to_publish").length}</p>
          </div>
        </div>
        <div className="dashboard-panel p-6 flex items-center gap-5">
          <div className="w-12 h-12 rounded-2xl bg-rose-50 flex items-center justify-center text-rose-500">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-bold text-aura-on-surface-variant uppercase tracking-widest font-label">Failed / Auth</p>
            <p className="text-3xl font-black text-aura-on-surface font-headline">{publishingJobs.filter(c => c.publish?.status === "failed" || c.publish?.status === "auth_required").length}</p>
          </div>
        </div>
      </div>

      {/* Content List */}
      <div className="dashboard-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-aura-outline-variant/10">
                <th className="px-8 py-5 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">Content Title</th>
                <th className="px-8 py-5 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">Platforms</th>
                <th className="px-8 py-5 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">Status</th>
                <th className="px-8 py-5 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">Timing</th>
                <th className="px-8 py-5 text-right text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70 font-label">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-aura-outline-variant/5">
              {filteredContent.length > 0 ? (
                filteredContent.map((item) => (
                  <tr key={item.job_id} className="group hover:bg-aura-surface-container-lowest transition-colors">
                    <td className="px-8 py-6">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-aura-surface-container flex items-center justify-center shrink-0 border border-aura-outline-variant/10">
                          <Globe className="w-5 h-5 text-aura-on-surface-variant" />
                        </div>
                        <span className="font-bold text-aura-on-surface font-headline truncate max-w-[200px]" title={item.content?.title || item.page_title || "App Review"}>
                          {item.content?.title || item.page_title || "App Review"}
                        </span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex gap-1.5 flex-wrap">
                        {[(item.target_platform || "tiktok")].map(p => (
                          <span key={p} className="px-2.5 py-1 bg-aura-surface-container rounded-full text-[10px] font-bold text-aura-on-surface-variant uppercase tracking-widest border border-aura-outline/5">
                            {p}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-8 py-6 text-sm">
                      <div className={cn(
                        "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest border transition-all",
                        getStatusColor(item.publish?.status)
                      )}>
                        {getStatusIcon(item.publish?.status)}
                        {(item.publish?.status || "Draft").replace(/_/g, " ")}
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2 text-xs font-semibold text-aura-on-surface">
                          <Calendar className="w-3 h-3 text-aura-primary/60" />
                          {item.published_at ? new Date(item.published_at).toLocaleDateString() : item.scheduled_at ? new Date(item.scheduled_at).toLocaleDateString() : "Pending"}
                        </div>
                        <div className="text-[10px] text-aura-on-surface-variant font-medium font-body opacity-60">
                           {item.published_at ? new Date(item.published_at).toLocaleTimeString() : item.scheduled_at ? new Date(item.scheduled_at).toLocaleTimeString() : "Pending"}
                        </div>
                      </div>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button className="p-2 hover:bg-aura-primary/10 hover:text-aura-primary rounded-lg transition-all" title="View details">
                          <ExternalLink className="w-4 h-4" />
                        </button>
                        <button className="p-2 hover:bg-aura-primary/10 hover:text-aura-primary rounded-lg transition-all" title="Share">
                          <Share2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-8 py-20 text-center">
                    <div className="flex flex-col items-center gap-4">
                      <div className="w-16 h-16 rounded-full bg-aura-surface-container flex items-center justify-center">
                        <Search className="w-8 h-8 text-aura-on-surface-variant/20" />
                      </div>
                      <div className="space-y-1">
                        <p className="text-aura-on-surface font-bold font-headline">No content found</p>
                        <p className="text-aura-on-surface-variant text-sm font-body">Try adjusting your search or filters.</p>
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
