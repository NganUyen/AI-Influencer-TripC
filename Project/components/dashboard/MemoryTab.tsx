"use client";

import React from "react";
import {
  Plus, Database, Share2,
  Settings, Save, Key,
  MessageSquare, ExternalLink,
  Twitter, Facebook, Linkedin,
  Instagram, AlertCircle,
  Activity, Gauge, BarChart3, AlertTriangle, Server,
} from "lucide-react";

import { PanelHeader } from "@/components/ui/PanelHeader";
import { FieldSet } from "@/components/ui/FieldSet";
import { FormField } from "@/components/ui/FormField";
import { SelectField } from "@/components/ui/SelectField";
import { TextAreaField } from "@/components/ui/TextAreaField";
import { DataCard } from "@/components/ui/DataCard";


interface MemoryTabProps {
  brandForm: any;
  accounts: any[];
  aiBackboneForm: any;
  busyKey: string | null;
  handleBrandSave: (e: React.FormEvent<HTMLFormElement>) => void;
  handleConnect: (platform: string) => void;
  handleDisconnect: (accountId: string) => void;
  setBrandForm: React.Dispatch<React.SetStateAction<any>>;
  setAiBackboneForm: React.Dispatch<React.SetStateAction<any>>;
  handleAiBackboneSave: (e: React.FormEvent<HTMLFormElement>) => void;
  handleLinkChatgptOAuth: (e: React.FormEvent<HTMLFormElement>) => void;
  handleDisconnectChatgptOAuth: () => void;
  aiBackbone: any;
  user: any;
  systemSummary: any;
}


const SUPPORTED_PLATFORMS = ["linkedin", "facebook", "twitter", "instagram", "tiktok"];

const AI_BACKBONE_OPTIONS = [
  { value: "platform_managed", title: "Shared Backbone" },
  { value: "customer_api_key", title: "Customer API Key" },
  { value: "chatgpt_oauth", title: "GPT OAuth" },
];

function parseLatencyToMs(value?: string | null) {
  if (!value) return null;

  const normalized = value.trim().toLowerCase();
  const match = normalized.match(/^([\d.]+)\s*(ms|s)$/);

  if (!match) return null;

  const amount = Number(match[1]);
  if (!Number.isFinite(amount)) return null;

  return match[2] === "s" ? amount * 1000 : amount;
}

