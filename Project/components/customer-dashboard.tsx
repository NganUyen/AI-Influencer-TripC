"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Bot,
  Database,
  LayoutDashboard,
  Radio,
  Users,
  Zap,
  Clock,
  CheckCircle,
  type LucideIcon,
} from "lucide-react";

import { customerApiRequest } from "@/lib/customer-api";
import { getClientTelegramBotLaunchUrl } from "@/lib/public-env";
import { useCustomerAuthStore } from "@/store/customer-auth-store";
import { DashboardHeader } from "@/components/DashboardHeader";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { Panel } from "@/components/ui/Panel";
import { PanelHeader } from "@/components/ui/PanelHeader";
import { StatCard } from "@/components/ui/StatCard";
import { DataCard } from "@/components/ui/DataCard";
import { FormField } from "@/components/ui/FormField";
import { SelectField } from "@/components/ui/SelectField";
import { TextAreaField } from "@/components/ui/TextAreaField";
import { ButtonGroup } from "@/components/ui/ButtonGroup";
import { PersonaCard } from "@/components/ui/PersonaCard";
import { ThreadItem } from "@/components/ui/ThreadItem";
import { MessageBubble } from "@/components/ui/MessageBubble";
import { TimelineItem } from "@/components/ui/TimelineItem";
import { FieldSet } from "@/components/ui/FieldSet";


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

export type DashboardTabId = "overview" | "ops" | "skills" | "memory" | "live_feed";

