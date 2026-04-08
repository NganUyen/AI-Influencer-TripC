"use client";

import { TimelineItem } from "@/components/ui/TimelineItem";
import { useCallback, useEffect, useMemo, useState } from "react";
import { 
  LayoutDashboard, 
  Cpu, 
  Database, 
  Activity, 
  Search, 
  Bell, 
  Settings, 
  LogOut, 
  Plus, 
  RefreshCw, 
  Zap, 
  Pause, 
  X, 
  CheckCircle2, 
  MoreVertical,
  Rocket,
  Check,
  Layout
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { WORKFLOW_POLL_INTERVAL } from "@/config/constants";
import { useContentStore, type ContentItem } from "@/store/content-store";

// --- Types ---

type DashboardTab = "dashboard" | "ai-ops" | "memory" | "activity";

interface WorkflowListItem {
  workflow_id: string;
  run_id: string;
  status: string;
  start_time?: string;
  title?: string;
}

interface WorkflowStatusPayload {
  status: string;
  current_step?: string;
  approval_received?: boolean;
  approval_feedback?: string;
  workflow_id: string;
}

interface DashboardWorkflow extends WorkflowListItem {
  details?: WorkflowStatusPayload;
}

interface ContentStats {
  total_content: number;
  active_campaigns: number;
  published: number;
}

interface AnalyticsSummary {
  average_engagement_rate: number | null;
}

interface QuotaProviderSummary {
  provider: string;
  label: string;
  status: string;
  usage_unit: string;
  monthly_limit: number | null;
  cost_usd: number;
  usage_value: number;
  remaining_limit: number | null;
}

interface QuotaSummary {
  total_cost_usd: number;
  providers: QuotaProviderSummary[];
}

interface PersonaItem {
  id: string;
  display_name: string;
  role: string;
  status: string;
  avatar_image_url?: string;
}

// --- Main Component ---

export default function OpsConsole() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("dashboard");
  const [workflows, setWorkflows] = useState<DashboardWorkflow[]>([]);
  const [stats, setStats] = useState<ContentStats>({
    total_content: 0,
    active_campaigns: 0,
    published: 0,
  });
  const [analytics, setAnalytics] = useState<AnalyticsSummary>({
    average_engagement_rate: null,
  });
  const [quota, setQuota] = useState<QuotaSummary>({
    total_cost_usd: 0,
    providers: [],
  });
  const [personas, setPersonas] = useState<PersonaItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { items: contentItems, fetchItems } = useContentStore();

  const loadData = useCallback(async () => {
    try {
      const [listRes, statsRes, analyticsRes, quotaRes, personasRes] = await Promise.all([
        apiClient.get<{ workflows: WorkflowListItem[] }>("/api/workflows/list", { params: { limit: 10 } }),
        apiClient.get<ContentStats>("/api/content/stats"),
        apiClient.get<AnalyticsSummary>("/api/analytics/summary").catch(() => ({ data: { average_engagement_rate: null } })),
        apiClient.get<QuotaSummary>("/api/quota/summary", { params: { days: 0 } }).catch(() => ({ data: { total_cost_usd: 0, providers: [] } })),
        apiClient.get<{ personas: PersonaItem[] }>("/api/customer/personas").catch(() => ({ data: { personas: [] } })),
      ]);

      setStats(statsRes.data);
      setAnalytics(analyticsRes.data);
      setQuota(quotaRes.data);
      setPersonas(personasRes.data.personas || []);
      await fetchItems();

      const baseWorkflows = listRes.data.workflows || [];
      const detailedWorkflows = await Promise.all(
        baseWorkflows.map(async (item) => {
          try {
            const statusRes = await apiClient.get<{ status: WorkflowStatusPayload }>(`/api/workflows/status/${item.workflow_id}`);
            return { ...item, details: statusRes.data.status };
          } catch {
            return item;
          }
        })
      );
      setWorkflows(detailedWorkflows);
      setError(null);
    } catch (err) {
      console.error("Dashboard error:", err);
      setError("Failed to sync dashboard data");
    } finally {
      setIsLoading(false);
    }
  }, [fetchItems]);

  useEffect(() => {
    loadData();
    const poller = setInterval(loadData, WORKFLOW_POLL_INTERVAL);
    return () => clearInterval(poller);
  }, [loadData]);

  // --- Derived State ---

  const runningCount = useMemo(() => 
    workflows.filter(w => (w.details?.status || w.status) === "running" || (w.details?.status || w.status) === "waiting_approval").length,
    [workflows]
  );

  const engagementRate = useMemo(() => {
    const rate = analytics.average_engagement_rate;
    return typeof rate === "number" ? `${rate.toFixed(1)}%` : "0%";
  }, [analytics]);

  // --- Sub-components (Views) ---

  const SideNavBar = () => (
    <aside className="hidden lg:flex flex-col p-6 space-y-4 bg-[#deddd7] dark:bg-stone-950 h-[calc(100vh-5rem)] w-64 rounded-r-[3rem] sticky top-20 left-0 z-40 transition-transform">
      <div className="mb-8 px-4">
        <h2 className="text-xl font-black text-[#2e2f2c] dark:text-stone-100">Aura Factory</h2>
        <p className="text-xs font-label text-stone-500">The Human Touch</p>
      </div>
      <nav className="flex-1 space-y-2">
        {[
          { icon: LayoutDashboard, label: "Creator Hub", id: "dashboard" },
          { icon: Cpu, label: "Design Room", id: "ai-ops" },
          { icon: Database, label: "Story Lab", id: "memory" },
          { icon: Activity, label: "Community", id: "activity" }
        ].map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id as DashboardTab)}
            className={`flex items-center gap-3 w-full px-4 py-3 rounded-full transition-all active:scale-[0.98] ${
              activeTab === item.id 
                ? "bg-white dark:bg-stone-800 text-[#a03929] dark:text-[#fd7d68] shadow-sm" 
                : "text-stone-600 dark:text-stone-400 hover:text-[#a03929] hover:bg-white/40 dark:hover:bg-stone-800/40"
            }`}
          >
            <item.icon className="h-5 w-5" />
            <span className="font-body text-sm">{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="pt-6 border-t border-stone-300/30 space-y-2">
        <button className="flex items-center gap-3 w-full px-4 py-3 text-stone-600 dark:text-stone-400 hover:text-[#a03929] hover:bg-white/40 dark:hover:bg-stone-800/40 rounded-full transition-all">
          <LogOut className="h-4 w-4" />
          <span className="font-body text-sm">Logout</span>
        </button>
      </div>
    </aside>
  );

  const TopBar = () => (
    <header className="fixed top-0 w-full z-50 bg-[#f8f6f1]/70 dark:bg-stone-900/70 backdrop-blur-xl shadow-[0_20px_40px_rgba(46,47,44,0.06)] px-8 py-4">
      <div className="flex justify-between items-center w-full">
        <div className="flex items-center gap-8">
          <span className="text-2xl font-bold tracking-tight text-[#a03929] dark:text-[#fd7d68]">Aura Influencer</span>
          <div className="hidden md:flex items-center bg-[#f2f1eb] dark:bg-stone-800/50 rounded-full px-4 py-2 gap-2">
            <Search className="h-4 w-4 text-stone-500" />
            <input className="bg-transparent border-none focus:ring-0 text-sm font-label text-[#5c5c58] w-64" placeholder="Search systems..." type="text" />
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button className="p-2 hover:bg-[#deddd7]/50 dark:hover:bg-stone-800/50 rounded-full transition-all active:scale-95 duration-200">
            <Bell className="h-5 w-5 text-stone-500" />
          </button>
          <button className="p-2 hover:bg-[#deddd7]/50 dark:hover:bg-stone-800/50 rounded-full transition-all active:scale-95 duration-200">
            <Settings className="h-5 w-5 text-stone-500" />
          </button>
          <div className="w-10 h-10 rounded-full overflow-hidden bg-[#eae8e3]">
            <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuDRMKmmphbKNMy_EQQDxR4lXzPcou2fj2cwP2JC6vJrDdIFTYr2gG6DURMqVP2NXAv3XddURAFJqHglVTAKFNQQ4QoZFr5Z0Arn7BcMqAOZmMZ-94W15mkMvNhnO5Er0cxzKY9rz3rc5Iq1wLZmm8p2CqWbgVIhcTYsBkYxIZkQmyr-WeUgQjd91F5Qr1ZoRj3jcUBI06zPtTUGpfrkkKLfYcMufNSyZsk-k-FfmzmYfHsfb9tDawym2dCQ9RJmNtg7PgcSPYzo9xY" alt="Profile" className="w-full h-full object-cover" />
          </div>
        </div>
      </div>
    </header>
  );

  const SummaryView = () => (
    <div className="space-y-12">
      {/* Quick Stats Summary Row */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { label: "Active Campaigns", val: Math.max(runningCount, stats.active_campaigns), trend: "+2 today", color: "text-[#00684f]" },
          { label: "Total Inferences", val: "142.8k", trend: "99.9% success", color: "text-[#00684f]" },
          { label: "Avg. Latency", val: "240ms", trend: "+12ms peak", color: "text-[#b41340]" },
          { label: "Active Personas", val: personas.length, trend: "4 idle", color: "text-[#5c5c58]" }
        ].map((s, i) => (
          <div key={i} className="bg-white dark:bg-stone-800 p-6 rounded-xl shadow-[0_20px_40px_rgba(46,47,44,0.06)] flex flex-col justify-between border border-black/5 dark:border-white/5">
            <span className="text-[10px] uppercase tracking-widest text-[#5c5c58] dark:text-stone-400 font-label font-bold">{s.label}</span>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="text-3xl font-extrabold text-[#2e2f2c] dark:text-white">{s.val}</span>
              <span className={`${s.color} text-[10px] font-bold`}>{s.trend}</span>
            </div>
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        {/* Left Column: System Health & Backbone */}
        <div className="lg:col-span-4 space-y-10">
          <div className="bg-[#e4e2dd] dark:bg-stone-900/50 p-8 rounded-xl border border-black/5 dark:border-white/5">
            <div className="flex items-center justify-between mb-8">
              <h3 className="text-xl font-bold font-headline">System Health</h3>
              <span className="flex items-center gap-2 px-3 py-1 bg-[#98ffd9] text-[#004f3b] rounded-full text-[10px] font-black tracking-tight">
                <span className="w-2 h-2 rounded-full bg-[#00684f] animate-pulse"></span>
                OPERATIONAL
              </span>
            </div>
            <div className="space-y-6">
              {[
                { name: "Core API", latency: "12ms", icon: Database },
                { name: "Vector DB", latency: "45ms", icon: Layout },
                { name: "Edge Proxy", latency: "8ms", icon: Zap }
              ].map((s, i) => (
                <div key={i} className="flex justify-between items-center p-2 hover:bg-white/20 rounded-lg transition-colors">
                  <div className="flex items-center gap-3">
                    <s.icon className="h-4 w-4 text-[#a03929]" />
                    <span className="text-sm font-medium font-body">{s.name}</span>
                  </div>
                  <span className="text-[10px] font-mono bg-white dark:bg-stone-800 px-2 py-1 rounded shadow-sm">{s.latency}</span>
                </div>
              ))}
            </div>
            <div className="mt-10 p-4 bg-white/40 dark:bg-white/5 rounded-lg border border-black/5">
              <span className="text-[10px] uppercase font-bold text-[#777773] tracking-wider mb-3 block">Real-time Load</span>
              <div className="h-16 flex items-end gap-1 px-1">
                {[40, 60, 45, 85, 70, 55, 40, 60, 45, 85].map((h, i) => (
                  <div key={i} className={`w-full ${h > 80 ? 'bg-[#a03929]' : 'bg-[#fd7d68]'} rounded-t-sm transition-all duration-500`} style={{ height: `${h}%` }}></div>
                ))}
              </div>
            </div>
          </div>

          <div className="bg-[#deddd7] dark:bg-stone-900/40 p-8 rounded-xl border border-black/5 dark:border-white/5">
            <h3 className="text-xl font-bold font-headline mb-6">AI Backbone</h3>
            <div className="space-y-6">
              <div>
                <label className="text-[10px] uppercase font-bold text-[#5c5c58] block mb-2">Primary Model</label>
                <div className="flex items-center justify-between p-3 bg-white dark:bg-stone-800 rounded-full shadow-sm">
                  <span className="text-sm font-bold pl-2">GPT-4o (Snapshot 2024)</span>
                  <CheckCircle2 className="h-4 w-4 text-[#00684f] fill-[#00684f]" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] uppercase font-bold text-[#5c5c58] block mb-2">Access Mode</label>
                  <div className="p-3 bg-white dark:bg-stone-800 rounded-2xl text-center shadow-sm">
                    <span className="text-xs font-bold">Priority Plus</span>
                  </div>
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-[#5c5c58] block mb-2">Region</label>
                  <div className="p-3 bg-white dark:bg-stone-800 rounded-2xl text-center shadow-sm">
                    <span className="text-xs font-bold">US-East-1</span>
                  </div>
                </div>
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-[#5c5c58] block mb-2">Endpoint URL</label>
                <div className="flex items-center gap-2 text-[10px] font-mono text-[#5c5c58] truncate bg-white dark:bg-stone-800 p-3 rounded-lg border border-black/5">
                  <span>https://api.aura.factory/v2/inference/prod_ext_293...</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-8 space-y-10">
          <div className="bg-white dark:bg-stone-900 p-10 rounded-xl shadow-[0_20px_40px_rgba(46,47,44,0.06)] border border-black/5 dark:border-white/10">
            <div className="flex items-center justify-between mb-10">
              <div>
                <h2 className="text-3xl font-extrabold text-[#2e2f2c] dark:text-white leading-tight font-headline">Quota Snapshot</h2>
                <p className="text-[#5c5c58] dark:text-stone-400 text-sm mt-1 font-body">Provider-specific consumption metrics</p>
              </div>
              <button className="bg-[#fdd34d] text-[#463600] px-6 py-3 rounded-full font-bold text-sm transition-all hover:shadow-lg active:scale-95 shadow-sm">
                Upgrade Plan
              </button>
            </div>
            <div className="space-y-10">
              {quota.providers.map((p, i) => (
                <div key={i} className="space-y-3">
                  <div className="flex justify-between items-end">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-[#eae8e3] dark:bg-stone-800 flex items-center justify-center">
                        <Rocket className="h-5 w-5 text-[#a03929]" />
                      </div>
                      <div>
                        <p className="font-bold text-sm font-body">{p.label}</p>
                        <p className="text-[10px] text-[#5c5c58] dark:text-stone-400 uppercase font-black">{p.provider}</p>
                      </div>
                    </div>
                    <span className="text-xs font-bold font-label">
                      {p.remaining_limit ? Math.round((p.usage_value / p.remaining_limit) * 100) : 0}% consumed
                    </span>
                  </div>
                  <div className="h-3 bg-[#e4e2dd] dark:bg-stone-800 rounded-full overflow-hidden">
                    <div 
                      className={`h-full bg-gradient-to-r ${i % 2 === 0 ? 'from-[#a03929] to-[#fd7d68]' : 'from-[#00684f] to-[#89f0cb]'} rounded-full transition-all duration-1000`} 
                      style={{ width: `${p.remaining_limit ? Math.min(100, (p.usage_value / p.remaining_limit) * 100) : 0}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {personas.slice(0, 2).map((p, i) => (
              <div key={i} className="bg-white dark:bg-stone-900 rounded-xl p-6 shadow-sm border border-black/5 dark:border-white/5 flex flex-col gap-6 group hover:shadow-md transition-all">
                <div className="flex gap-4">
                  <div className="w-20 h-20 rounded-xl overflow-hidden shadow-inner flex-shrink-0 group-hover:scale-105 transition-transform duration-500">
                    <img 
                      src={p.avatar_image_url || "https://lh3.googleusercontent.com/y/AB6AXuCYDbbhZy5Mybz1zaQWR1DoXdYRfT8pp0BC2AReYNHoV_5FYMrQc4mkYYCaFjcVY8hwnBIWmffNbzkTZAwEjR7U41ODtojX7t2OWcr0zy8Czyxc4GnIu4igatj23VwZ24Xu-IgCPiz6mgxkgSrw6Wy9guyzLk8Ozx2sizUEFaUIPy665lhNATV4UJO10OLfhJ6k7DlrSk3MhFBc6KkZ5Unr_qkqi-LZ7-qdmVut6XZrRC2KK2J8rMJyrpHTm44QWvWRMSAcKCFWsYk"} 
                      alt={p.display_name} 
                      className="w-full h-full object-cover" 
                    />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-lg font-bold font-headline">{p.display_name}</h4>
                    <p className="text-sm text-[#5c5c58] mb-3 font-body">{p.role}</p>
                    <div className="flex gap-2">
                       <span className="text-[8px] px-2 py-0.5 bg-[#f2f1eb] dark:bg-stone-800 rounded-full font-black uppercase tracking-widest">{p.status}</span>
                       <span className="text-[8px] px-2 py-0.5 bg-[#f2f1eb] dark:bg-stone-800 rounded-full font-black uppercase tracking-widest">LIVE</span>
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 pt-4 border-t border-[#f2f1eb] dark:border-white/5">
                  <div className="text-center">
                    <p className="text-[8px] text-[#5c5c58] uppercase font-black tracking-widest">ER</p>
                    <p className="text-xs font-bold">4.2%</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[8px] text-[#5c5c58] uppercase font-black tracking-widest">POSTS</p>
                    <p className="text-xs font-bold">241</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[8px] text-[#5c5c58] uppercase font-black tracking-widest">MOOD</p>
                    <p className="text-xs font-bold text-[#00684f] uppercase">ZEN</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const MemoryView = () => (
    <div className="max-w-6xl mx-auto space-y-12">
      <div className="mb-12">
        <h2 className="text-4xl font-headline font-extrabold text-[#2e2f2c] mb-2 dark:text-white">Memory & Context</h2>
        <p className="text-[#5c5c58] dark:text-stone-400 max-w-2xl">Định nghĩa bản sắc thương hiệu kỹ thuật số. Aura sẽ học hỏi và duy trì phong cách nhất quán dựa trên các thiết lập tại đây.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        <div className="lg:col-span-8 space-y-8">
          <div className="bg-white dark:bg-stone-900 rounded-xl p-8 shadow-sm border border-black/5 dark:border-white/5">
            <div className="flex items-center gap-3 mb-8">
              <div className="w-12 h-12 rounded-2xl bg-[#a03929]/10 flex items-center justify-center text-[#a03929]">
                <Plus className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold font-headline dark:text-white">Bối cảnh Thương hiệu</h3>
            </div>
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-[#5c5c58] dark:text-stone-400 px-1">Tên nhãn hàng</label>
                  <input className="w-full bg-[#f2f1eb] dark:bg-stone-800 border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-[#a03929]/20 text-[#2e2f2c] dark:text-white font-medium" defaultValue="Aura Lifestyle" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-[#5c5c58] dark:text-stone-400 px-1">Nhóm khách hàng</label>
                  <input className="w-full bg-[#f2f1eb] dark:bg-stone-800 border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-[#a03929]/20 text-[#2e2f2c] dark:text-white font-medium" defaultValue="Premium Enthusiasts" />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-[#5c5c58] dark:text-stone-400 px-1">Định hướng phong cách</label>
                <textarea className="w-full bg-[#f2f1eb] dark:bg-stone-800 border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-[#a03929]/20 text-[#2e2f2c] dark:text-white font-medium min-h-[120px]" defaultValue="Sang trọng, tối giản, và luôn nhấn mạnh vào giá trị nguyên bản của con người trong kỷ nguyên AI." />
              </div>
              <div className="flex justify-end">
                <button className="px-10 py-3.5 bg-[#a03929] text-white font-bold rounded-full hover:opacity-90 transition-all shadow-lg shadow-[#a03929]/20">Lưu thay đổi</button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="bg-white dark:bg-stone-900 rounded-xl p-8 shadow-sm border border-black/5 dark:border-white/5 flex flex-col justify-between">
              <div>
                <h4 className="font-bold font-headline mb-2 dark:text-white">Chế độ Trí tuệ</h4>
                <p className="text-sm text-[#5c5c58] dark:text-stone-400 mb-6">Xác định cách AI truy xuất dữ liệu từ memory.</p>
              </div>
              <div className="space-y-3">
                <button className="w-full p-4 bg-white dark:bg-stone-800 border-2 border-[#a03929] rounded-2xl flex justify-between items-center">
                  <span className="font-bold text-[#2e2f2c] dark:text-white">Truy xuất chủ động</span>
                  <CheckCircle2 className="h-5 w-5 text-[#a03929]" />
                </button>
                <button className="w-full p-4 bg-[#f2f1eb] dark:bg-stone-800 border-2 border-transparent rounded-2xl text-left font-medium text-[#5c5c58] dark:text-stone-400">
                  Chỉ khi được yêu cầu
                </button>
              </div>
            </div>
            <div className="bg-white dark:bg-stone-900 rounded-xl p-8 shadow-sm border border-black/5 dark:border-white/5 flex flex-col justify-between">
              <div>
                <h4 className="font-bold font-headline mb-2 dark:text-white">Hệ thống cầu nối</h4>
                <p className="text-sm text-[#5c5c58] dark:text-stone-400 mb-6">Kết nối trực tiếp qua các giao thức bảo mật.</p>
              </div>
              <div className="p-4 bg-[#f2f1eb] dark:bg-stone-800 rounded-2xl flex items-center gap-4">
                <div className="w-10 h-10 bg-[#0088cc] text-white rounded-full flex items-center justify-center">
                  <Zap className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <p className="text-xs font-bold text-[#2e2f2c] dark:text-white">Telegram Connected</p>
                  <p className="text-[10px] text-[#00684f] font-black">ACTIVE</p>
                </div>
                <RefreshCw className="h-4 w-4 text-[#5c5c58] dark:text-stone-400 cursor-pointer" />
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-4 space-y-8">
          <div className="bg-[#e4e2dd] dark:bg-stone-900 rounded-xl p-8">
            <h4 className="text-lg font-bold font-headline mb-6 dark:text-white">Social Grid</h4>
            <div className="grid grid-cols-2 gap-4">
              {["LinkedIn", "Twitter X", "YouTube", "Instagram"].map((s, i) => (
                <div key={i} className="bg-white/60 dark:bg-white/5 p-4 rounded-[1.5rem] flex flex-col items-center gap-3 hover:bg-white dark:hover:bg-white/10 transition-all shadow-sm">
                  <div className="w-10 h-10 bg-black/5 dark:bg-white/5 rounded-full flex items-center justify-center">
                    <Rocket className="h-4 w-4 text-[#a03929]" />
                  </div>
                  <span className="text-[10px] font-bold dark:text-stone-300">{s}</span>
                </div>
              ))}
            </div>
            <div className="mt-10 pt-8 border-t border-black/5 dark:border-white/5">
              <div className="flex justify-between text-xs font-bold mb-2 dark:text-stone-300">
                <span>Lưu giữ bộ nhớ</span>
                <span className="text-[#a03929]">84%</span>
              </div>
              <div className="w-full h-1.5 bg-white dark:bg-stone-800 rounded-full overflow-hidden">
                <div className="h-full bg-[#a03929]" style={{ width: '84%' }} />
              </div>
            </div>
          </div>

          <div className="rounded-xl overflow-hidden shadow-xl aspect-[4/5] relative group">
            <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuAoSdywEmOK1nmK1QbNITG2jFKWka9AEj13aTiXUhFRS75uOKDEs3K4-_qZrBuuRYzcaRm_X7xS3zi_P8bs-r89JL-0F-TbQ3Nnydk_MN8g7d28vO8zsyTg45Y9KjGkcJ2vc52-F0LIgtiv0rEEwQnWXWTYvzfJmuexJ4ZrFwFun9r6EuBH6nUel7_yzeeyXvwRnurddcruLIELBLiROhzM0vcR4mT1EdSjkeWNvKdXlZ2B8cyB29aLSNH1fA-PhgFDLQcnFnytTfY" className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" alt="Memory" />
            <div className="absolute inset-x-0 bottom-0 p-6 bg-black/60 backdrop-blur-md">
              <h5 className="text-white font-bold leading-none">Persona Online</h5>
              <div className="flex items-center gap-2 mt-2">
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <span className="text-[10px] text-white/80 font-bold uppercase tracking-widest">Synced</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const ActivityView = () => (
    <div className="space-y-10 h-full">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <span className="text-[#a03929] font-semibold tracking-widest uppercase text-xs font-label">Ops Center</span>
          <h2 className="text-4xl font-headline font-extrabold text-[#2e2f2c] dark:text-white mt-1">Activity & Workflows</h2>
        </div>
        <div className="flex gap-4">
          <button onClick={loadData} className="px-6 py-3 bg-[#fdd34d] text-[#463600] rounded-full font-bold flex items-center gap-2 shadow-sm active:scale-95 transition-all">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
          <button className="px-6 py-3 bg-[#a03929] text-white rounded-full font-bold flex items-center gap-2 shadow-lg shadow-[#a03929]/20 active:scale-95 transition-all">
            <Zap className="h-4 w-4 fill-current" />
            Optimize
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-10 items-stretch h-full">
        <div className="xl:col-span-8 flex flex-col gap-8">
          <div className="bg-white dark:bg-stone-900 rounded-xl p-8 shadow-sm border border-black/5 dark:border-white/5">
            <div className="flex items-center justify-between mb-8">
              <h3 className="text-xl font-bold font-headline flex items-center gap-2 dark:text-white">
                <Activity className="h-5 w-5 text-[#a03929]" />
                Active Pipelines
              </h3>
              <span className="text-[#5c5c58] dark:text-stone-400 text-sm font-bold uppercase tracking-widest">Live: {runningCount}</span>
            </div>
            <div className="space-y-6">
              {workflows.length > 0 ? workflows.map((w, i) => (
                <div key={i} className="bg-[#f2f1eb]/50 dark:bg-stone-800/50 hover:bg-[#f2f1eb] dark:hover:bg-stone-800 p-6 rounded-xl transition-all duration-300">
                  <div className="flex gap-6 items-center">
                    <div className="w-16 h-16 rounded-2xl overflow-hidden bg-[#deddd7] dark:bg-stone-700 shrink-0 border border-black/5 shadow-sm">
                      <img 
                        src="https://lh3.googleusercontent.com/y/AB6AXuDy3BIg8IKDtbIqBwX5EqzRts6Mm8hSbtzgXbeqd4kKubS2RR23u4tUFdZSfU9bLzK3Pgw6umDiE3xi74Iaf5JTmrs47zfWAXVWvrEaokUOxmSZ0Z5WbIGxONVWhvcQzoenoIk7Bju1Xn_WzmkoKfRg-Iv6hM6IbK2SbrQQtzf9VTNOvtri45yeTpIgt2vzZi4fYeiisoQQ7Ajx2J6fOH78mKMUydR_xnCIlSN815h-J6OdcSUTr4TpZw4AF_bC2eWzR0aqoBF5qVc" 
                        className="w-full h-full object-cover" 
                        alt="Workflow" 
                      />
                    </div>
                    <div className="flex-1">
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-bold text-[#2e2f2c] dark:text-white">{w.title || "Generic Workflow"}</h4>
                        <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider ${
                          (w.details?.status || w.status) === "running" ? "bg-[#a03929]/10 text-[#a03929]" : "bg-[#5c5c58]/10 text-[#5c5c58] dark:text-stone-400"
                        }`}>
                          {w.details?.status || w.status}
                        </span>
                      </div>
                      <p className="text-xs text-[#5c5c58] dark:text-stone-400 mb-4 font-body">Step: {w.details?.current_step || "Initializing"}</p>
                      <div className="h-1.5 w-full bg-[#deddd7] dark:bg-stone-700 rounded-full overflow-hidden">
                        <div className={`h-full transition-all duration-500 ${(w.details?.status || w.status) === "running" ? "bg-[#a03929]" : "bg-[#5c5c58]"}`} style={{ width: (w.details?.status || w.status) === "running" ? '65%' : '0%' }} />
                      </div>
                    </div>
                    <div className="flex gap-2">
                       <button className="p-3 bg-white dark:bg-stone-700 rounded-full shadow-sm hover:text-[#a03929] transition-all dark:text-stone-300"><Pause className="h-4 w-4" /></button>
                       <button className="p-3 bg-white dark:bg-stone-700 rounded-full shadow-sm hover:text-[#b41340] transition-all dark:text-stone-300"><X className="h-4 w-4" /></button>
                    </div>
                  </div>
                </div>
              )) : (
                <div className="text-center py-20 bg-[#f2f1eb]/30 dark:bg-stone-800/30 rounded-xl border-2 border-dashed border-[#deddd7] dark:border-stone-700">
                  <Activity className="h-12 w-12 text-[#deddd7] dark:text-stone-700 mx-auto mb-4" />
                  <p className="text-[#5c5c58] dark:text-stone-500 font-bold">No pipelines currently active.</p>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="xl:col-span-4 overflow-hidden">
          <div className="bg-[#deddd7] dark:bg-stone-900/60 p-8 rounded-xl h-full flex flex-col border border-black/5 dark:border-white/5 shadow-sm">
            <h3 className="text-xl font-bold font-headline mb-8 text-[#2e2f2c] dark:text-white">Activity Feed</h3>
            <div className="space-y-6 overflow-y-auto pr-2 custom-scrollbar flex-1">
              {[
                { time: "Vừa xong", label: "Media Generated", desc: "3 hình ảnh chất lượng cao cho Chiến dịch A đã sẵn sàng.", variant: "info" as const },
                { time: "15 phút trước", label: "Persona Synced", desc: "Tiến trình training cho Aura_05 đã hoàn tất.", variant: "success" as const },
                { time: "1 giờ trước", label: "Post Published", desc: "Bài đăng 'Modern Living' trên Instagram đã live.", variant: "warning" as const }
              ].map((ev, i) => (
                <TimelineItem
                  key={i}
                  id={`activity-${i}`}
                  title={ev.label}
                  description={ev.desc}
                  timestamp={ev.time}
                  variant={ev.variant}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-[#f8f6f1] dark:bg-black text-[#2e2f2c] dark:text-stone-200 font-body transition-colors">
      <SideNavBar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="mt-20 p-8 lg:p-12 overflow-y-auto flex-1 custom-scrollbar">
          {activeTab === "dashboard" && <SummaryView />}
          {activeTab === "ai-ops" && <SummaryView />} {/* Reusing SummaryView as base for AI Ops per snippet structure */}
          {activeTab === "memory" && <MemoryView />}
          {activeTab === "activity" && <ActivityView />}
        </main>
        
        {/* Unified Footer */}
        <footer className="w-full py-8 border-t border-black/5 dark:border-white/5 bg-[#f8f6f1] dark:bg-black flex flex-col md:flex-row justify-between items-center px-12 gap-6">
          <div className="text-[#5c5c58] dark:text-stone-500 font-label text-[10px] uppercase font-bold tracking-[0.2em]">
            © 2024 Aura Influencer Factory. All rights reserved.
          </div>
          <div className="flex gap-8">
            {["Privacy", "Terms", "API Docs"].map((l, i) => (
              <a key={i} className="text-[#5c5c58] dark:text-stone-500 hover:text-[#a03929] transition-colors font-label text-[10px] uppercase font-bold tracking-widest" href="#">{l}</a>
            ))}
          </div>
        </footer>
      </div>
    </div>
  );
}