function formatLatency(ms: number | null) {
  if (ms === null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)}s`;
  return `${Math.round(ms)}ms`;
}

function getQuotaUsagePercent(used: number, total: number) {
  if (!Number.isFinite(used) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.min(100, Math.max(0, (used / total) * 100));
}

function formatMetricNumber(value?: number | null, maximumFractionDigits = 0) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return value.toLocaleString(undefined, { maximumFractionDigits });
}

function formatTimestamp(value?: string | null) {
  if (!value) return "-";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return value;
  return new Date(parsed).toLocaleString();
}

function humanizeKey(value?: string | null) {
  if (!value) return "-";
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function MemoryTab({
  brandForm,
  accounts,
  aiBackboneForm,
  busyKey,
  handleBrandSave,
  handleConnect,
  handleDisconnect,
  setBrandForm,
  setAiBackboneForm,
  handleAiBackboneSave,
  handleLinkChatgptOAuth,
  handleDisconnectChatgptOAuth,
  aiBackbone,
  systemSummary,
}: MemoryTabProps) {
  const services = systemSummary?.services || [];
  const quotas = systemSummary?.quota || [];
  const summary = systemSummary?.summary || null;
  const systemSummaryEndpoint = "/api/customer/system/summary";
  const telemetryScope = summary?.telemetry_scope || "user";
  const workspaceFallbackUsed = Boolean(summary?.workspace_fallback_used);
  const telemetryFallbackService = services.find((service: any) => service?.key === "system_status");
  const telemetryFallbackError = telemetryFallbackService?.last_error || systemSummary?.detail || null;

  const servicesWithLatency = services
    .map((service: any) => ({
      ...service,
      latencyMs:
        typeof service.latency_ms === "number"
          ? service.latency_ms
          : parseLatencyToMs(service.latency),
    }))
    .sort((a: any, b: any) => (b.latencyMs || 0) - (a.latencyMs || 0));

  const quotasWithUsage = quotas
    .map((quota: any) => ({
      ...quota,
      usagePercent:
        typeof quota.usage_percent === "number"
          ? quota.usage_percent
          : getQuotaUsagePercent(quota.used, quota.total),
    }))
    .sort((a: any, b: any) => b.usagePercent - a.usagePercent);

  const onlineServices = services.filter((service: any) => service.status === "online").length;
  const degradedServices = services.filter(
    (service: any) => service.status === "warning" || service.status === "error",
  ).length;
  const erroredServices = services.filter((service: any) => service.status === "error").length;

  const latencySamples = servicesWithLatency
    .map((service: any) => service.latencyMs)
    .filter((value: number | null): value is number => value !== null);
  const averageLatencyMs =
    typeof summary?.average_latency_ms === "number"
      ? summary.average_latency_ms
      : latencySamples.length
        ? latencySamples.reduce((sum: number, value: number) => sum + value, 0) / latencySamples.length
        : null;
  const peakLatencyService = servicesWithLatency.find((service: any) => service.latencyMs !== null) || null;

  const averageQuotaUsage =
    typeof summary?.average_quota_usage_percent === "number"
      ? summary.average_quota_usage_percent
      : quotasWithUsage.length
        ? quotasWithUsage.reduce((sum: number, quota: any) => sum + quota.usagePercent, 0) / quotasWithUsage.length
        : null;
  const hotQuotaCount =
    typeof summary?.warning_quotas === "number"
      ? summary.warning_quotas
      : quotasWithUsage.filter((quota: any) => quota.usagePercent >= 75).length;
  const criticalQuotaCount =
    typeof summary?.critical_quotas === "number"
      ? summary.critical_quotas
      : quotasWithUsage.filter((quota: any) => quota.usagePercent >= 90).length;
  const activeAlertCount =
    typeof summary?.alert_count === "number"
      ? summary.alert_count
      : degradedServices + hotQuotaCount;

  const projectHealth = erroredServices > 0 || criticalQuotaCount > 0
    ? {
        label: "Critical",
        tone: "text-rose-700 bg-rose-50 border-rose-100",
        accent: "bg-rose-500",
        description: "Immediate attention recommended",
      }
    : degradedServices > 0 || hotQuotaCount > 0
      ? {
          label: "Degraded",
          tone: "text-amber-700 bg-amber-50 border-amber-100",
          accent: "bg-amber-500",
          description: "Some resources are under pressure",
        }
      : services.length > 0 || quotas.length > 0
        ? {
            label: "Healthy",
            tone: "text-emerald-700 bg-emerald-50 border-emerald-100",
            accent: "bg-emerald-500",
            description: "Runtime is operating normally",
          }
        : {
            label: "Waiting",
            tone: "text-aura-on-surface-variant bg-aura-surface-container border-aura-outline/10",
            accent: "bg-aura-outline/30",
            description: "Telemetry appears when the workspace syncs",
          };

  return (

    <div className="space-y-10 animate-fade-in pb-20">
      {/* Page header */}
      <header>
        <h1 className="text-4xl font-extrabold text-aura-on-surface font-headline tracking-tight mb-2">Agent &amp; Instruction</h1>
        <p className="text-aura-on-surface-variant max-w-2xl text-sm font-body">
          Define the core behavior and operational constraints for your AI agent. These settings act as the global system prompt for your workspace.
        </p>
      </header>

      <section className="dashboard-panel overflow-hidden">
        <PanelHeader
          title="Project Runtime Overview"
          subtitle="High-level quota pressure and service latency across your workspace"
          className="border-b border-aura-outline/5 bg-aura-surface-container-low/30 px-8 py-6"
        />

        <div className="p-8 space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="dashboard-card p-5 bg-white">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-aura-on-surface-variant">Project Health</p>
                  <div className={`mt-3 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold ${projectHealth.tone}`}>
                    <span className={`w-2 h-2 rounded-full ${projectHealth.accent}`} />
                    {projectHealth.label}
                  </div>
                  <p className="mt-3 text-[11px] text-aura-on-surface-variant">{projectHealth.description}</p>
                </div>
                <div className="w-12 h-12 rounded-2xl bg-aura-primary/10 flex items-center justify-center text-aura-primary">
                  <Activity className="w-5 h-5" />
                </div>
              </div>
            </div>

            <div className="dashboard-card p-5 bg-white">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-aura-on-surface-variant">Average Latency</p>
                  <p className="mt-3 text-3xl font-black text-aura-on-surface font-headline">{formatLatency(averageLatencyMs)}</p>
                  <p className="mt-2 text-[11px] text-aura-on-surface-variant">
                    {summary?.peak_latency_service || peakLatencyService
                      ? `Peak: ${summary?.peak_latency_service || peakLatencyService?.name} at ${formatLatency(
                          typeof summary?.peak_latency_ms === "number"
                            ? summary.peak_latency_ms
                            : peakLatencyService?.latencyMs ?? null,
                        )}`
                      : "Latency will appear once services report in"}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-2xl bg-aura-secondary/10 flex items-center justify-center text-aura-secondary">
                  <Gauge className="w-5 h-5" />
                </div>
              </div>
            </div>

            <div className="dashboard-card p-5 bg-white">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-aura-on-surface-variant">Quota Pressure</p>
                  <p className="mt-3 text-3xl font-black text-aura-on-surface font-headline">
                    {averageQuotaUsage === null ? "—" : `${Math.round(averageQuotaUsage)}%`}
                  </p>
                  <p className="mt-2 text-[11px] text-aura-on-surface-variant">
                    {summary?.hottest_quota_name || quotasWithUsage[0]
                      ? `Highest: ${summary?.hottest_quota_name || quotasWithUsage[0]?.name} at ${Math.round(
                          summary?.hottest_quota_usage_percent ?? quotasWithUsage[0]?.usagePercent ?? 0,
                        )}%`
                      : "Quota telemetry will appear once providers sync"}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-2xl bg-aura-tertiary/10 flex items-center justify-center text-aura-tertiary">
                  <BarChart3 className="w-5 h-5" />
                </div>
              </div>
            </div>

            <div className="dashboard-card p-5 bg-white">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-aura-on-surface-variant">Active Alerts</p>
                  <p className="mt-3 text-3xl font-black text-aura-on-surface font-headline">{activeAlertCount}</p>
                  <p className="mt-2 text-[11px] text-aura-on-surface-variant">
                    {degradedServices} service issues • {hotQuotaCount} quota warnings
                  </p>
                </div>
                <div className="w-12 h-12 rounded-2xl bg-amber-500/10 flex items-center justify-center text-amber-600">
                  <AlertTriangle className="w-5 h-5" />
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-[11px] text-aura-on-surface-variant">
            <span className="rounded-full bg-aura-surface-container px-3 py-1.5 font-medium">
              Last sync: {formatTimestamp(summary?.refreshed_at)}
            </span>
            <span className="rounded-full bg-aura-surface-container px-3 py-1.5 font-medium">
              Snapshots: {formatMetricNumber(summary?.total_snapshots)}
            </span>
            <span className="rounded-full bg-aura-surface-container px-3 py-1.5 font-medium">
              Tracked cost: ${formatMetricNumber(summary?.total_cost_usd, 2)}
            </span>
            <span className="rounded-full bg-aura-surface-container px-3 py-1.5 font-medium">
              Scope: {humanizeKey(telemetryScope)}
            </span>
            <a
              href={systemSummaryEndpoint}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-full bg-aura-surface-container px-3 py-1.5 font-medium text-aura-on-surface hover:text-aura-primary transition-colors"
            >
              API: <span className="font-mono text-[10px]">{systemSummaryEndpoint}</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          {telemetryFallbackError && (
            <div className="rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 shrink-0" />
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-widest text-rose-700">
                    Telemetry Fallback Active
                  </p>
                  <p className="mt-1 text-sm text-rose-700">
                    The backend summary endpoint returned a fallback payload, so some quota and latency details may be incomplete.
                  </p>
                  <p className="mt-2 text-[11px] font-mono text-rose-700/90">
                    {telemetryFallbackError}
                  </p>
                </div>
              </div>
            </div>
          )}

          {!telemetryFallbackError && workspaceFallbackUsed && (
            <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-widest text-amber-700">
                    Workspace Telemetry Fallback
                  </p>
                  <p className="mt-1 text-sm text-amber-700">
                    This user does not have enough runtime snapshots yet, so some quota and latency cards are using workspace-level telemetry until more user-specific activity is recorded.
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="dashboard-card p-6 bg-white space-y-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant">Latency Radar</p>
                  <p className="mt-1 text-sm text-aura-on-surface">Current service responsiveness across the project</p>
                </div>
                <div className="w-10 h-10 rounded-2xl bg-aura-primary/10 flex items-center justify-center text-aura-primary">
                  <Server className="w-4 h-4" />
                </div>
              </div>

              <div className="space-y-3">
                {servicesWithLatency.length > 0 ? (
                  servicesWithLatency.slice(0, 4).map((service: any) => (
                    <div key={service.name} className="rounded-2xl border border-aura-outline/5 bg-aura-surface-container-low p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3 min-w-0">
                          <span
                            className={`w-2.5 h-2.5 rounded-full ${
                              service.status === "online"
                                ? "bg-emerald-500"
                                : service.status === "warning"
                                  ? "bg-amber-500"
                                  : "bg-rose-500"
                            }`}
                          />
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-aura-on-surface truncate">{service.name}</p>
                            <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant">
                              {service.status}
                              {service.status_reason ? ` | ${humanizeKey(service.status_reason)}` : ""}
                            </p>
                          </div>
                        </div>
                        <span className="text-xs font-mono font-semibold text-aura-on-surface">
                          {service.latency || formatLatency(service.latencyMs)}
                        </span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-aura-on-surface-variant border border-aura-outline/5">
                          {humanizeKey(service.latency_band)}
                        </span>
                        <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-aura-on-surface-variant border border-aura-outline/5">
                          Source: {humanizeKey(service.source)}
                        </span>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-[10px] text-aura-on-surface-variant">
                        <span>Latency</span>
                        <span className="text-right font-semibold text-aura-on-surface">
                          {formatLatency(service.latencyMs ?? parseLatencyToMs(service.latency))}
                        </span>
                        <span>Checked</span>
                        <span className="text-right font-semibold text-aura-on-surface">
                          {formatTimestamp(service.checked_at)}
                        </span>
                        <span>Configured</span>
                        <span className="text-right font-semibold text-aura-on-surface">
                          {service.configured ? "Yes" : "No"}
                        </span>
                      </div>
                      {service.detail && (
                        <p className="mt-3 text-[11px] leading-relaxed text-aura-on-surface-variant">
                          {service.detail}
                        </p>
                      )}
                      {service.last_error && (
                        <p className="mt-2 text-[11px] font-medium text-rose-600">
                          Last error: {service.last_error}
                        </p>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-aura-outline/15 bg-aura-surface-container-low px-4 py-6 text-center">
                    <p className="text-sm font-semibold text-aura-on-surface">No latency samples yet</p>
                    <p className="mt-1 text-[11px] text-aura-on-surface-variant">Service telemetry will appear here after the workspace healthcheck syncs.</p>
                  </div>
                )}
              </div>
            </div>

            <div className="dashboard-card p-6 bg-white space-y-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant">Quota Pressure</p>
                  <p className="mt-1 text-sm text-aura-on-surface">Combined resource load for the current project</p>
                </div>
                <div className="w-10 h-10 rounded-2xl bg-aura-secondary/10 flex items-center justify-center text-aura-secondary">
                  <BarChart3 className="w-4 h-4" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-2xl bg-aura-surface-container-low p-4 border border-aura-outline/5">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-aura-on-surface-variant">Tracked Providers</p>
                  <p className="mt-2 text-2xl font-black text-aura-on-surface font-headline">
                    {summary?.provider_count ?? quotasWithUsage.length}
                  </p>
                </div>
                <div className="rounded-2xl bg-aura-surface-container-low p-4 border border-aura-outline/5">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-aura-on-surface-variant">Services Online</p>
                  <p className="mt-2 text-2xl font-black text-aura-on-surface font-headline">
                    {typeof summary?.online_services === "number" && typeof summary?.total_services === "number"
                      ? `${summary.online_services}/${summary.total_services}`
                      : services.length > 0
                        ? `${onlineServices}/${services.length}`
                        : "-"}
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                {quotasWithUsage.length > 0 ? (
                  quotasWithUsage.slice(0, 4).map((quota: any) => (
                    <div key={quota.name} className="rounded-2xl border border-aura-outline/5 bg-aura-surface-container-low p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-aura-on-surface truncate">{quota.name}</p>
                          <p className="text-[10px] text-aura-on-surface-variant">
                            {formatMetricNumber(quota.used)} / {formatMetricNumber(quota.total)} {quota.unit}
                          </p>
                        </div>
                        <span
                          className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
                            quota.usagePercent >= 90
                              ? "bg-rose-100 text-rose-700"
                              : quota.usagePercent >= 75
                                ? "bg-amber-100 text-amber-700"
                                : "bg-aura-primary/10 text-aura-primary"
                          }`}
                        >
                          {Math.round(quota.usagePercent)}%
                        </span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {quota.provider && (
                          <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-aura-on-surface-variant border border-aura-outline/5">
                            {humanizeKey(quota.provider)}
                          </span>
                        )}
                        {quota.billing_type && (
                          <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-aura-on-surface-variant border border-aura-outline/5">
                            Billing: {humanizeKey(quota.billing_type)}
                          </span>
                        )}
                        {quota.remaining_source && (
                          <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-aura-on-surface-variant border border-aura-outline/5">
                            Source: {humanizeKey(quota.remaining_source)}
                          </span>
                        )}
                      </div>
                      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-aura-surface-container">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            quota.usagePercent >= 90
                              ? "bg-rose-500"
                              : quota.usagePercent >= 75
                                ? "bg-amber-500"
                                : "bg-aura-primary"
                          }`}
                          style={{ width: `${quota.usagePercent}%` }}
                        />
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[10px] text-aura-on-surface-variant">
                        <span>Remaining</span>
                        <span className="text-right font-semibold text-aura-on-surface">
                          {quota.remaining === null || quota.remaining === undefined
                            ? "-"
                            : `${formatMetricNumber(quota.remaining)} ${quota.remaining_unit || quota.unit || ""}`.trim()}
                        </span>
                        <span>Requests</span>
                        <span className="text-right font-semibold text-aura-on-surface">
                          {quota.requests_remaining === null || quota.requests_remaining === undefined
                            ? "-"
                            : `${formatMetricNumber(quota.requests_remaining)}${
                                quota.requests_limit ? ` / ${formatMetricNumber(quota.requests_limit)}` : ""
                              }`}
                        </span>
                        <span>Reset</span>
                        <span className="text-right font-semibold text-aura-on-surface">
                          {formatTimestamp(quota.reset_at || quota.requests_reset_at)}
                        </span>
                        <span>Cost / Snapshots</span>
                        <span className="text-right font-semibold text-aura-on-surface">
                          ${formatMetricNumber(quota.cost_usd, 2)} / {formatMetricNumber(quota.snapshot_count)}
                        </span>
                      </div>
                      {quota.remaining_message && (
                        <p className="mt-3 text-[11px] leading-relaxed text-aura-on-surface-variant">
                          {quota.remaining_message}
                        </p>
                      )}
                      {quota.last_error && (
                        <p className="mt-2 rounded-xl bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
                          Last error: {quota.last_error}
                        </p>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-aura-outline/15 bg-aura-surface-container-low px-4 py-6 text-center">
                    <p className="text-sm font-semibold text-aura-on-surface">No quota data yet</p>
                    <p className="mt-1 text-[11px] text-aura-on-surface-variant">Provider usage will appear here once your workspace starts consuming resources.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>


      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        {/* Main Content Area (Left/Wide) */}
        <div className="lg:col-span-8 space-y-10">
          {/* Brand Identity Panel */}
          <div className="dashboard-panel overflow-hidden">
            <PanelHeader
              title="Agent Behavior Definition"
              subtitle="Core personality and knowledge base for the AI Agent"
              className="border-b border-aura-outline/5 bg-aura-surface-container-low/30 px-8 py-6"
            />

            
            <form onSubmit={handleBrandSave} className="p-8 space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <FieldSet title="Product Name" description="Brand or product name" className="bg-transparent border-none p-0">
                  <FormField
                    value={brandForm.product_name || ""}
                    onChange={(val) => setBrandForm((c: any) => ({ ...c, product_name: val }))}
                    placeholder="e.g. AI-Influencer Factory"
                  />
                </FieldSet>
                <FieldSet title="Website URL" description="Official website URL" className="bg-transparent border-none p-0">
                  <FormField
                    value={brandForm.website_url || ""}
                    onChange={(val) => setBrandForm((c: any) => ({ ...c, website_url: val }))}
                    placeholder="https://ai-influencer.com"
                  />
                </FieldSet>
              </div>

              <FieldSet title="Target Audience" description="Describe your target customers" className="bg-transparent border-none p-0">
                <TextAreaField
                  value={brandForm.audience || ""}
                  onChange={(val) => setBrandForm((c: any) => ({ ...c, audience: val }))}
                  placeholder="e.g. Content creators who want to automate their channels."
                  rows={3}
                />
              </FieldSet>

              <FieldSet title="Offer Summary" description="What problem does your product solve?" className="bg-transparent border-none p-0">
                <TextAreaField
                  value={brandForm.offer_summary || ""}
                  onChange={(val) => setBrandForm((c: any) => ({ ...c, offer_summary: val }))}
                  placeholder="e.g. Provide an AI-powered workflow for creating and operating virtual influencers."
                  rows={3}
                />
              </FieldSet>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <FieldSet title="Tone of Voice" description="How the AI should communicate" className="bg-transparent border-none p-0">
                  <SelectField
                    value={brandForm.tone_voice || "professional"}
                    onChange={(val) => setBrandForm((c: any) => ({ ...c, tone_voice: val }))}
                    options={[
                      { value: "professional", label: "Professional" },
                      { value: "friendly", label: "Friendly" },
                      { value: "witty", label: "Witty & Bold" },
                      { value: "luxury", label: "Luxury & Sophisticated" },
                    ]}
                  />
                </FieldSet>
                <FieldSet title="Timezone" description="Primary operating timezone" className="bg-transparent border-none p-0">
                  <SelectField
                    value={brandForm.timezone || "UTC"}
                    onChange={(val) => setBrandForm((c: any) => ({ ...c, timezone: val }))}
                    options={[
                      { value: "UTC+7", label: "Hanoi (UTC+7)" },
                      { value: "UTC", label: "Universal (UTC)" },
                      { value: "UTC-5", label: "New York (UTC-5)" },
                    ]}
                  />
                </FieldSet>
              </div>

              <div className="pt-6 border-t border-aura-outline/5 flex justify-end">
                <button
                  type="submit"
                  disabled={busyKey === "brand"}
                  className="btn-primary flex items-center gap-2 disabled:opacity-45"
                >
                  {busyKey === "brand" ? "Saving..." : (
                    <>
                      <Save className="w-4 h-4" />
                      Save Brand Identity
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Connect Accounts Card */}
          <div className="dashboard-panel overflow-hidden">
            <PanelHeader 
              title="Connected Accounts" 
              subtitle="Social accounts the AI will operate directly"
              className="border-b border-aura-outline/5 px-8 py-6"
            />
            <div className="p-8">
              <DataCard tone="neutral" className="border-none p-0 bg-transparent cursor-default">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {SUPPORTED_PLATFORMS.map((platform) => {
                    const account = accounts.find((a) => a.platform === platform);
                    const isConnected = account && account.connection_status === "connected";
                    const isBusy = busyKey === `connect-${platform}` || (account && busyKey === `disconnect-${account.id}`);

                    return (
                      <div 
                        key={platform} 
                        className={`dashboard-card flex items-center justify-between p-4 transition-all group ${isConnected ? 'border-aura-primary/20 bg-aura-primary-container/10' : 'bg-white'}`}
                      >
                        <div className="flex items-center gap-4">
                          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${isConnected ? 'bg-aura-primary text-white shadow-lg shadow-aura-primary/20' : 'bg-aura-surface-container text-aura-on-surface-variant'}`}>
                              {platform === 'linkedin' && <Linkedin className="w-6 h-6" />}
                              {platform === 'twitter' && <Twitter className="w-6 h-6" />}
                              {platform === 'facebook' && <Facebook className="w-6 h-6" />}
                              {platform === 'instagram' && <Instagram className="w-6 h-6" />}
                              {!['linkedin','twitter','facebook','instagram'].includes(platform) && <Share2 className="w-6 h-6" />}
                          </div>
                          <div>
                              <p className="text-xs font-bold capitalize text-aura-on-surface">{platform}</p>
                              <p className="text-[10px] text-aura-on-surface-variant">
                                {isConnected ? (account.account_handle || account.display_name || "Connected") : "Not connected"}
                              </p>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => isConnected ? handleDisconnect(account.id) : handleConnect(platform)}
                          disabled={isBusy}
                           className={`rounded-card border px-4 py-2 text-[10px] font-bold transition-all ${isConnected ? 'bg-white border-aura-error/20 text-aura-error hover:bg-aura-error hover:text-white' : 'bg-aura-surface-container-high border-aura-outline/10 text-aura-on-surface hover:border-aura-primary hover:text-aura-primary'} disabled:opacity-50`}
                        >
                          {isBusy ? "..." : (isConnected ? "Disconnect" : "Connect")}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </DataCard>
            </div>
          </div>
        </div>

        {/* Sidebar Info (Right/Narrow) */}
        <div className="lg:col-span-4 space-y-10">
          {/* AI Backbone Settings */}
          <section className="dashboard-panel relative overflow-hidden p-8">
             <div className="relative z-10 space-y-8">
               <div className="flex items-center gap-4">
                 <div className="w-12 h-12 rounded-2xl bg-aura-on-surface flex items-center justify-center text-white shadow-xl">
                    <Key className="w-6 h-6" />
                 </div>
                 <div>
                    <h3 className="text-lg font-bold text-aura-on-surface">AI Backbone</h3>
                    <p className="text-xs text-aura-on-surface-variant">Intelligence operating layer</p>
                 </div>
               </div>

               <form onSubmit={handleAiBackboneSave} className="space-y-6">
                  <FieldSet title="Engine Source" description="Source of language processing resources" className="bg-transparent border-none p-0">
                   <SelectField
                     value={aiBackboneForm.accessMode}
                     onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, accessMode: val }))}
                     options={AI_BACKBONE_OPTIONS.map(opt => ({ value: opt.value, label: opt.title }))}
                   />
                 </FieldSet>

                 {aiBackboneForm.accessMode === "customer_api_key" && (
                   <div className="space-y-4 pt-2 border-t border-aura-outline/5">
                     <FormField
                       label="Endpoint URL"
                       value={aiBackboneForm.customerApiUrl}
                       onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, customerApiUrl: val }))}
                       placeholder="https://api.openai.com/v1"
                     />
                     <FormField
                       label="Secret API Key"
                       type="password"
                       value={aiBackboneForm.customerApiKey}
                       onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, customerApiKey: val }))}
                       placeholder="sk-..."
                     />
                   </div>
                 )}

                 {aiBackboneForm.accessMode === "chatgpt_oauth" && (
                   <div className="space-y-4 pt-2 border-t border-aura-outline/5">
                     {aiBackbone?.chatgpt_oauth.linked ? (
                         <div className="dashboard-card space-y-4 border-emerald-100 bg-emerald-50 p-4">
                           <div className="flex items-center justify-between">
                              <span className="text-[10px] uppercase font-bold text-emerald-600 tracking-widest">Linked Account</span>
                              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                           </div>
                           <div>
                              <p className="text-sm font-bold text-emerald-900">{aiBackboneForm.chatgptDisplayName}</p>
                              <p className="text-[10px] text-emerald-700 opacity-70 truncate">{aiBackboneForm.chatgptSubject}</p>
                           </div>
                           <button 
                             type="button"
                             onClick={handleDisconnectChatgptOAuth}
                             disabled={busyKey === "chatgpt-disconnect"}
                              className="rounded-card w-full border border-rose-100 bg-white py-2 text-[10px] font-bold text-rose-600 transition-all hover:bg-rose-50"
                           >
                              Disconnect ChatGPT
                           </button>
                        </div>
                     ) : (
                       <div className="space-y-4">
                          <FormField
                              label="Display Name (Optional)"
                             value={aiBackboneForm.chatgptDisplayName}
                             onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, chatgptDisplayName: val }))}
                          />
                           <button
                             type="button"
                             onClick={(e: any) => handleLinkChatgptOAuth(e)}
                             disabled={busyKey === "chatgpt-link"}
                             className="btn-primary btn-wide flex items-center gap-3 disabled:opacity-45"
                           >
                              <Key className="w-4 h-4" />
                               Connect ChatGPT Plus / Pro
                           </button>
                       </div>
                     )}
                   </div>
                 )}

                  <button
                    type="submit"
                    disabled={busyKey === "ai-backbone"}
                    className="btn-primary btn-wide btn-sm flex items-center gap-2 disabled:opacity-45"
                  >
                    <Save className="w-3 h-3" />
                     {busyKey === "ai-backbone" ? "Saving settings..." : "Update Engine"}
                  </button>
               </form>
             </div>

             {/* Background Decoration */}
             <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-aura-primary/5 rounded-full blur-3xl" />
          </section>

          {/* Quick Info Card */}
            <div className="dashboard-panel-soft border border-aura-tertiary/10 bg-aura-tertiary-container/10 p-8">
              <div className="flex items-center gap-2 mb-4">
                 <AlertCircle className="w-4 h-4 text-aura-tertiary" />
                 <span className="text-[10px] font-bold uppercase tracking-widest text-aura-tertiary">Agent Instrument Tips</span>
              </div>
                 <p className="text-xs text-aura-on-surface leading-loose">
                  Precise instrument settings lead to better autonomous behavior. Use the "Agent Behavior Definition" to set specific rules for how the AI should react to different scenarios.
               </p>
           </div>
        </div>
      </div>
    </div>
  );
}

