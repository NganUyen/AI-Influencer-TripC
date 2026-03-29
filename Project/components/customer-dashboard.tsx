"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Bot,
  Database,
  LayoutDashboard,
  Radio,
  Users,
  type LucideIcon,
} from "lucide-react";

import { customerApiRequest } from "@/lib/customer-api";
import {
  deriveTelegramBotUsername,
  getClientPublicEnvValue,
} from "@/lib/public-env";
import { useCustomerAuthStore } from "@/store/customer-auth-store";

type BrandProfile = {
  product_name: string | null;
  website_url: string | null;
  audience: string | null;
  offer_summary: string | null;
  tone_voice: string | null;
  timezone: string | null;
  campaign_goals: string[] | null;
  asset_urls: string[] | null;
  telegram_contact: string | null;
};

type SocialAccount = {
  id: string;
  platform: string;
  account_handle: string | null;
  display_name: string | null;
  connection_status: string;
};

type AssistantThread = {
  id: string;
  title: string;
  created_at: string;
  last_message_preview: string | null;
};

type AssistantMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

type AssistantArtifact = {
  id: string;
  title: string;
  type: string;
  payload: any;
  created_at: string;
};

type Campaign = {
  id: string;
  name: string;
  description: string | null;
  target_platforms: string[];
  status: string;
  approval_status: string;
  active_workflow_id: string | null;
};

type ContentItem = {
  id: string;
  title: string;
  platform: string[];
  status: string;
  scheduled_at: string | null;
  published_at: string | null;
};

type AIBackboneSettings = {
  access_mode: "workspace_default" | "customer_api_key" | "chatgpt_oauth";
  customer_api: {
    api_url: string | null;
    has_api_key: boolean;
  };
  workspace_default: {
    api_url: string;
  };
  chatgpt_oauth: {
    linked: boolean;
    chatgpt_subject: string | null;
    session_ready: boolean;
    session_expires_at: string | null;
  };
  effective_status: {
    ready: boolean;
    message: string;
  };
};

type Persona = {
  persona_id: string;
  display_name: string;
  avatar_image_url: string | null;
  status: string;
  video_count: number;
};

type TelegramLinkStatus = {
  linked: boolean;
  link?: {
    telegram_username: string | null;
    chat_id: string;
  };
};

type TelegramLinkToken = {
  start_token: string;
  expires_at: string;
};

type SystemSummaryData = {
  services: { name: string; status: "online" | "warning" | "error"; latency: string }[];
  quota: { name: string; used: number; total: number; unit: string }[];
};

type SystemWorkflowData = {
  id: string;
  name: string;
  status: "idle" | "running" | "completed" | "error";
  progress: number;
};

type DashboardTabId = "overview" | "ops" | "skills" | "memory" | "live_feed";

type DashboardTab = {
  id: DashboardTabId;
  label: string;
  icon: LucideIcon;
};

type ActivityItemTone = "default" | "success" | "warning";

type ActivityItem = {
  id: string;
  title: string;
  detail: string;
  tone?: ActivityItemTone;
};

const EMPTY_BRAND: BrandProfile = {
  product_name: "",
  website_url: "",
  audience: "",
  offer_summary: "",
  tone_voice: "",
  timezone: "UTC",
  campaign_goals: [],
  asset_urls: [],
  telegram_contact: "",
};

const SUPPORTED_PLATFORMS = ["linkedin", "facebook", "twitter", "instagram", "tiktok"];

const AI_BACKBONE_OPTIONS = [
  {
    value: "workspace_default",
    title: "Shared Backbone",
    description: "Use the agency's provisioned AI infrastructure.",
  },
  {
    value: "customer_api_key",
    title: "Customer API Key",
    description: "Provide your own OpenClaw API key and endpoint.",
  },
  {
    value: "chatgpt_oauth",
    title: "GPT OAuth",
    description: "Direct connection to your GPT Plus or Pro account.",
  },
] as const;

const DASHBOARD_TABS: DashboardTab[] = [
  { id: "overview", label: "Tổng quan", icon: LayoutDashboard },
  { id: "ops", label: "AI vận hành", icon: Bot },
  { id: "skills", label: "Personas", icon: Users },
  { id: "memory", label: "Dự án & Memory", icon: Database },
  { id: "live_feed", label: "Activity Feed", icon: Radio },
];

function buildAiBackboneForm(
  settings: AIBackboneSettings,
  defaultDisplayName: string,
) {
  return {
    accessMode: settings.access_mode,
    customerApiUrl: settings.customer_api.api_url || "",
    customerApiKey: "",
    chatgptSubject: settings.chatgpt_oauth.chatgpt_subject || "",
    chatgptDisplayName: defaultDisplayName,
    chatgptSubscriptionTier: "plus" as "plus" | "pro",
  };
}