export type DashboardTab = {
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
  const { user, isAuthenticated, initialized, isLoading, logout } = useCustomerAuthStore();
// // Replace the destructuring with mock values:
//   const { user, isAuthenticated, initialized, isLoading, logout } = {
//     user: { name: "Preview User", email: "preview@example.com" },
//     isAuthenticated: true,
//     initialized: true,
//     isLoading: false,
//     logout: () => console.log("Logout clicked"),
//   };
  
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

  const [campaignDraft, setCampaignDraft] = useState({
    name: "",
    description: "",
    targetPlatforms: "linkedin,facebook,twitter",
  });

  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const telegramBotUrl = getClientTelegramBotLaunchUrl();
  const telegramVerificationUrl = getClientTelegramBotLaunchUrl(linkToken?.start_token);

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

// const fetchSystemData = useCallback(async () => {
//   setSystemSummary({
//     services: [
//       { name: "API Gateway", status: "online", latency: "24ms" },
//       { name: "Worker Node", status: "online", latency: "115ms" }
//     ],
//     quota: [
//       { name: "GPT-4o Tokens", used: 45000, total: 100000, unit: "tokens" },
//       { name: "Image Gen", used: 12, total: 50, unit: "images" }
//     ]
//   });
//   setSystemWorkflows([
//     { id: "wf-123", name: "Content Generation", status: "running", progress: 65 }
//   ]);
// }, []);

  useEffect(() => {
    void fetchSystemData();
    const interval = setInterval(fetchSystemData, 30000);
    return () => clearInterval(interval);
  }, [fetchSystemData]);

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

// async function loadWorkspace() {
//   setPageError(null);
  
//   // Set dummy brand data
//   setBrandForm({
//     product_name: "Acme AI",
//     website_url: "https://acme.ai",
//     audience: "Tech Enthusiasts",
//     offer_summary: "AI-driven marketing automation",
//     tone_voice: "Professional & Witty",
//     timezone: "UTC+7",
//     campaign_goals: ["Brand Awareness"],
//     asset_urls: [],
//     telegram_contact: "@acme_bot",
//   });

//   // Set dummy social accounts
//   setAccounts([
//     { id: "1", platform: "linkedin", account_handle: "@acme", display_name: "Acme Corp", connection_status: "connected" },
//     { id: "2", platform: "twitter", account_handle: "@acme_ai", display_name: "Acme AI", connection_status: "connected" }
//   ]);

//   // Set dummy campaigns
//   setCampaigns([
//     { id: "c1", name: "Spring Launch", description: "New AI features", target_platforms: ["linkedin"], status: "running", approval_status: "approved", active_workflow_id: "w1" }
//   ]);

//   // Add more setters as needed for personas, threads, etc.
// }

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

  async function handleLogout() {
    setBusyKey("signout");
    setPageError(null);
    try {
      await logout();
      router.replace("/auth");
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to sign out");
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
    <div className="min-h-screen bg-zinc-950 text-stone-100">
      <DashboardHeader
        userName={user?.name}
        userEmail={user?.email}
        telegramBotUrl={telegramBotUrl}
        onLogout={() => void handleLogout()}
        isSigningOut={busyKey === "signout"}
      />

      <div className="flex pt-0">
        <DashboardSidebar
          tabs={DASHBOARD_TABS}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <main className="md:ml-64 flex-1 px-4 md:px-6 py-6 md:py-8 min-w-0">
          <div className="mx-auto max-w-7xl space-y-4 md:space-y-6">


        {banner && (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
            {banner}
          </div>
        )}

        {pageError && (
          <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {pageError}
          </div>
        )}

        {activeTab === "overview" && (
          <div className="space-y-6">
            <Panel variant="elevated">
              <PanelHeader 
                title="Quick Stats" 
                subtitle="Current workflow pulse"
              />
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
                <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-3 md:p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="w-4 h-4 text-emerald-400" />
                    <p className="text-xs font-medium text-zinc-400 uppercase tracking-wide">Active</p>
                  </div>
                  <p className="text-2xl md:text-3xl font-bold text-emerald-400">
                    {campaigns.filter(c => c.status === 'active').length}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Campaigns</p>
                </div>

                <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-3 md:p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Clock className="w-4 h-4 text-amber-400" />
                    <p className="text-xs font-medium text-zinc-400 uppercase tracking-wide">Pending</p>
                  </div>
                  <p className="text-2xl md:text-3xl font-bold text-amber-400">
                    {approvals.length}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Approvals</p>
                </div>

                <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-3 md:p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle className="w-4 h-4 text-sky-400" />
                    <p className="text-xs font-medium text-zinc-400 uppercase tracking-wide">Published</p>
                  </div>
                  <p className="text-2xl md:text-3xl font-bold text-sky-400">
                    {content.filter(c => c.status === 'published').length}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Content</p>
                </div>

                <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-3 md:p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="w-4 h-4 text-emerald-400" />
                    <p className="text-xs font-medium text-zinc-400 uppercase tracking-wide">AI</p>
                  </div>
                  <p className="text-2xl md:text-3xl font-bold text-emerald-400">
                    {personas?.length || 0}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Personas</p>
                </div>
              </div>
            </Panel>

            <div className="grid gap-4 md:gap-6 lg:grid-cols-2">
              <Panel variant="elevated">
                <PanelHeader 
                  title="System Health" 
                  subtitle="Service status and runtime availability."
                />
                <div className="space-y-3">
                  {(systemSummary?.services || []).length === 0 && (
                    <p className="text-sm text-stone-400">No system service data available yet.</p>
                  )}
                  {(systemSummary?.services || []).map((service) => (
                    <div
                      key={service.name}
                      className="flex items-center justify-between rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl px-4 py-3"
                    >
                      <div>
                        <p className="font-medium text-white">{service.name}</p>
                        <p className="text-xs text-zinc-500">
                          Latency {service.latency}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${
                          service.status === 'online' ? 'bg-emerald-400' :
                          service.status === 'warning' ? 'bg-amber-400' : 'bg-rose-400'
                        }`} />
                        <span className="text-xs text-zinc-400 capitalize">{service.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Panel>

              <Panel variant="elevated">
                <PanelHeader 
                  title="AI Backbone" 
                  subtitle="Current model access mode and readiness."
                />
                <div className="space-y-4">
                  <div className="rounded-lg border border-emerald-500/15 bg-emerald-500/5 backdrop-blur-xl p-4">
                    <p className="text-xs font-medium text-emerald-300 uppercase tracking-wide">
                      Access Mode
                    </p>
                    <p className="mt-2 text-lg font-semibold uppercase text-white">
                      {aiBackbone?.access_mode.replace(/_/g, " ") || "Loading"}
                    </p>
                    <p className="mt-2 text-sm text-zinc-400">
                      {aiBackbone?.effective_status.message || "Initializing workspace access."}
                    </p>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-4">
                      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
                        Workspace Endpoint
                      </p>
                      <p className="mt-2 break-all text-sm text-white">
                        {aiBackbone?.workspace_default.api_url || "Not configured"}
                      </p>
                    </div>
                    <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-4">
                      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
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

            <div className="grid gap-4 md:gap-6 lg:grid-cols-2">
              <Panel variant="elevated">
                <PanelHeader 
                  title="Recent Activity" 
                  subtitle="Latest events across campaigns, content, and workflow state."
                />
                <ActivityFeed items={activityItems} />
              </Panel>

              <Panel variant="elevated">
                <PanelHeader 
                  title="Quota Snapshot" 
                  subtitle="Current provider usage pulled from system summary."
                />
                <div className="space-y-3">
                  {(systemSummary?.quota || []).length === 0 && (
                    <p className="text-sm text-stone-400">No quota data available yet.</p>
                  )}
                  {(systemSummary?.quota || []).map((quotaItem) => (
                    <div
                      key={quotaItem.name}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-4"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <p className="font-medium text-white">{quotaItem.name}</p>
                        <p className="text-sm text-zinc-400">
                          {quotaItem.used}/{quotaItem.total} {quotaItem.unit}
                        </p>
                      </div>
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]"
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
          <div className="grid gap-4 md:gap-6 lg:grid-cols-3">
            <section className="lg:col-span-2 space-y-4 md:space-y-6">
              <Panel variant="elevated">
                <PanelHeader 
                  title="In-App OpenClaw Assistant" 
                  subtitle="Refine positioning and content plans."
                />
                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="space-y-3 rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wide">Threads</h3>
                      <button type="button" onClick={() => void handleCreateThread()} disabled={busyKey === "thread"} className="rounded border border-blue-500/40 bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-300 transition-all duration-200 ease-out hover:border-blue-500/60 hover:bg-blue-500/20 active:scale-[0.98] disabled:opacity-50">New</button>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto space-y-2">
                      {threads.length === 0 && <p className="text-xs text-zinc-500">No threads yet.</p>}
                      {threads.map((thread) => (
                        <ThreadItem
                          key={thread.id}
                          id={thread.id}
                          title={thread.title}
                          preview={thread.last_message_preview || undefined}
                          isActive={selectedThreadId === thread.id}
                          onClick={() => setSelectedThreadId(thread.id)}
                        />
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-4">
                    <div className="flex-1 min-h-0">
                      <div className="max-h-[300px] overflow-y-auto pr-2 space-y-3 mb-4">
                        {messages.map((message) => (
                          <MessageBubble
                            key={message.id}
                            id={message.id}
                            role={message.role}
                            content={message.content}
                          />
                        ))}
                      </div>
                    </div>
                    <form className="space-y-3 flex-shrink-0" onSubmit={handleSendMessage}>
                      <TextAreaField
                        value={composer}
                        onChange={(e) => setComposer(e.target.value)}
                        placeholder="Type a message..."
                        minHeight="60px"
                        containerClassName="flex-1"
                      />
                      <button type="submit" disabled={busyKey === "assistant"} className="w-full bg-blue-500 text-white font-semibold py-2.5 rounded-lg shadow-lg shadow-blue-500/20 transition-all duration-200 ease-out hover:bg-blue-400 hover:shadow-blue-500/30 active:scale-[0.98] disabled:opacity-50">
                        {busyKey === "assistant" ? "OpenClaw Thinking..." : "Send to AI"}
                      </button>
                    </form>
                  </div>
                </div>
              </Panel>
              <Panel variant="elevated">
                <PanelHeader 
                  title="Campaign Control" 
                  subtitle="Manage workflow drafts."
                />          
                <div className="space-y-3">
                  {campaigns.map(c => (
                    <div key={c.id} className="p-3 bg-white/[0.02] border border-white/[0.08] rounded-lg backdrop-blur-xl transition-colors duration-200 ease-out hover:bg-white/[0.04]">
                      <div className="flex justify-between items-center mb-3">
                        <h4 className="font-medium text-white text-sm">{c.name}</h4>
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${
                            c.status === 'running' ? 'bg-emerald-400' :
                            c.status === 'pending' ? 'bg-amber-400' : 'bg-zinc-400'
                          }`} />
                          <span className="text-xs text-zinc-400 capitalize">{c.status}</span>
                        </div>
                      </div>
                      <button onClick={() => handleLaunch(c.id)} disabled={c.approval_status !== "approved" || busyKey === `launch-${c.id}`} className="w-full px-3 py-2 bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-blue-500/20 transition-all duration-200 ease-out hover:bg-blue-400 hover:shadow-blue-500/30 active:scale-[0.98] disabled:opacity-50">
                        {busyKey === `launch-${c.id}` ? "Launching..." : "Launch"}
                      </button>
                    </div>
                  ))}
                  {campaigns.length === 0 && <p className="text-sm text-zinc-500 italic">Queue clear.</p>}
                </div>
              </Panel>
            </section>

            <section className="space-y-4 md:space-y-6">
              <Panel variant="elevated">
                <PanelHeader 
                  title="Pending Approvals" subtitle="Action items."/>
                <div className="space-y-3">
                  {approvals.map(a => (
                    <div key={a.id} className="p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg backdrop-blur-xl">
                      <p className="font-medium text-amber-300 text-sm">{a.name}</p>
                      <div className="mt-3">
                        <ButtonGroup
                          buttons={[
                            {
                              label: "Approve",
                              onClick: () => handleApprove(a.id, true),
                              variant: "primary",
                            },
                            {
                              label: "Reject",
                              onClick: () => handleApprove(a.id, false),
                              variant: "danger",
                            },
                          ]}
                          size="sm"
                        />
                      </div>
                    </div>
                  ))}
                  {approvals.length === 0 && <p className="text-sm text-zinc-500 italic">System clear.</p>}
                </div>
              </Panel>
              <Panel variant="elevated">
                <PanelHeader 
                  title="Output Stream" 
                  subtitle="Recently published."
                />        
                <div className="space-y-2">
                  {content.slice(0, 5).map(item => (
                    <div key={item.id} className="p-3 bg-white/[0.02] border border-white/[0.08] rounded-lg backdrop-blur-xl text-xs flex justify-between items-center transition-colors duration-200 ease-out hover:bg-white/[0.04]">
                      <span className="text-zinc-400 truncate mr-2">{item.title}</span>
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${
                          item.status === 'published' ? 'bg-emerald-400' :
                          item.status === 'scheduled' ? 'bg-amber-400' : 'bg-zinc-400'
                        }`} />
                        <span className="text-zinc-500 capitalize">{item.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Panel>
            </section>
          </div>
        )}

        {activeTab === "skills" && (
          <div className="space-y-4 md:space-y-6">
            <Panel variant="elevated">
              <PanelHeader 
                title="AI Influencer Personas" 
                subtitle="Your account-linked characters."
              />

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
                {personas.map(p => (
                  <PersonaCard
                    key={p.persona_id}
                    id={p.persona_id}
                    name={p.display_name}
                    avatarUrl={p.avatar_image_url || undefined}
                    status={p.status}
                    videoCount={p.video_count}
                    tone="emerald"
                  />
                ))}

                <div className="border border-dashed border-zinc-700 rounded-lg p-6 md:p-8 flex flex-col items-center justify-center text-center space-y-4 transition-colors duration-200 ease-out hover:bg-white/[0.02] group cursor-pointer">
                  <p className="text-xs text-zinc-500">Create more characters on Telegram</p>
                  {telegramBotUrl && (
                    <a href={telegramBotUrl} target="_blank" rel="noreferrer" className="px-4 py-2 bg-blue-500 text-white font-semibold rounded text-xs uppercase tracking-wide shadow-lg shadow-blue-500/20 transition-all duration-200 ease-out hover:bg-blue-400 hover:shadow-blue-500/30 active:scale-[0.98]">Open Bot</a>
                  )}
                </div>
              </div>
            </Panel>
          </div>
        )}

        {activeTab === "memory" && (
          <div className="grid gap-4 md:gap-6 lg:grid-cols-2">
            <Panel variant="elevated">
              <PanelHeader 
                title="Brand Context" subtitle="Knowledge assets."/>
              <form className="space-y-4 md:space-y-6" onSubmit={handleBrandSave}>
                <FieldSet title="Brand Profile" description="Core information about your brand">
                  <FormField
                    label="Brand Name"
                    value={brandForm.product_name || ""}
                    onChange={v => setBrandForm(c => ({ ...c, product_name: v }))}
                    placeholder="Enter your brand name"
                  />
                  <TextAreaField
                    label="Audience"
                    value={brandForm.audience || ""}
                    onChange={v => setBrandForm(c => ({ ...c, audience: v }))}
                    placeholder="Describe your target audience"
                    minHeight="80px"
                  />
                  <TextAreaField
                    label="Offer Summary"
                    value={brandForm.offer_summary || ""}
                    onChange={v => setBrandForm(c => ({ ...c, offer_summary: v }))}
                    placeholder="Summarize your product or service offering"
                    minHeight="80px"
                  />
                </FieldSet>
                <button type="submit" className="w-full bg-blue-500 text-white font-semibold py-2.5 rounded-lg shadow-lg shadow-blue-500/20 transition-all duration-200 ease-out hover:bg-blue-400 hover:shadow-blue-500/30 active:scale-[0.98]">Update Memory</button>
              </form>
            </Panel>

            <div className="space-y-4 md:space-y-6">
              <Panel variant="elevated">
                <PanelHeader 
                  title="Intelligence Settings" subtitle="AI configurations."/>
                <div className="p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-lg backdrop-blur-xl">
                  <p className="text-xs font-medium text-emerald-400 uppercase tracking-wide">Access Mode</p>
                  <p className="text-lg font-semibold text-white mt-1 uppercase">{aiBackbone?.access_mode.replace(/_/g, " ")}</p>
                  <p className="text-xs text-zinc-400 mt-2">{aiBackbone?.effective_status.message}</p>
                </div>
              </Panel>

              <Panel variant="elevated">
                <PanelHeader 
                  title="System Bridge" subtitle="Telegram sync."/>
                {telegramLink?.linked ? (
                  <div className="flex justify-between items-center p-4 bg-emerald-500/5 border border-emerald-500/20 rounded-lg backdrop-blur-xl">
                    <div>
                      <p className="text-sm font-semibold text-white">@{telegramLink.link?.telegram_username || "Linked Account"}</p>
                      <p className="text-xs text-zinc-500 uppercase">Chat ID: {telegramLink.link?.chat_id}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-emerald-400" />
                      <span className="text-xs text-zinc-400">Linked</span>
                    </div>
                  </div>
                ) : (
                  <button onClick={handleStartTelegramLink} className="w-full bg-blue-500 text-white font-semibold py-2.5 rounded-lg shadow-lg shadow-blue-500/20 transition-all duration-200 ease-out hover:bg-blue-400 hover:shadow-blue-500/30 active:scale-[0.98]">
                    {busyKey === "telegram-link" ? "Generating Link..." : "Connect Telegram"}
                  </button>
                )}
                {linkToken && (
                  <div className="mt-4 p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg backdrop-blur-xl text-center">
                    <p className="text-xs text-amber-300 mb-3 font-medium">
                      {isPollingTelegramLink
                        ? "Waiting for Telegram confirmation. This card updates automatically."
                        : "Secure link ready. Finish the confirmation in Telegram."}
                    </p>
                    {telegramVerificationUrl && (
                      <a href={telegramVerificationUrl} target="_blank" rel="noreferrer" className="bg-amber-500 text-zinc-950 px-4 py-2 rounded font-semibold text-xs uppercase tracking-wide shadow-lg shadow-amber-500/20 transition-all duration-200 ease-out hover:bg-amber-400 hover:shadow-amber-500/30 active:scale-[0.98] inline-block">Verify Now</a>
                    )}
                  </div>
                )}
              </Panel>

              <Panel variant="elevated">
                <PanelHeader 
                  title="Social Grid" subtitle="Publishing targets."/>
                <div className="grid grid-cols-2 gap-3">
                  {SUPPORTED_PLATFORMS.map(p => {
                    const acc = accounts.find(a => a.platform === p);
                    return (
                      <div key={p} className="p-3 bg-white/[0.02] border border-white/[0.08] rounded-lg backdrop-blur-xl flex justify-between items-center transition-colors duration-200 ease-out hover:bg-white/[0.04]">
                        <p className="text-xs font-medium uppercase tracking-wide">{p}</p>
                        {acc ? <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-emerald-400" />
                          <span className="text-xs text-zinc-400">Linked</span>
                        </div> : (
                          <button onClick={() => handleConnect(p)} className="text-xs text-zinc-500 hover:text-blue-400 uppercase font-medium tracking-wide transition-colors">Link</button>
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
          <div className="grid gap-4 md:gap-6 lg:grid-cols-2">
            <Panel variant="elevated">
              <PanelHeader 
                title="Activity Feed" subtitle="Recent customer-facing events and workflow changes."/>
              <ActivityFeed
                items={activityItems}
                emptyMessage="Activity will appear here once workflows, approvals, or content updates arrive."
              />
            </Panel>

            <Panel variant="elevated">
              <PanelHeader 
                title="Workflow Monitor" subtitle="Current workflow queue and publishing output."/>
              <div className="space-y-4">
                <div className="space-y-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Runtime Workflows
                  </p>
                  {systemWorkflows.length === 0 && (
                    <p className="text-sm text-zinc-400">No active workflow telemetry right now.</p>
                  )}
                  {systemWorkflows.map((workflow) => (
                    <div
                      key={workflow.id}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-4"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="font-medium text-white">{workflow.name}</p>
                          <p className="text-xs text-zinc-500">
                            {workflow.id}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${
                            workflow.status === 'running' ? 'bg-emerald-400' :
                            workflow.status === 'completed' ? 'bg-sky-400' : 'bg-rose-400'
                          }`} />
                          <span className="text-xs text-zinc-400 capitalize">{workflow.status}</span>
                        </div>
                      </div>
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]"
                          style={{ width: `${Math.max(0, Math.min(workflow.progress, 100))}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Recent Output
                  </p>
                  {content.slice(0, 5).map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-4 rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-4"
                    >
                      <div>
                        <p className="font-medium text-white">{item.title}</p>
                        <p className="text-xs text-zinc-500">
                          {(item.platform || []).join(", ")}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${
                          item.status === 'published' ? 'bg-emerald-400' :
                          item.status === 'scheduled' ? 'bg-amber-400' : 'bg-zinc-400'
                        }`} />
                        <span className="text-xs text-zinc-400 capitalize">{item.status}</span>
                      </div>
                    </div>
                  ))}
                  {content.length === 0 && (
                    <p className="text-sm text-zinc-400">No recent output yet.</p>
                  )}
                </div>
              </div>
            </Panel>
          </div>
        )}
          </div>
        </main>
      </div>
    </div>
  );
}

/* function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[32px] border border-white/[0.08] bg-white/[0.03] p-6 backdrop-blur-xl">
      <div className="mb-5">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-300">
          {title}
        </p>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400 leading-relaxed">{subtitle}</p>
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
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    sky: "text-sky-400",
    stone: "text-stone-300",
  }[tone];

  return (
    <div className="rounded-[16px] border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl p-4">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
        {label}
      </p>
      <p className={`mt-3 text-3xl font-semibold ${toneClasses}`}>{value}</p>
    </div>
  );
} */

function ActivityFeed({
  items,
  emptyMessage = "No activity yet.",
}: {
  items: ActivityItem[];
  emptyMessage?: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-zinc-400">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-4">
      {items.map((item) => {
        const variant = item.tone === "success" 
          ? "success" as const
          : item.tone === "warning" 
            ? "warning" as const
            : "info" as const;
        
        return (
          <TimelineItem
            key={item.id}
            id={item.id}
            title={item.title}
            description={item.detail}
            variant={variant}
          />
        );
      })}
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
      <span className="mb-2 block text-xs font-semibold uppercase tracking-widest text-zinc-500">
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-[14px] border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl px-4 py-3 text-sm text-white placeholder:text-zinc-500 outline-none transition-colors focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
      />
    </label>
  );
}

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
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