export default function CustomerDashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isAuthenticated, initialized, isLoading } = useCustomerAuthStore();

  const [activeTab, setActiveTab] = useState<DashboardTabId>("overview");
  const [systemSummary, setSystemSummary] = useState<SystemSummaryData | null>(null);
  const [systemWorkflows, setSystemWorkflows] = useState<SystemWorkflowData[]>([]);

  const [brandForm, setBrandForm] = useState<BrandProfile>(EMPTY_BRAND);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [threads, setThreads] = useState<AssistantThread[]>([]);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [artifacts, setArtifacts] = useState<AssistantArtifact[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [composer, setComposer] = useState("");
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [approvals, setApprovals] = useState<Campaign[]>([]);
  const [content, setContent] = useState<ContentItem[]>([]);
  const [aiBackbone, setAiBackbone] = useState<AIBackboneSettings | null>(null);
  const [aiBackboneForm, setAiBackboneForm] = useState(() =>
    buildAiBackboneForm(
      {
        access_mode: "workspace_default",
        customer_api: { api_url: "", has_api_key: false },
        workspace_default: { api_url: "" },
        chatgpt_oauth: {
          linked: false,
          chatgpt_subject: null,
          session_ready: false,
          session_expires_at: null,
        },
        effective_status: { ready: false, message: "Initializing..." },
      },
      user?.name || user?.email || "",
    ),
  );
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [telegramLink, setTelegramLink] = useState<TelegramLinkStatus | null>(null);
  const [linkToken, setLinkToken] = useState<TelegramLinkToken | null>(null);
  const [isPollingTelegramLink, setIsPollingTelegramLink] = useState(false);
  const [telegramBotUrl, setTelegramBotUrl] = useState<string | null>(null);

  const [campaignDraft, setCampaignDraft] = useState({
    name: "",
    description: "",
    targetPlatforms: "linkedin,facebook,twitter",
  });

  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const fetchSystemData = useCallback(async () => {
    try {
      const [summary, workflows] = await Promise.all([
        customerApiRequest<SystemSummaryData>("/api/customer/system/summary"),
        customerApiRequest<{ workflows: SystemWorkflowData[] }>("/api/customer/system/workflows"),
      ]);
      setSystemSummary(summary);
      setSystemWorkflows(workflows.workflows);
    } catch (error) {
      console.error("Failed to fetch system monitoring data:", error);
    }
  }, []);

  useEffect(() => {
    void fetchSystemData();
    const interval = setInterval(fetchSystemData, 30000);
    return () => clearInterval(interval);
  }, [fetchSystemData]);

  useEffect(() => {
    setTelegramBotUrl(buildTelegramBotUrl());
  }, []);

  useEffect(() => {
    const oauthStatus = searchParams.get("oauth_status");
    const platform = searchParams.get("platform");
    const reason = searchParams.get("reason");
    if (oauthStatus === "success" && platform) {
      setBanner(`${platform} connected successfully.`);
    }
    if (oauthStatus === "error") {
      setBanner(reason || "OAuth connection failed.");
    }
  }, [searchParams]);

  useEffect(() => {
    if (!initialized || isLoading) {
      return;
    }
    if (!isAuthenticated) {
      router.replace("/auth");
      return;
    }
    void loadWorkspace();
  }, [initialized, isLoading, isAuthenticated, router]);

  useEffect(() => {
    if (selectedThreadId && isAuthenticated) {
      void loadThread(selectedThreadId);
    }
  }, [selectedThreadId, isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || !linkToken || telegramLink?.linked) {
      setIsPollingTelegramLink(false);
      return;
    }

    let cancelled = false;
    let timeoutId: number | undefined;
    const expiresAt = Date.parse(linkToken.expires_at);

    const pollTelegramLink = async () => {
      if (cancelled) {
        return;
      }

      if (Number.isFinite(expiresAt) && Date.now() >= expiresAt) {
        setLinkToken(null);
        setIsPollingTelegramLink(false);
        setBanner("Telegram link expired. Start a fresh secure link to continue.");
        return;
      }

      setIsPollingTelegramLink(true);

      try {
        const latestLink = await customerApiRequest<TelegramLinkStatus>(
          "/api/customer/telegram/link",
        );
        if (cancelled) {
          return;
        }

        setTelegramLink(latestLink);
        if (latestLink.linked) {
          setLinkToken(null);
          setIsPollingTelegramLink(false);
          setBanner("Telegram connected successfully.");
          return;
        }

        timeoutId = window.setTimeout(() => {
          void pollTelegramLink();
        }, 2500);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setIsPollingTelegramLink(false);
        setPageError(
          error instanceof Error
            ? error.message
            : "Failed to refresh Telegram link status",
        );
      }
    };

    void pollTelegramLink();

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [isAuthenticated, linkToken, telegramLink?.linked]);

  async function loadWorkspace() {
    try {
      setPageError(null);
      const [
        brand,
        social,
        assistant,
        campaignList,
        approvalList,
        contentList,
        aiBackboneResponse,
        personasList,
        telegramLinkResponse,
      ] = await Promise.all([
        customerApiRequest<{ brand_profile: BrandProfile | null }>("/api/customer/brand"),
        customerApiRequest<{ accounts: SocialAccount[] }>("/api/customer/social-accounts"),
        customerApiRequest<{ threads: AssistantThread[] }>("/api/customer/assistant/threads"),
        customerApiRequest<{ campaigns: Campaign[] }>("/api/customer/campaigns"),
        customerApiRequest<{ approvals: Campaign[] }>("/api/customer/approvals"),
        customerApiRequest<{ items: ContentItem[] }>("/api/customer/content"),
        customerApiRequest<{ settings: AIBackboneSettings }>("/api/customer/ai-backbone"),
        customerApiRequest<{ personas: Persona[] }>("/api/customer/personas"),
        customerApiRequest<TelegramLinkStatus>("/api/customer/telegram/link"),
      ]);

      setBrandForm(brand.brand_profile || EMPTY_BRAND);
      setAccounts(social.accounts);
      setThreads(assistant.threads);
      setCampaigns(campaignList.campaigns);
      setApprovals(approvalList.approvals);
      setContent(contentList.items);
      setPersonas(personasList.personas || []);
      setTelegramLink(telegramLinkResponse);
      const settings = aiBackboneResponse.settings;
      setAiBackbone(settings);
      setAiBackboneForm(buildAiBackboneForm(settings, user?.name || user?.email || ""));

      const nextThreadId = selectedThreadId || assistant.threads[0]?.id || null;
      setSelectedThreadId(nextThreadId);
      if (!nextThreadId) {
        setMessages([]);
        setArtifacts([]);
      }
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to load workspace");
    }
  }

  async function loadThread(threadId: string) {
    try {
      const payload = await customerApiRequest<{
        messages: AssistantMessage[];
        artifacts: AssistantArtifact[];
      }>(`/api/customer/assistant/threads/${threadId}/messages`);
      setMessages(payload.messages);
      setArtifacts(payload.artifacts);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to load thread");
    }
  }

  async function handleBrandSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyKey("brand");
    try {
      await customerApiRequest("/api/customer/brand", {
        method: "PUT",
        body: JSON.stringify({
          ...brandForm,
          campaign_goals: brandForm.campaign_goals || [],
          asset_urls: brandForm.asset_urls || [],
        }),
      });
      setBanner("Brand profile saved.");
      await loadWorkspace();
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to save brand profile");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleConnect(platform: string) {
    setBusyKey(`connect-${platform}`);
    try {
      const response = await customerApiRequest<{ auth_url: string }>(
        `/api/customer/social-accounts/${platform}/oauth/start`,
        { method: "POST" },
      );
      window.location.href = response.auth_url;
    } catch (error) {
      setPageError(error instanceof Error ? error.message : `Failed to connect ${platform}`);
      setBusyKey(null);
    }
  }

  async function handleDisconnect(accountId: string) {
    setBusyKey(`disconnect-${accountId}`);
    try {
      await customerApiRequest(`/api/customer/social-accounts/${accountId}/disconnect`, {
        method: "POST",
      });
      await loadWorkspace();
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to disconnect account");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleCreateThread() {
    setBusyKey("thread");
    try {
      const payload = await customerApiRequest<{ thread: AssistantThread }>(
        "/api/customer/assistant/threads",
        {
          method: "POST",
          body: JSON.stringify({ title: "Campaign Planning" }),
        },
      );
      setThreads((current) => [payload.thread, ...current]);
      setSelectedThreadId(payload.thread.id);
      setMessages([]);
      setArtifacts([]);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to create thread");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedThreadId || !composer.trim() || !aiBackbone?.effective_status.ready) {
      return;
    }
    setBusyKey("assistant");
    try {
      const payload = await customerApiRequest<{
        messages: AssistantMessage[];
        artifacts: AssistantArtifact[];
      }>(`/api/customer/assistant/threads/${selectedThreadId}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: composer.trim() }),
      });
      setMessages(payload.messages);
      setArtifacts(payload.artifacts);
      setComposer("");
      await loadWorkspace();
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Assistant request failed");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleAiBackboneSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyKey("ai-backbone");
    try {
      const payload: Record<string, unknown> = {
        access_mode: aiBackboneForm.accessMode,
      };
      if (aiBackboneForm.accessMode === "customer_api_key") {
        payload.openclaw_api_url = aiBackboneForm.customerApiUrl.trim();
        if (aiBackboneForm.customerApiKey.trim()) {
          payload.api_key = aiBackboneForm.customerApiKey.trim();
        }
      }
      const response = await customerApiRequest<{ settings: AIBackboneSettings }>(
        "/api/customer/ai-backbone",
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
      );
      setAiBackbone(response.settings);
      setAiBackboneForm((current) => ({
        ...buildAiBackboneForm(
          response.settings,
          current.chatgptDisplayName || user?.name || user?.email || "",
        ),
        customerApiKey: "",
        chatgptSubject: current.chatgptSubject,
        chatgptDisplayName: current.chatgptDisplayName,
        chatgptSubscriptionTier: current.chatgptSubscriptionTier,
      }));
      setBanner("AI backbone settings saved.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to save AI backbone settings");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleLinkChatgptOAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyKey("chatgpt-link");
    try {
      const response = await customerApiRequest<{ settings: AIBackboneSettings }>(
        "/api/customer/ai-backbone/chatgpt/oauth/link",
        {
          method: "POST",
          body: JSON.stringify({
            chatgpt_subject: aiBackboneForm.chatgptSubject.trim(),
            display_name: aiBackboneForm.chatgptDisplayName.trim(),
            subscription_tier: aiBackboneForm.chatgptSubscriptionTier,
          }),
        },
      );
      setAiBackbone(response.settings);
      setAiBackboneForm((current) =>
        buildAiBackboneForm(
          response.settings,
          current.chatgptDisplayName || user?.name || user?.email || "",
        ),
      );
      setBanner("GPT OAuth link connected for this customer.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to link GPT OAuth");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleDisconnectChatgptOAuth() {
    setBusyKey("chatgpt-disconnect");
    try {
      const response = await customerApiRequest<{ settings: AIBackboneSettings }>(
        "/api/customer/ai-backbone/chatgpt/oauth/disconnect",
        {
          method: "POST",
        },
      );
      setAiBackbone(response.settings);
      setAiBackboneForm((current) => ({
        ...buildAiBackboneForm(
          response.settings,
          current.chatgptDisplayName || user?.name || user?.email || "",
        ),
        chatgptSubject: current.chatgptSubject,
        chatgptDisplayName: current.chatgptDisplayName,
        chatgptSubscriptionTier: current.chatgptSubscriptionTier,
      }));
      setBanner("GPT OAuth link disconnected.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to disconnect GPT OAuth");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleCreateCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyKey("campaign");
    try {
      const targetPlatforms = splitCsv(campaignDraft.targetPlatforms);
      const payload = await customerApiRequest<{ campaign: Campaign }>(
        "/api/customer/campaigns",
        {
          method: "POST",
          body: JSON.stringify({
            name: campaignDraft.name,
            description: campaignDraft.description,
            target_platforms: targetPlatforms,
            connected_account_ids: accounts
              .filter(
                (account) =>
                  account.connection_status === "connected" &&
                  targetPlatforms.includes(account.platform),
              )
              .map((account) => account.id),
            source_thread_id: selectedThreadId,
          }),
        },
      );
      setCampaigns((current) => [payload.campaign, ...current]);
      setApprovals((current) => [payload.campaign, ...current]);
      setCampaignDraft({
        name: "",
        description: "",
        targetPlatforms: "linkedin,facebook,twitter",
      });
      setBanner("Campaign draft created.");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to create campaign");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleApprove(campaignId: string, approved: boolean) {
    setBusyKey(`approve-${campaignId}`);
    try {
      await customerApiRequest(`/api/customer/campaigns/${campaignId}/approve`, {
        method: "POST",
        body: JSON.stringify({
          approved,
          feedback: approved
            ? "Approved from customer dashboard"
            : "Rejected from customer dashboard",
        }),
      });
      await loadWorkspace();
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to update approval");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleLaunch(campaignId: string) {
    setBusyKey(`launch-${campaignId}`);
    try {
      await customerApiRequest(`/api/customer/campaigns/${campaignId}/launch`, {
        method: "POST",
      });
      setBanner("Campaign launched into Temporal.");
      await loadWorkspace();
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to launch campaign");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleStartTelegramLink() {
    setBusyKey("telegram-link");
    setPageError(null);
    try {
      const payload = await customerApiRequest<TelegramLinkToken>(
        "/api/customer/telegram/link/start",
        {
          method: "POST",
          body: JSON.stringify({ expires_in_minutes: 15 }),
        },
      );
      setLinkToken(payload);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to start Telegram link");
    } finally {
      setBusyKey(null);
    }
  }

  const activityItems = buildActivityItems({
    campaigns,
    approvals,
    content,
    systemWorkflows,
  });

  if (isLoading || !initialized) {
    return (
      <div className="min-h-screen bg-slate-950 text-stone-100 flex items-center justify-center">
        <p className="text-lg tracking-wide">Loading your workspace...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#1f3a34_0%,#0c1220_45%,#07080c_100%)] px-6 py-8 text-stone-100">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="rounded-[30px] border border-white/10 bg-white/5 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.25)] backdrop-blur">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-emerald-200/70">
                Customer Workspace
              </p>
              <h1 className="mt-3 text-4xl font-semibold text-white">
                Dashboard
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-relaxed text-stone-300">
                Manage your customer assistant threads, connected platforms,
                Telegram linking, and campaign approvals from one workspace.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:items-end">
              <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-stone-300">
                Signed in as <span className="font-semibold text-white">{user?.name || user?.email}</span>
              </div>
              {telegramBotUrl && (
                <a
                  href={telegramBotUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center rounded-full bg-emerald-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200"
                >
                  Open Telegram Bot
                </a>
              )}
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {DASHBOARD_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition ${
                  activeTab === tab.id
                    ? "border-emerald-300/60 bg-emerald-300 text-slate-950"
                    : "border-white/10 bg-white/5 text-stone-300 hover:border-white/20 hover:bg-white/10"
                }`}
              >
                <tab.icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        </section>

        {banner && (
          <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">
            {banner}
          </div>
        )}

        {pageError && (
          <div className="rounded-2xl border border-rose-300/20 bg-rose-300/10 px-4 py-3 text-sm text-rose-100">
            {pageError}
          </div>
        )}

      {activeTab === "overview" && (
        <div className="space-y-6">
          <Panel title="Quick Stats" subtitle="Current workflow pulse">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Active Workflows"
                value={String(systemWorkflows.length)}
                tone="emerald"
              />
              <StatCard
                label="Pending Approvals"
                value={String(approvals.length)}
                tone="amber"
              />
              <StatCard
                label="Connected Platforms"
                value={String(accounts.filter((account) => account.connection_status === "connected").length)}
                tone="sky"
              />
              <StatCard
                label="Active Personas"
                value={String(personas.length)}
                tone="stone"
              />
            </div>
          </Panel>

          <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <Panel title="System Health" subtitle="Service status and runtime availability.">
              <div className="space-y-3">
                {(systemSummary?.services || []).length === 0 && (
                  <p className="text-sm text-stone-400">No system service data available yet.</p>
                )}
                {(systemSummary?.services || []).map((service) => (
                  <div
                    key={service.name}
                    className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/20 px-4 py-3"
                  >
                    <div>
                      <p className="font-medium text-white">{service.name}</p>
                      <p className="text-xs uppercase tracking-[0.18em] text-stone-500">
                        Latency {service.latency}
                      </p>
                    </div>
                    <StatusBadge label={service.status} />
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="AI Backbone" subtitle="Current model access mode and readiness.">
              <div className="space-y-4">
                <div className="rounded-2xl border border-emerald-300/15 bg-emerald-300/5 p-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-200/80">
                    Access Mode
                  </p>
                  <p className="mt-2 text-lg font-semibold uppercase text-white">
                    {aiBackbone?.access_mode.replace(/_/g, " ") || "Loading"}
                  </p>
                  <p className="mt-2 text-sm text-stone-300">
                    {aiBackbone?.effective_status.message || "Initializing workspace access."}
                  </p>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-stone-500">
                      Workspace Endpoint
                    </p>
                    <p className="mt-2 break-all text-sm text-white">
                      {aiBackbone?.workspace_default.api_url || "Not configured"}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-stone-500">
                      Customer API
                    </p>
                    <p className="mt-2 text-sm text-white">
                      {aiBackbone?.customer_api.has_api_key ? "Configured" : "Using workspace-managed access"}
                    </p>
                  </div>
                </div>
              </div>
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <Panel title="Recent Activity" subtitle="Latest events across campaigns, content, and workflow state.">
              <ActivityFeed items={activityItems} />
            </Panel>

            <Panel title="Quota Snapshot" subtitle="Current provider usage pulled from system summary.">
              <div className="space-y-3">
                {(systemSummary?.quota || []).length === 0 && (
                  <p className="text-sm text-stone-400">No quota data available yet.</p>
                )}
                {(systemSummary?.quota || []).map((quotaItem) => (
                  <div
                    key={quotaItem.name}
                    className="rounded-2xl border border-white/10 bg-black/20 p-4"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <p className="font-medium text-white">{quotaItem.name}</p>
                      <p className="text-sm text-stone-300">
                        {quotaItem.used}/{quotaItem.total} {quotaItem.unit}
                      </p>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-emerald-300"
                        style={{
                          width: `${Math.min(
                            quotaItem.total > 0 ? (quotaItem.used / quotaItem.total) * 100 : 0,
                            100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      )}

      {activeTab === "ops" && (
        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
           <section className="space-y-6">
              <Panel title="In-App OpenClaw Assistant" subtitle="Refine positioning and content plans.">
                <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                  <div className="space-y-3 rounded-3xl border border-white/10 bg-black/20 p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-300">Threads</h3>
                      <button type="button" onClick={() => void handleCreateThread()} disabled={busyKey === "thread"} className="rounded-full border border-emerald-300/40 px-3 py-1 text-xs uppercase tracking-[0.18em] text-emerald-200 transition hover:border-emerald-200">New</button>
                    </div>
                    <div className="space-y-2">
                       {threads.length === 0 && <p className="text-xs text-slate-500">No threads yet.</p>}
                      {threads.map((thread) => (
                        <button key={thread.id} type="button" onClick={() => setSelectedThreadId(thread.id)} className={`w-full rounded-2xl border px-4 py-3 text-left transition ${selectedThreadId === thread.id ? "border-emerald-300 bg-emerald-200/10" : "border-white/8 bg-white/5 hover:border-white/20"}`}>
                          <p className="font-medium text-white truncate">{thread.title}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-4 rounded-3xl border border-white/10 bg-black/20 p-4">
                     <div className="max-h-[420px] overflow-y-auto pr-2 space-y-3">
                        {messages.map((message) => (
                          <div key={message.id} className={`rounded-3xl px-4 py-3 text-sm ${message.role === "assistant" ? "bg-emerald-200/10 text-stone-100" : "bg-white/8 text-stone-200"}`}>
                            <p className="mb-1 text-[10px] uppercase text-stone-500">{message.role}</p>
                            <p className="whitespace-pre-wrap">{message.content}</p>
                          </div>
                        ))}
                     </div>
                     <form className="space-y-2" onSubmit={handleSendMessage}>
                        <textarea value={composer} onChange={(e) => setComposer(e.target.value)} placeholder="Type a message..." className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-white text-sm outline-none focus:border-emerald-500" />
                        <button type="submit" disabled={busyKey === "assistant"} className="w-full bg-emerald-500 text-slate-950 font-bold py-2 rounded-xl hover:bg-emerald-400 transition-colors disabled:opacity-50">
                           {busyKey === "assistant" ? "OpenClaw Thinking..." : "Send to AI"}
                        </button>
                     </form>
                  </div>
                </div>
              </Panel>
              
              <Panel title="Campaign Control" subtitle="Manage workflow drafts.">
                 <div className="space-y-4">
                    {campaigns.map(c => (
                      <div key={c.id} className="p-4 bg-white/5 border border-white/10 rounded-2xl hover:border-emerald-500/30 transition-all">
                        <div className="flex justify-between items-center">
                          <h4 className="font-bold text-white">{c.name}</h4>
                          <StatusBadge label={c.status} />
                        </div>
                        <div className="mt-4 flex gap-2">
                           <button onClick={() => handleLaunch(c.id)} disabled={c.approval_status !== "approved" || busyKey === `launch-${c.id}`} className="px-4 py-1.5 bg-white text-slate-900 rounded-full text-xs font-bold hover:bg-emerald-200 transition-colors disabled:opacity-50">
                              {busyKey === `launch-${c.id}` ? "Launching..." : "Launch"}
                           </button>
                        </div>
                      </div>
                    ))}
                    {campaigns.length === 0 && <p className="text-sm text-slate-500 italic">Queue clear.</p>}
                 </div>
              </Panel>
           </section>
           
           <section className="space-y-6">
              <Panel title="Pending Approvals" subtitle="Action items.">
                 <div className="space-y-3">
                    {approvals.map(a => (
                      <div key={a.id} className="p-4 bg-amber-500/5 border border-amber-500/20 rounded-2xl">
                        <p className="font-medium text-amber-100">{a.name}</p>
                        <div className="mt-4 flex gap-2">
                           <button onClick={() => handleApprove(a.id, true)} className="px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-lg text-xs font-bold hover:bg-emerald-500/30">Approve</button>
                           <button onClick={() => handleApprove(a.id, false)} className="px-3 py-1 bg-rose-500/20 text-rose-400 rounded-lg text-xs font-bold hover:bg-rose-500/30">Reject</button>
                        </div>
                      </div>
                    ))}
                    {approvals.length === 0 && <p className="text-sm text-slate-500 italic">System clear.</p>}
                 </div>
              </Panel>

              <Panel title="Output Stream" subtitle="Recently published.">
                 <div className="space-y-2">
                    {content.slice(0, 5).map(item => (
                      <div key={item.id} className="p-3 bg-white/5 border border-white/10 rounded-xl text-xs flex justify-between items-center">
                         <span className="text-slate-300 truncate mr-2">{item.title}</span>
                         <StatusBadge label={item.status} />
                      </div>
                    ))}
                 </div>
              </Panel>
           </section>
        </div>
      )}

      {activeTab === "skills" && (
        <div className="space-y-6">
           <Panel title="AI Influencer Personas" subtitle="Your account-linked characters.">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                 {personas.map(p => (
                   <div key={p.persona_id} className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 flex items-center gap-4 hover:border-emerald-500/30 transition-all group">
                      <div className="w-16 h-16 bg-slate-800 rounded-xl overflow-hidden">
                        {p.avatar_image_url && <img src={p.avatar_image_url} alt={p.display_name} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-bold text-white truncate">{p.display_name}</h4>
                        <StatusBadge label={p.status} />
                      </div>
                   </div>
                 ))}
                 
                 <div className="border border-dashed border-slate-700 rounded-2xl p-8 flex flex-col items-center justify-center text-center space-y-4 hover:bg-white/5 transition-colors group cursor-pointer">
                    <p className="text-xs text-slate-500">Create more characters on Telegram</p>
                    {telegramBotUrl && (
                      <a href={telegramBotUrl} target="_blank" rel="noreferrer" className="px-6 py-2 bg-emerald-500 text-slate-950 font-bold rounded-full text-[10px] uppercase tracking-widest hover:bg-emerald-400 transition-all">Open Bot</a>
                    )}
                 </div>
              </div>
           </Panel>
        </div>
      )}

      {activeTab === "memory" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
           <Panel title="Brand Context" subtitle="Knowledge assets.">
              <form className="space-y-4" onSubmit={handleBrandSave}>
                 <Field label="Brand Name" value={brandForm.product_name || ""} onChange={v => setBrandForm(c => ({...c, product_name: v}))} />
                 <TextAreaField label="Audience" value={brandForm.audience || ""} onChange={v => setBrandForm(c => ({...c, audience: v}))} />
                 <TextAreaField label="Offer Summary" value={brandForm.offer_summary || ""} onChange={v => setBrandForm(c => ({...c, offer_summary: v}))} />
                 <button type="submit" className="w-full bg-emerald-500 text-slate-950 font-bold py-3 rounded-xl hover:bg-emerald-400 transition-colors">Update Memory</button>
              </form>
           </Panel>

           <div className="space-y-6">
              <Panel title="Intelligence Settings" subtitle="AI configurations.">
                 <div className="p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-2xl">
                    <p className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest">Access Mode</p>
                    <p className="text-lg font-bold text-white mt-1 uppercase">{aiBackbone?.access_mode.replace(/_/g, " ")}</p>
                    <p className="text-xs text-slate-400 mt-2">{aiBackbone?.effective_status.message}</p>
                 </div>
              </Panel>

              <Panel title="System Bridge" subtitle="Telegram sync.">
                 {telegramLink?.linked ? (
                   <div className="flex justify-between items-center p-4 bg-emerald-500/5 border border-emerald-500/20 rounded-2xl">
                      <div>
                        <p className="text-sm font-bold text-white">@{telegramLink.link?.telegram_username || "Linked Account"}</p>
                        <p className="text-[10px] text-slate-500 uppercase">Chat ID: {telegramLink.link?.chat_id}</p>
                      </div>
                      <StatusBadge label="Linked" />
                   </div>
                 ) : (
                   <button onClick={handleStartTelegramLink} className="w-full bg-white text-slate-900 font-bold py-3 rounded-xl hover:bg-emerald-200 transition-colors">
                      {busyKey === "telegram-link" ? "Generating Link..." : "Connect Telegram"}
                   </button>
                 )}
                 {linkToken && (
                    <div className="mt-4 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl text-center">
                       <p className="text-xs text-amber-200 mb-3 font-medium">
                          {isPollingTelegramLink
                            ? "Waiting for Telegram confirmation. This card updates automatically."
                            : "Secure link ready. Finish the confirmation in Telegram."}
                       </p>
                       <a href={`${telegramBotUrl}?start=${linkToken.start_token}`} target="_blank" rel="noreferrer" className="bg-amber-400 text-slate-900 px-6 py-2 rounded-full font-bold text-[10px] uppercase tracking-widest hover:bg-amber-300 transition-colors inline-block">Verify Now</a>
                    </div>
                 )}
              </Panel>

              <Panel title="Social Grid" subtitle="Publishing targets.">
                 <div className="grid grid-cols-2 gap-3">
                    {SUPPORTED_PLATFORMS.map(p => {
                      const acc = accounts.find(a => a.platform === p);
                      return (
                        <div key={p} className="p-3 bg-white/5 border border-white/10 rounded-xl flex justify-between items-center">
                           <p className="text-[10px] font-bold uppercase">{p}</p>
                           {acc ? <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" /> : (
                             <button onClick={() => handleConnect(p)} className="text-[10px] text-slate-500 hover:text-white uppercase font-bold tracking-tighter">Link</button>
                           )}
                        </div>
                      );
                    })}
                 </div>
              </Panel>
           </div>
        </div>
      )}

      {activeTab === "live_feed" && (
        <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <Panel title="Activity Feed" subtitle="Recent customer-facing events and workflow changes.">
            <ActivityFeed
              items={activityItems}
              emptyMessage="Activity will appear here once workflows, approvals, or content updates arrive."
            />
          </Panel>

          <Panel title="Workflow Monitor" subtitle="Current workflow queue and publishing output.">
            <div className="space-y-4">
              <div className="space-y-3">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">
                  Runtime Workflows
                </p>
                {systemWorkflows.length === 0 && (
                  <p className="text-sm text-stone-400">No active workflow telemetry right now.</p>
                )}
                {systemWorkflows.map((workflow) => (
                  <div
                    key={workflow.id}
                    className="rounded-2xl border border-white/10 bg-black/20 p-4"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="font-medium text-white">{workflow.name}</p>
                        <p className="text-xs uppercase tracking-[0.18em] text-stone-500">
                          {workflow.id}
                        </p>
                      </div>
                      <StatusBadge label={workflow.status} />
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-emerald-300"
                        style={{ width: `${Math.max(0, Math.min(workflow.progress, 100))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="space-y-3">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">
                  Recent Output
                </p>
                {content.slice(0, 5).map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-black/20 p-4"
                  >
                    <div>
                      <p className="font-medium text-white">{item.title}</p>
                      <p className="text-xs uppercase tracking-[0.18em] text-stone-500">
                        {(item.platform || []).join(", ")}
                      </p>
                    </div>
                    <StatusBadge label={item.status} />
                  </div>
                ))}
                {content.length === 0 && (
                  <p className="text-sm text-stone-400">No recent output yet.</p>
                )}
              </div>
            </div>
          </Panel>
        </div>
      )}
      </div>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[30px] border border-white/10 bg-white/5 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.25)] backdrop-blur">
      <div className="mb-5">
        <p className="text-xs uppercase tracking-[0.24em] text-emerald-200/70 font-bold">
          {title}
        </p>
        <p className="mt-2 max-w-2xl text-sm text-stone-400 leading-relaxed font-medium">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "emerald" | "amber" | "sky" | "stone";
}) {
  const toneClasses = {
    emerald: "text-emerald-300",
    amber: "text-amber-300",
    sky: "text-sky-300",
    stone: "text-stone-200",
  }[tone];

  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-stone-500">
        {label}
      </p>
      <p className={`mt-3 text-3xl font-semibold ${toneClasses}`}>{value}</p>
    </div>
  );
}

function ActivityFeed({
  items,
  emptyMessage = "No activity yet.",
}: {
  items: ActivityItem[];
  emptyMessage?: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-stone-400">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-start justify-between gap-4 rounded-2xl border border-white/10 bg-black/20 p-4"
        >
          <div>
            <p className="font-medium text-white">{item.title}</p>
            <p className="mt-1 text-sm text-stone-400">{item.detail}</p>
          </div>
          <div className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${activityToneClass(item.tone)}`} />
        </div>
      ))}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500 font-bold">
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-2xl border border-white/5 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-emerald-500"
      />
    </label>
  );
}

function TextAreaField({
  label,
  value,
  onChange,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <label className={className}>
      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500 font-bold">
        {label}
      </span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[92px] w-full rounded-2xl border border-white/5 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-emerald-500"
      />
    </label>
  );
}

function StatusBadge({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-emerald-200">
      {label.replaceAll("_", " ")}
    </span>
  );
}

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function buildTelegramBotUrl(): string | null {
  const explicitUrl = getClientPublicEnvValue("NEXT_PUBLIC_TELEGRAM_BOT_URL").trim();
  if (explicitUrl) {
    return explicitUrl;
  }

  const username =
    getClientPublicEnvValue("NEXT_PUBLIC_TELEGRAM_BOT_USERNAME").trim() ||
    deriveTelegramBotUsername(explicitUrl);
  if (!username) {
    return null;
  }

  return `https://t.me/${username.replace(/^@/, "")}`;
}

function buildActivityItems({
  campaigns,
  approvals,
  content,
  systemWorkflows,
}: {
  campaigns: Campaign[];
  approvals: Campaign[];
  content: ContentItem[];
  systemWorkflows: SystemWorkflowData[];
}): ActivityItem[] {
  const items: ActivityItem[] = [];

  systemWorkflows.slice(0, 3).forEach((workflow) => {
    items.push({
      id: `workflow-${workflow.id}`,
      title: workflow.name,
      detail: `${workflow.status} • ${workflow.progress}% complete`,
      tone:
        workflow.status === "completed"
          ? "success"
          : workflow.status === "error"
            ? "warning"
            : "default",
    });
  });

  approvals.slice(0, 2).forEach((approval) => {
    items.push({
      id: `approval-${approval.id}`,
      title: `Approval pending: ${approval.name}`,
      detail: `${approval.target_platforms.join(", ") || "No platform"} • ${approval.approval_status}`,
      tone: "warning",
    });
  });

  content.slice(0, 3).forEach((item) => {
    items.push({
      id: `content-${item.id}`,
      title: `Content: ${item.title}`,
      detail: `${item.platform.join(", ") || "No platform"} • ${describeContentTiming(item)}`,
      tone: item.status === "published" ? "success" : "default",
    });
  });

  campaigns.slice(0, 2).forEach((campaign) => {
    items.push({
      id: `campaign-${campaign.id}`,
      title: `Campaign: ${campaign.name}`,
      detail: `${campaign.status} • approval ${campaign.approval_status}`,
      tone: campaign.approval_status === "approved" ? "success" : "default",
    });
  });

  return items.slice(0, 8);
}

function describeContentTiming(item: ContentItem): string {
  if (item.published_at) {
    return `Published ${formatDateLabel(item.published_at)}`;
  }
  if (item.scheduled_at) {
    return `Scheduled ${formatDateLabel(item.scheduled_at)}`;
  }
  return item.status;
}

function formatDateLabel(value: string): string {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString();
}

function activityToneClass(tone: ActivityItemTone = "default"): string {
  if (tone === "success") {
    return "bg-emerald-300";
  }
  if (tone === "warning") {
    return "bg-amber-300";
  }
  return "bg-sky-300";
}
