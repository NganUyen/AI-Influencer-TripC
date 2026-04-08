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

type VideoContextDraft = {
  title: string;
  description: string;
  duration: string;
  style: string;
  targetAudience: string;
  keyMessages: string;
  callToAction: string;
  tone: string;
  personaId: string;
  platforms: string;
  language: string;
  subtitles: boolean;
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
  telegram_bot_url?: string | null;
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

const VIDEO_DURATION_OPTIONS = [
  { value: "15s", label: "15 seconds" },
  { value: "30s", label: "30 seconds" },
  { value: "60s", label: "60 seconds" },
  { value: "90s", label: "90 seconds" },
  { value: "2m", label: "2 minutes" },
] as const;

const VIDEO_STYLE_OPTIONS = [
  { value: "educational", label: "Educational" },
  { value: "promotional", label: "Promotional" },
  { value: "storytelling", label: "Storytelling" },
  { value: "tutorial", label: "Tutorial" },
  { value: "testimonial", label: "Testimonial" },
] as const;

const VIDEO_TONE_OPTIONS = [
  { value: "professional", label: "Professional" },
  { value: "casual", label: "Casual" },
  { value: "energetic", label: "Energetic" },
  { value: "bold", label: "Bold" },
] as const;

const VIDEO_PLATFORM_OPTIONS = [
  { value: "tiktok", label: "TikTok" },
  { value: "instagram", label: "Instagram" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "facebook", label: "Facebook" },
  { value: "twitter", label: "Twitter / X" },
  { value: "youtube", label: "YouTube" },
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
  const { user, isAuthenticated, initialized, isLoading, logout, initialize } = useCustomerAuthStore();
// // Replace the destructuring with mock values:
  // const { user, isAuthenticated, initialized, isLoading, logout } = {
  //   user: { name: "Preview User", email: "preview@example.com" },
  //   isAuthenticated: true,
  //   initialized: true,
  //   isLoading: false,
  //   logout: () => console.log("Logout clicked"),
  // };
  
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

  const [videoContextDraft, setVideoContextDraft] = useState<VideoContextDraft>({
    title: "",
    description: "",
    duration: "60s",
    style: "promotional",
    targetAudience: "",
    keyMessages: "",
    callToAction: "",
    tone: "professional",
    personaId: "",
    platforms: "tiktok,instagram,linkedin",
    language: "Vietnamese",
    subtitles: false,
  });
  const [isVideoContextModalOpen, setIsVideoContextModalOpen] = useState(false);

  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const telegramBotUrl = systemSummary?.telegram_bot_url || getClientTelegramBotLaunchUrl();
  const telegramVerificationUrl = getClientTelegramBotLaunchUrl(linkToken?.start_token);

  const fetchSystemData = useCallback(async () => {
    // Only attempt fetch if we are in the browser and authenticated
    if (typeof window === "undefined" || !isAuthenticated) {
      return;
    }

    try {
      const [summary, workflows] = await Promise.all([
        customerApiRequest<SystemSummaryData>("/api/customer/system/summary"),
        customerApiRequest<{ workflows: SystemWorkflowData[] }>("/api/customer/system/workflows"),
      ]);
      setSystemSummary(summary);
      setSystemWorkflows(workflows.workflows);
    } catch (error) {
      if (error instanceof TypeError && error.message === "Failed to fetch") {
        console.warn("[Dashboard] System data fetch failed (Network error).");
        return;
      }
      
      const msg = error instanceof Error ? error.message : "";
      if (
        msg.includes("401") ||
        msg.includes("Unauthorized") ||
        msg.toLowerCase().includes("invalid or expired")
      ) {
        void logout();
        router.replace("/auth");
      } else {
        console.error("Failed to fetch system monitoring data:", error);
      }
    }
  }, [isAuthenticated, logout, router]);

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
    if (!initialized && !isLoading) {
       // Only start initialize if we aren't already loading
       void initialize();
    } else if (!initialized) {
       void initialize();
    }
  }, [initialized, initialize]);

  useEffect(() => {
    if (!initialized || isLoading || pageError) {
      return;
    }
    if (!isAuthenticated) {
      router.replace("/auth");
      return;
    }
    void loadWorkspace();
  }, [initialized, isLoading, isAuthenticated, router, pageError]);

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

      setBrandForm(brand?.brand_profile || EMPTY_BRAND);
      setAccounts(social?.accounts || []);
      setThreads(assistant?.threads || []);
      setCampaigns(campaignList?.campaigns || []);
      setApprovals(approvalList?.approvals || []);
      setContent(contentList?.items || []);
      
      // Robust handling for persona list (handles both raw array and object with personas key)
      const personasData = (personasList as any)?.personas || (Array.isArray(personasList) ? personasList : []);
      setPersonas(personasData);
      
      setTelegramLink(telegramLinkResponse || null);
      
      const settings = aiBackboneResponse?.settings || {
        access_mode: "workspace_default",
        customer_api: { api_url: "", has_api_key: false },
        workspace_default: { api_url: "" },
        chatgpt_oauth: { linked: false, chatgpt_subject: null, session_ready: false, session_expires_at: null },
        effective_status: { ready: false, message: "Initializing..." },
      };
      setAiBackbone(settings);
      setAiBackboneForm(buildAiBackboneForm(settings, user?.name || user?.email || ""));

      const nextThreadId = selectedThreadId || assistant?.threads?.[0]?.id || null;
      setSelectedThreadId(nextThreadId);
      if (!nextThreadId) {
        setMessages([]);
        setArtifacts([]);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to load workspace";
      if (
        msg.includes("401") ||
        msg.includes("Unauthorized") ||
        msg.toLowerCase().includes("invalid or expired")
      ) {
        void logout();
        router.replace("/auth");
        return;
      }
      setPageError(msg);
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

  function handleVideoContextSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyKey("video-context");
    setBanner("Video context saved locally. Ready for AI generation.");
    setBusyKey(null);
    console.log("videoContextDraft", videoContextDraft);
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

  const [quotaBannerDismissed, setQuotaBannerDismissed] = useState(false);

  if (isLoading || !initialized) {
    return (
      <div className="min-h-screen bg-aura-surface">
        <DashboardHeader
          userName={undefined}
          userEmail={undefined}
          telegramBotUrl={null}
          onLogout={() => {}}
          isSigningOut={false}
        />
        <div className="flex pt-16">
          <DashboardSidebar
            tabs={DASHBOARD_TABS}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
          <main className="flex-1 min-w-0 px-6 md:px-10 py-8">
            <div className="mx-auto max-w-7xl h-[60vh] flex flex-col items-center justify-center space-y-4">
              <div className="animate-spin h-10 w-10 border-2 border-aura-primary border-t-transparent rounded-full" />
              <p className="text-sm text-aura-outline font-body">Loading workspace…</p>
            </div>
          </main>
        </div>
      </div>
    );
  }

  // Quota warnings — providers at ≥80% usage
  const quotaWarnings = (systemSummary?.quota || []).filter(
    (q) => q.total > 0 && q.used / q.total >= 0.8,
  );

  return (
    <div className="min-h-screen bg-aura-surface text-aura-on-surface">
      <DashboardHeader
        userName={user?.name}
        userEmail={user?.email}
        telegramBotUrl={telegramBotUrl}
        onLogout={() => void handleLogout()}
        isSigningOut={busyKey === "signout"}
      />

      <div className="flex pt-16 min-h-[calc(100vh-64px)]">
        <DashboardSidebar
          tabs={DASHBOARD_TABS}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          telegramBotUrl={telegramBotUrl}
        />

        <main className="flex-1 min-w-0 px-6 md:px-10 py-8">
          <div className="mx-auto max-w-7xl space-y-6">


        {/* Success banner */}
        {banner && (
          <div className="flex items-center justify-between rounded-2xl border border-aura-tertiary/20 bg-aura-tertiary-container/30 px-5 py-3 text-sm text-aura-tertiary font-medium">
            <span>✓ {banner}</span>
            <button onClick={() => setBanner(null)} className="ml-4 text-aura-tertiary/60 hover:text-aura-tertiary transition-colors">✕</button>
          </div>
        )}

        {/* Error banner */}
        {pageError && (
          <div className="flex items-center justify-between rounded-2xl border border-aura-error/20 bg-aura-error-container/20 px-5 py-3 text-sm text-aura-error font-medium">
            <span>⚠ {pageError}</span>
            <button onClick={() => setPageError(null)} className="ml-4 text-aura-error/60 hover:text-aura-error transition-colors">✕</button>
          </div>
        )}

        {/* ─── Quota Warning Banner ─── */}
        {activeTab === "overview" && quotaWarnings.length > 0 && !quotaBannerDismissed && (
          <div className="flex items-start justify-between gap-4 rounded-2xl border border-aura-secondary/30 bg-aura-secondary-container/40 px-5 py-4">
            <div className="flex items-start gap-3">
              <span className="text-xl leading-none mt-0.5">⚠️</span>
              <div>
                <p className="font-semibold text-aura-secondary text-sm">Quota cảnh báo vượt ngưỡng hôm nay</p>
                <p className="text-xs text-aura-on-surface-variant mt-0.5">
                  {quotaWarnings.map((q) => {
                    const pct = Math.round((q.used / q.total) * 100);
                    return `${q.name} (${pct}%)`;
                  }).join(" · ")}
                </p>
              </div>
            </div>
            <button
              onClick={() => setQuotaBannerDismissed(true)}
              className="flex-shrink-0 text-aura-secondary/60 hover:text-aura-secondary transition-colors text-sm"
            >
              ✕
            </button>
          </div>
        )}

        {activeTab === "overview" && (
          <div className="space-y-8 animate-fade-in">

            {/* ── Quick Stats Row ── */}
            <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                {
                  label: "Active Campaigns",
                  value: campaigns.filter((c) => c.status === "active").length,
                  sub: `${campaigns.length} total`,
                  color: "text-aura-tertiary",
                  bg: "bg-aura-tertiary-container/30",
                },
                {
                  label: "Pending Approvals",
                  value: approvals.length,
                  sub: approvals.length > 0 ? "Action needed" : "All clear",
                  color: approvals.length > 0 ? "text-aura-secondary" : "text-aura-tertiary",
                  bg: approvals.length > 0 ? "bg-aura-secondary-container/30" : "bg-aura-tertiary-container/20",
                },
                {
                  label: "Published Content",
                  value: content.filter((c) => c.status === "published").length,
                  sub: `${content.length} total items`,
                  color: "text-aura-primary",
                  bg: "bg-aura-primary-container/20",
                },
                {
                  label: "AI Personas",
                  value: personas?.length ?? 0,
                  sub: personas && personas.length > 0 ? `${personas.filter(p => p.status === 'active').length} active` : "None yet",
                  color: "text-aura-on-surface",
                  bg: "bg-aura-surface-container",
                },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="bg-white rounded-2xl p-5 shadow-aura flex flex-col gap-2"
                >
                  <span className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-body">
                    {stat.label}
                  </span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-3xl font-extrabold text-aura-on-surface font-headline">
                      {stat.value}
                    </span>
                    <span className={`text-xs font-semibold ${stat.color}`}>{stat.sub}</span>
                  </div>
                  <div className={`h-1 rounded-full mt-1 ${stat.bg}`} />
                </div>
              ))}
            </section>

            {/* ── Main Grid ── */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

              {/* Left: System Health + AI Backbone */}
              <div className="lg:col-span-4 space-y-6">

                {/* System Health */}
                <div className="bg-aura-surface-container-high rounded-2xl p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-base font-bold text-aura-on-surface font-headline">System Health</h3>
                    <span className="flex items-center gap-1.5 px-3 py-1 bg-aura-tertiary-fixed text-aura-on-tertiary-fixed rounded-full text-[10px] font-bold uppercase tracking-wider">
                      <span className="w-1.5 h-1.5 rounded-full bg-aura-tertiary animate-pulse-slow" />
                      {(systemSummary?.services || []).length > 0 ? "OPERATIONAL" : "LOADING"}
                    </span>
                  </div>

                  <div className="space-y-4">
                    {(systemSummary?.services || []).length === 0 ? (
                      <div className="space-y-3">
                        {["Core API", "Vector DB", "Edge Proxy"].map((name) => (
                          <div key={name} className="flex items-center justify-between">
                            <span className="text-sm text-aura-on-surface-variant">{name}</span>
                            <div className="h-4 w-12 bg-aura-surface-container rounded animate-pulse" />
                          </div>
                        ))}
                      </div>
                    ) : (
                      (systemSummary?.services || []).map((service) => (
                        <div key={service.name} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span
                              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                                service.status === "online"
                                  ? "bg-aura-tertiary"
                                  : service.status === "warning"
                                  ? "bg-aura-secondary"
                                  : "bg-aura-error"
                              }`}
                            />
                            <span className="text-sm font-medium text-aura-on-surface">{service.name}</span>
                          </div>
                          <span className="text-xs font-mono bg-aura-surface px-2 py-0.5 rounded-full text-aura-on-surface-variant">
                            {service.latency}
                          </span>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Load bars */}
                  <div className="mt-6 p-3 bg-aura-surface rounded-xl">
                    <span className="text-[10px] uppercase font-bold text-aura-outline tracking-wider mb-2 block">Real-time Load</span>
                    <div className="h-14 flex items-end gap-1">
                      {[40, 60, 45, 85, 70, 55, 40, 65, 50, 80].map((h, i) => (
                        <div
                          key={i}
                          className={`flex-1 rounded-t-sm transition-all duration-500 ${
                            h > 75 ? "bg-aura-primary" : "bg-aura-primary-container"
                          }`}
                          style={{ height: `${h}%` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                {/* AI Backbone */}
                <div className="bg-aura-surface-container-highest rounded-2xl p-6">
                  <h3 className="text-base font-bold text-aura-on-surface font-headline mb-5">AI Backbone</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="text-[10px] uppercase font-bold text-aura-on-surface-variant block mb-1.5">Access Mode</label>
                      <div className="flex items-center justify-between px-4 py-2.5 bg-aura-surface rounded-full">
                        <span className="text-sm font-semibold text-aura-on-surface capitalize">
                          {aiBackbone?.access_mode.replace(/_/g, " ") || "Loading…"}
                        </span>
                        {aiBackbone?.effective_status.ready ? (
                          <span className="w-4 h-4 rounded-full bg-aura-tertiary flex items-center justify-center">
                            <span className="text-white text-[10px]">✓</span>
                          </span>
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-aura-secondary animate-pulse" />
                        )}
                      </div>
                    </div>

                    <div>
                      <label className="text-[10px] uppercase font-bold text-aura-on-surface-variant block mb-1.5">Status</label>
                      <p className="text-xs text-aura-on-surface-variant px-1">
                        {aiBackbone?.effective_status.message || "Initializing workspace access."}
                      </p>
                    </div>

                    <div>
                      <label className="text-[10px] uppercase font-bold text-aura-on-surface-variant block mb-1.5">Endpoint</label>
                      <div className="flex items-center text-xs font-mono text-aura-on-surface-variant truncate bg-aura-surface px-3 py-2 rounded-xl">
                        <span className="truncate">{aiBackbone?.workspace_default.api_url || "Not configured"}</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="text-center bg-aura-surface rounded-xl p-3">
                        <label className="text-[10px] uppercase font-bold text-aura-on-surface-variant block mb-1">Customer Key</label>
                        <span className="text-sm font-bold text-aura-on-surface">
                          {aiBackbone?.customer_api.has_api_key ? "Set" : "Shared"}
                        </span>
                      </div>
                      <div className="text-center bg-aura-surface rounded-xl p-3">
                        <label className="text-[10px] uppercase font-bold text-aura-on-surface-variant block mb-1">GPT OAuth</label>
                        <span className="text-sm font-bold text-aura-on-surface">
                          {aiBackbone?.chatgpt_oauth.linked ? "Linked" : "—"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right: Quota + Personas */}
              <div className="lg:col-span-8 space-y-6">

                {/* Quota Snapshot */}
                <div className="bg-white rounded-2xl p-7 shadow-aura">
                  <div className="flex items-center justify-between mb-7">
                    <div>
                      <h2 className="text-2xl font-extrabold text-aura-on-surface font-headline leading-tight">Quota Snapshot</h2>
                      <p className="text-xs text-aura-on-surface-variant mt-0.5">Provider-specific consumption today</p>
                    </div>
                    {quotaWarnings.length > 0 && (
                      <span className="flex items-center gap-2 px-3 py-1.5 bg-aura-secondary-container rounded-full text-xs font-bold text-aura-on-secondary-container">
                        ⚠️ {quotaWarnings.length} over 80%
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
                    {(systemSummary?.quota || []).length === 0 ? (
                      // Skeleton placeholder when no data
                      ["OpenAI", "Anthropic", "Image Gen"].map((name) => (
                        <div key={name} className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-sm font-medium text-aura-on-surface-variant">{name}</span>
                            <span className="text-xs text-aura-outline">—</span>
                          </div>
                          <div className="h-2.5 bg-aura-surface-container-high rounded-full" />
                        </div>
                      ))
                    ) : (
                      (systemSummary?.quota || []).map((q) => {
                        const pct = q.total > 0 ? Math.min((q.used / q.total) * 100, 100) : 0;
                        const isOverThreshold = pct >= 80;
                        const isCritical = pct >= 95;
                        return (
                          <div key={q.name} className="space-y-2.5">
                            <div className="flex justify-between items-end">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-aura-on-surface">{q.name}</span>
                                {isOverThreshold && (
                                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                                    isCritical
                                      ? "bg-aura-error-container/30 text-aura-error"
                                      : "bg-aura-secondary-container/50 text-aura-secondary"
                                  }`}>
                                    {isCritical ? "⚠ Critical" : "⚠ High"}
                                  </span>
                                )}
                              </div>
                              <span className={`text-sm font-bold ${
                                isCritical ? "text-aura-error" : isOverThreshold ? "text-aura-secondary" : "text-aura-on-surface"
                              }`}>
                                {Math.round(pct)}% consumed
                              </span>
                            </div>
                            <div className="h-2.5 bg-aura-surface-container-high rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-700 ${
                                  isCritical
                                    ? "bg-gradient-to-r from-aura-error to-aura-error-container"
                                    : isOverThreshold
                                    ? "bg-gradient-to-r from-aura-secondary to-aura-secondary-fixed"
                                    : "bg-gradient-to-r from-aura-primary to-aura-primary-container"
                                }`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <p className="text-[10px] text-aura-outline">
                              {q.used.toLocaleString()} / {q.total.toLocaleString()} {q.unit}
                            </p>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* AI Persona Bento */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  {personas.length === 0 ? (
                    <div className="sm:col-span-2 bg-aura-surface-container-low rounded-2xl p-6 text-center text-sm text-aura-outline">
                      No personas configured yet.
                    </div>
                  ) : (
                    personas.slice(0, 4).map((persona) => (
                      <div
                        key={persona.persona_id}
                        className="bg-white rounded-2xl p-5 shadow-aura border border-aura-outline-variant/15 flex flex-col gap-4 hover:shadow-aura-md transition-shadow duration-200"
                      >
                        <div className="flex gap-3">
                          <div className="w-14 h-14 rounded-xl bg-aura-primary-container/30 flex items-center justify-center flex-shrink-0 overflow-hidden">
                            {persona.avatar_image_url ? (
                              <img
                                src={persona.avatar_image_url}
                                alt={persona.display_name}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <span className="text-xl font-bold text-aura-primary">
                                {persona.display_name.charAt(0).toUpperCase()}
                              </span>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className="text-sm font-bold text-aura-on-surface truncate">{persona.display_name}</h4>
                            <p className="text-xs text-aura-on-surface-variant mt-0.5 truncate">{persona.status}</p>
                            <span className={`inline-block mt-1.5 text-[10px] px-2 py-0.5 rounded-full font-bold ${
                              persona.status === "active"
                                ? "bg-aura-tertiary-container/50 text-aura-tertiary"
                                : "bg-aura-surface-container text-aura-on-surface-variant"
                            }`}>
                              {persona.status === "active" ? "● LIVE" : "● IDLE"}
                            </span>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-aura-surface-container">
                          <div className="text-center">
                            <p className="text-[10px] text-aura-on-surface-variant uppercase font-bold">Videos</p>
                            <p className="text-base font-bold text-aura-on-surface mt-0.5">{persona.video_count}</p>
                          </div>
                          <div className="text-center">
                            <p className="text-[10px] text-aura-on-surface-variant uppercase font-bold">Status</p>
                            <p className={`text-sm font-bold mt-0.5 ${
                              persona.status === "active" ? "text-aura-tertiary" : "text-aura-outline"
                            }`}>
                              {persona.status === "active" ? "ZEN" : "IDLE"}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Recent Activity */}
                <div className="bg-white rounded-2xl p-7 shadow-aura">
                  <h3 className="text-base font-bold text-aura-on-surface font-headline mb-5">Recent Activity</h3>
                  {activityItems.length === 0 ? (
                    <p className="text-sm text-aura-outline">No recent activity yet.</p>
                  ) : (
                    <div className="space-y-3">
                      {activityItems.map((item) => (
                        <div key={item.id} className="flex items-start gap-3">
                          <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${auraActivityDotClass(item.tone)}` } />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-aura-on-surface truncate">{item.title}</p>
                            <p className="text-xs text-aura-on-surface-variant truncate">{item.detail}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "ops" && (
          <div className="space-y-10 animate-fade-in">

            {/* ── Hero / Quick Stats Bento ── */}
            <section className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {/* Hero card */}
              <div className="md:col-span-2 bg-gradient-to-br from-aura-primary to-aura-primary-container p-8 rounded-2xl flex flex-col justify-between text-aura-on-primary shadow-aura-md min-h-[220px]">
                <div>
                  <h2 className="text-3xl font-headline font-bold mb-2">AI vận hành</h2>
                  <p className="text-aura-on-primary/80 font-body max-w-xs text-sm">
                    Integrated view of your AI Influencer ecosystem — campaigns, backbone, and real-time quota.
                  </p>
                </div>
                <div className="flex items-center gap-3 mt-6">
                  <button
                    type="button"
                    onClick={() => void handleCreateThread()}
                    disabled={busyKey === "thread"}
                    className="bg-white/20 hover:bg-white/30 backdrop-blur-md px-6 py-2.5 rounded-full font-body text-sm transition-all active:scale-95 disabled:opacity-50"
                  >
                    + New Thread
                  </button>
                </div>
              </div>

              {/* Quick stat cards */}
              <div className="md:col-span-2 grid grid-cols-2 gap-4">
                {[
                  { label: "Active Campaigns", value: campaigns.filter(c => c.status === "active").length, border: "border-aura-primary" },
                  { label: "Pending Approvals", value: approvals.length, border: "border-aura-secondary" },
                  { label: "Published Content", value: content.filter(c => c.status === "published").length, border: "border-aura-tertiary" },
                  { label: "AI Personas", value: personas?.length ?? 0, border: "border-aura-outline" },
                ].map(stat => (
                  <div key={stat.label} className={`bg-white p-6 rounded-xl shadow-aura-sm border-l-4 ${stat.border}`}>
                    <p className="text-aura-on-surface-variant text-[10px] font-body uppercase tracking-widest mb-1">{stat.label}</p>
                    <p className="text-4xl font-headline font-extrabold text-aura-on-surface">{stat.value}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* ── Technical Integration Row ── */}
            <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">

              {/* System Health */}
              <div className="bg-aura-surface-container-low p-7 rounded-2xl space-y-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-headline font-bold text-aura-on-surface">System Health</h3>
                  <span className="flex h-2 w-2 rounded-full bg-aura-tertiary animate-pulse" />
                </div>
                <div className="space-y-3">
                  {(systemSummary?.services || []).length === 0 ? (
                    [
                      { name: "Temporal Cluster", icon: "☁" },
                      { name: "OpenClaw AI", icon: "🧠" },
                      { name: "Postiz Publisher", icon: "📡" },
                      { name: "GrowChief Growth", icon: "📈" },
                    ].map(s => (
                      <div key={s.name} className="flex items-center justify-between p-3 bg-white rounded-xl">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">{s.icon}</span>
                          <span className="text-sm font-body text-aura-on-surface-variant">{s.name}</span>
                        </div>
                        <div className="h-3 w-16 bg-aura-surface-container rounded animate-pulse" />
                      </div>
                    ))
                  ) : (
                    (systemSummary?.services || []).map(service => (
                      <div key={service.name} className="flex items-center justify-between p-3 bg-white rounded-xl">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            service.status === "online" ? "bg-aura-tertiary" :
                            service.status === "warning" ? "bg-aura-secondary" : "bg-aura-error"
                          }`} />
                          <span className="text-sm font-body text-aura-on-surface">{service.name}</span>
                        </div>
                        <div className="text-right">
                          <span className={`block text-[10px] font-bold uppercase ${
                            service.status === "online" ? "text-aura-tertiary" :
                            service.status === "warning" ? "text-aura-secondary" : "text-aura-error"
                          }`}>{service.status}</span>
                          <span className="block text-[10px] text-aura-on-surface-variant">{service.latency}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* AI Backbone */}
              <div className="bg-aura-surface-container-highest p-7 rounded-2xl flex flex-col justify-between">
                <div className="space-y-5">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-aura-primary/10 rounded-full flex items-center justify-center">
                      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                        <circle cx="9" cy="9" r="3" fill="#a03929"/>
                        <path d="M9 2v2M9 14v2M2 9h2M14 9h2M4.22 4.22l1.42 1.42M12.36 12.36l1.42 1.42M4.22 13.78l1.42-1.42M12.36 5.64l1.42-1.42" stroke="#a03929" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </div>
                    <h3 className="text-base font-headline font-bold text-aura-on-surface">AI Backbone</h3>
                  </div>
                  <div className="space-y-3">
                    <div className="p-4 bg-white/50 rounded-xl">
                      <p className="text-[10px] text-aura-on-surface-variant mb-1 font-body uppercase tracking-wider">Access Mode</p>
                      <p className="text-sm font-bold text-aura-on-surface capitalize">
                        {aiBackbone?.access_mode.replace(/_/g, " ") || "Loading…"}
                      </p>
                    </div>
                    <div className="p-4 bg-white/50 rounded-xl overflow-hidden">
                      <p className="text-[10px] text-aura-on-surface-variant mb-1 font-body uppercase tracking-wider">Workspace Endpoint</p>
                      <code className="text-xs font-mono text-aura-primary truncate block">
                        {aiBackbone?.workspace_default.api_url || "Not configured"}
                      </code>
                    </div>
                    <div className="p-4 bg-white/50 rounded-xl">
                      <p className="text-[10px] text-aura-on-surface-variant mb-1 font-body uppercase tracking-wider">Status</p>
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${aiBackbone?.effective_status.ready ? "bg-aura-tertiary" : "bg-aura-secondary animate-pulse"}`} />
                        <p className="text-xs text-aura-on-surface">
                          {aiBackbone?.effective_status.message || "Initializing…"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("memory")}
                  className="mt-6 w-full py-3 bg-aura-on-surface text-aura-surface rounded-full text-sm font-body hover:opacity-90 transition-all active:scale-95"
                >
                  Configure Backend
                </button>
              </div>

              {/* Quota Snapshot */}
              <div className="bg-aura-surface-container-low p-7 rounded-2xl space-y-5">
                <h3 className="text-base font-headline font-bold text-aura-on-surface">Quota Snapshot</h3>
                <div className="space-y-4">
                  {(systemSummary?.quota || []).length === 0 ? (
                    [
                      { name: "OpenAI", color: "bg-aura-primary", pct: 0 },
                      { name: "Anthropic", color: "bg-aura-secondary", pct: 0 },
                      { name: "Google TTS", color: "bg-aura-tertiary", pct: 0 },
                      { name: "fal.ai", color: "bg-aura-error", pct: 0 },
                      { name: "HeyGen", color: "bg-aura-primary-container", pct: 0 },
                    ].map(q => (
                      <div key={q.name} className="space-y-1">
                        <div className="flex justify-between text-xs font-body">
                          <span className="text-aura-on-surface">{q.name}</span>
                          <span className="text-aura-on-surface-variant">—</span>
                        </div>
                        <div className="h-1.5 w-full bg-aura-surface-container rounded-full overflow-hidden">
                          <div className={`h-full ${q.color} animate-pulse`} style={{ width: "20%" }} />
                        </div>
                      </div>
                    ))
                  ) : (
                    (systemSummary?.quota || []).map(q => {
                      const pct = q.total > 0 ? Math.min((q.used / q.total) * 100, 100) : 0;
                      const isHigh = pct >= 80;
                      const isCritical = pct >= 95;
                      const barColor = isCritical ? "bg-aura-error" : isHigh ? "bg-aura-secondary" : "bg-aura-primary";
                      return (
                        <div key={q.name} className="space-y-1">
                          <div className="flex justify-between text-xs font-body">
                            <span className="text-aura-on-surface flex items-center gap-1.5">
                              {q.name}
                              {isHigh && (
                                <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${
                                  isCritical ? "bg-aura-error/20 text-aura-error" : "bg-aura-secondary/20 text-aura-secondary"
                                }`}>
                                  {isCritical ? "⚠ Critical" : "⚠ High"}
                                </span>
                              )}
                            </span>
                            <span className={`font-bold ${isCritical ? "text-aura-error" : isHigh ? "text-aura-secondary" : "text-aura-on-surface-variant"}`}>
                              {Math.round(pct)}%
                            </span>
                          </div>
                          <div className="h-1.5 w-full bg-aura-surface-container rounded-full overflow-hidden">
                            <div className={`h-full ${barColor} transition-all duration-700 rounded-full`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </section>

            {/* ── Persona Showcase + Action ── */}
            <section className="grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
              {/* Persona visual */}
              <div className="md:col-span-7 bg-white p-1 rounded-2xl shadow-aura overflow-hidden relative group">
                <div className="aspect-[16/9] w-full relative overflow-hidden rounded-xl bg-aura-surface-container-high flex items-end">
                  {personas.length > 0 && personas[0].avatar_image_url ? (
                    <img
                      src={personas[0].avatar_image_url}
                      alt={personas[0].display_name}
                      className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                    />
                  ) : (
                    <div className="absolute inset-0 bg-gradient-to-br from-aura-primary/20 to-aura-primary-container/30 flex items-center justify-center">
                      <div className="text-6xl font-headline font-extrabold text-aura-primary/20">
                        {personas[0]?.display_name?.charAt(0) || "A"}
                      </div>
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent flex items-end p-8">
                    <div className="backdrop-blur-sm bg-white/10 p-5 rounded-xl border border-white/20">
                      <h4 className="text-white text-xl font-bold font-headline mb-1">
                        {personas[0]?.display_name || "Persona Alpha: Genesis"}
                      </h4>
                      <p className="text-white/80 text-sm font-body">
                        {personas[0]?.status === "active" ? "Active · Ready for deployment." : "Configure your first persona to get started."}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action panel */}
              <div className="md:col-span-5 space-y-6">
                <h3 className="text-3xl font-headline font-extrabold text-aura-on-surface leading-tight">
                  Craft Your Next Digital Influence.
                </h3>
                <p className="text-aura-on-surface-variant font-body text-base leading-relaxed">
                  Every great persona starts with a spark. Our AI backbone provides the infrastructure; you provide the soul. Monitor health, manage quotas, and watch your influence grow.
                </p>

                {/* Pending approvals inline */}
                {approvals.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-bold text-aura-on-surface-variant uppercase tracking-widest">Pending Approvals</p>
                    {approvals.slice(0, 3).map(a => (
                      <div key={a.id} className="p-3 bg-aura-secondary-container/30 border border-aura-secondary/20 rounded-xl flex items-center justify-between">
                        <span className="text-sm font-medium text-aura-on-surface truncate mr-2">{a.name}</span>
                        <div className="flex gap-2 flex-shrink-0">
                          <button
                            onClick={() => handleApprove(a.id, true)}
                            disabled={busyKey === `approve-${a.id}`}
                            className="text-[10px] px-3 py-1.5 bg-aura-tertiary text-white rounded-full font-bold hover:opacity-90 active:scale-95 disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleApprove(a.id, false)}
                            disabled={busyKey === `approve-${a.id}`}
                            className="text-[10px] px-3 py-1.5 bg-aura-error/20 text-aura-error rounded-full font-bold hover:bg-aura-error/30 active:scale-95 disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex gap-4">
                  <button
                    type="button"
                    onClick={() => void handleCreateThread()}
                    disabled={busyKey === "thread"}
                    className="bg-aura-primary text-aura-on-primary px-7 py-3.5 rounded-full font-body font-bold shadow-aura-md hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
                  >
                    Launch Studio
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab("live_feed")}
                    className="bg-aura-secondary-container text-aura-on-secondary-container px-7 py-3.5 rounded-full font-body font-bold hover:scale-105 active:scale-95 transition-all"
                  >
                    View Logs
                  </button>
                </div>
              </div>
            </section>

            {/* ── Campaign Control + Output Stream ── */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-2xl p-7 shadow-aura">
                <h3 className="text-base font-headline font-bold text-aura-on-surface mb-5">Campaign Control</h3>
                <div className="space-y-3">
                  {campaigns.map(c => (
                    <div key={c.id} className="p-4 bg-aura-surface-container-low border border-aura-outline-variant/20 rounded-xl flex items-center justify-between">
                      <div className="min-w-0 mr-3">
                        <h4 className="font-semibold text-aura-on-surface text-sm truncate">{c.name}</h4>
                        <p className="text-[10px] text-aura-on-surface-variant mt-0.5 uppercase tracking-wider">{c.status} · {c.approval_status}</p>
                      </div>
                      <button
                        onClick={() => handleLaunch(c.id)}
                        disabled={c.approval_status !== "approved" || busyKey === `launch-${c.id}`}
                        className="flex-shrink-0 text-[10px] px-4 py-2 bg-aura-tertiary text-white rounded-full font-bold hover:opacity-90 active:scale-95 disabled:opacity-40 transition-all"
                      >
                        {busyKey === `launch-${c.id}` ? "…" : "Launch"}
                      </button>
                    </div>
                  ))}
                  {campaigns.length === 0 && (
                    <p className="text-sm text-aura-outline italic text-center py-4">Queue clear.</p>
                  )}
                </div>
              </div>

              <div className="bg-white rounded-2xl p-7 shadow-aura">
                <h3 className="text-base font-headline font-bold text-aura-on-surface mb-5">Output Stream</h3>
                <div className="space-y-2">
                  {content.slice(0, 6).map(item => (
                    <div key={item.id} className="p-3 bg-aura-surface-container-low border border-aura-outline-variant/15 rounded-xl flex justify-between items-center">
                      <span className="text-sm text-aura-on-surface truncate mr-2">{item.title}</span>
                      <span className={`flex-shrink-0 text-[10px] px-2.5 py-1 rounded-full font-bold ${
                        item.status === "published"
                          ? "bg-aura-tertiary-container/50 text-aura-tertiary"
                          : item.status === "scheduled"
                          ? "bg-aura-secondary-container/50 text-aura-secondary"
                          : "bg-aura-surface-container text-aura-on-surface-variant"
                      }`}>
                        {item.status}
                      </span>
                    </div>
                  ))}
                  {content.length === 0 && (
                    <p className="text-sm text-aura-outline italic text-center py-4">No content yet.</p>
                  )}
                </div>
              </div>
            </section>

          </div>
        )}

        {isVideoContextModalOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                setIsVideoContextModalOpen(false);
              }
            }}
          >
            <div
              className="w-full max-w-3xl rounded-2xl border border-white/[0.08] bg-zinc-950/95 p-6 shadow-2xl shadow-black/40 backdrop-blur-xl"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4 pb-4 border-b border-white/[0.08]">
                <div>
                  <h2 className="text-xl font-semibold text-white">Video Creation Context</h2>
                  <p className="text-sm text-zinc-400 mt-1">Fill in the AI video brief and save it for later generation.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsVideoContextModalOpen(false)}
                  className="rounded-full border border-white/[0.08] bg-white/5 px-3 py-2 text-sm text-white transition-all duration-200 hover:bg-white/10"
                >
                  Close
                </button>
              </div>
              <div className="max-h-[calc(100vh-10rem)] overflow-y-auto overflow-x-visible pr-2 pt-4 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                <form className="space-y-4" onSubmit={(event) => {
                  handleVideoContextSave(event);
                  setIsVideoContextModalOpen(false);
                }}>
                  <FormField
                    label="Video Title"
                    value={videoContextDraft.title}
                    onChange={(event) => setVideoContextDraft((current) => ({ ...current, title: (event.target as HTMLInputElement).value }))}
                    placeholder="Short, descriptive title"
                  />
                  <TextAreaField
                    label="Video Description"
                    value={videoContextDraft.description}
                    onChange={(event) => setVideoContextDraft((current) => ({ ...current, description: (event.target as HTMLTextAreaElement).value }))}
                    placeholder="What should this video communicate?"
                    minHeight="100px"
                  />
                  <TextAreaField
                    label="Target Audience"
                    value={videoContextDraft.targetAudience}
                    onChange={(event) => setVideoContextDraft((current) => ({ ...current, targetAudience: (event.target as HTMLTextAreaElement).value }))}
                    placeholder="Who is this for?"
                    minHeight="80px"
                  />
                  <FormField
                    label="Call To Action"
                    value={videoContextDraft.callToAction}
                    onChange={(event) => setVideoContextDraft((current) => ({ ...current, callToAction: (event.target as HTMLInputElement).value }))}
                    placeholder="What should viewers do next?"
                  />
                  <div className="grid gap-4 md:grid-cols-2">
                    <SelectField
                      label="Duration"
                      value={videoContextDraft.duration}
                      onChange={(event) => setVideoContextDraft((current) => ({ ...current, duration: (event.target as HTMLSelectElement).value }))}
                      options={VIDEO_DURATION_OPTIONS.map((option) => ({
                        value: option.value,
                        label: option.label,
                      }))}
                    />
                    <SelectField
                      label="Video Style"
                      value={videoContextDraft.style}
                      onChange={(event) => setVideoContextDraft((current) => ({ ...current, style: (event.target as HTMLSelectElement).value }))}
                      options={VIDEO_STYLE_OPTIONS.map((option) => ({
                        value: option.value,
                        label: option.label,
                      }))}
                    />
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <SelectField
                      label="Tone"
                      value={videoContextDraft.tone}
                      onChange={(event) => setVideoContextDraft((current) => ({ ...current, tone: (event.target as HTMLSelectElement).value }))}
                      options={VIDEO_TONE_OPTIONS.map((option) => ({
                        value: option.value,
                        label: option.label,
                      }))}
                    />
                    <FormField
                      label="Persona"
                      value={videoContextDraft.personaId}
                      onChange={(event) => setVideoContextDraft((current) => ({ ...current, personaId: (event.target as HTMLInputElement).value }))}
                      placeholder="Choose or type persona ID"
                    />
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <SelectField
                      label="Target Platforms"
                      value={videoContextDraft.platforms}
                      onChange={(event) => setVideoContextDraft((current) => ({ ...current, platforms: (event.target as HTMLSelectElement).value }))}
                      options={VIDEO_PLATFORM_OPTIONS.map((option) => ({
                        value: option.value,
                        label: option.label,
                      }))}
                    />
                    <FormField
                      label="Language"
                      value={videoContextDraft.language}
                      onChange={(event) => setVideoContextDraft((current) => ({ ...current, language: (event.target as HTMLInputElement).value }))}
                      placeholder="Language for narration/captions"
                    />
                  </div>
                  <TextAreaField
                    label="Key Messages"
                    value={videoContextDraft.keyMessages}
                    onChange={(event) => setVideoContextDraft((current) => ({ ...current, keyMessages: (event.target as HTMLTextAreaElement).value }))}
                    placeholder="List the most important messages or bullet points."
                    minHeight="80px"
                  />
                  <div className="flex items-center gap-3">
                    <input
                      id="video-subtitles"
                      type="checkbox"
                      checked={videoContextDraft.subtitles}
                      onChange={(event) => setVideoContextDraft((current) => ({ ...current, subtitles: event.target.checked }))}
                      className="h-4 w-4 rounded border-white/10 bg-white/5 text-blue-500 focus:ring-blue-500"
                    />
                    <label htmlFor="video-subtitles" className="text-sm text-zinc-400">
                      Generate subtitles automatically
                    </label>
                  </div>
                  <button type="submit" className="w-full bg-blue-500 text-white font-semibold py-2.5 rounded-lg shadow-lg shadow-blue-500/20 transition-all duration-200 ease-out hover:bg-blue-400 hover:shadow-blue-500/30 active:scale-[0.98]">
                    Save Video Context
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}

        {activeTab === "skills" && (
          <div className="space-y-10 animate-fade-in">

            {/* Page header */}
            <header className="flex justify-between items-end">
              <div>
                <h1 className="text-4xl font-extrabold text-aura-on-surface font-headline tracking-tight mb-2">Quản lý AI Personas</h1>
                <p className="text-aura-on-surface-variant max-w-xl text-sm font-body">
                  Tùy chỉnh và điều phối các nhân vật ảo liên kết với tài khoản của bạn để tối ưu sức ảnh hưởng.
                </p>
              </div>
              {telegramBotUrl && (
                <a
                  href={telegramBotUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="hidden sm:flex items-center gap-2 bg-gradient-to-br from-aura-primary to-aura-primary-container text-aura-on-primary px-7 py-3 rounded-full font-bold shadow-aura-md hover:scale-105 active:scale-95 transition-all text-sm"
                >
                  <span>+</span> Tạo Persona mới
                </a>
              )}
            </header>

            {/* Persona bento grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
              {personas.map(p => {
                const isActive = p.status === "active";
                return (
                  <div
                    key={p.persona_id}
                    className="group relative overflow-hidden rounded-2xl bg-white shadow-aura transition-all duration-300 hover:-translate-y-2 hover:shadow-aura-md"
                  >
                    {/* Photo area */}
                    <div className="aspect-[4/5] overflow-hidden bg-aura-surface-container-high">
                      {p.avatar_image_url ? (
                        <img
                          src={p.avatar_image_url}
                          alt={p.display_name}
                          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-aura-primary/10 to-aura-primary-container/20">
                          <span className="text-7xl font-extrabold font-headline text-aura-primary/20">
                            {p.display_name.charAt(0).toUpperCase()}
                          </span>
                        </div>
                      )}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-60" />
                    </div>

                    {/* Glass info panel */}
                    <div className="absolute bottom-0 left-0 right-0 m-4 p-5 rounded-xl" style={{ background: "rgba(248,246,241,0.75)", backdropFilter: "blur(24px)" }}>
                      <div className="flex justify-between items-start mb-2">
                        <div className="min-w-0 mr-2">
                          <h3 className="text-lg font-bold font-headline text-aura-on-surface truncate">{p.display_name}</h3>
                          <p className="text-[10px] font-bold text-aura-primary uppercase tracking-widest mt-0.5">
                            {p.video_count} videos
                          </p>
                        </div>
                        <span className={`flex-shrink-0 px-2 py-1 rounded text-[10px] font-bold ${
                          isActive
                            ? "bg-aura-tertiary-container text-aura-on-tertiary-container"
                            : "bg-aura-surface-container-high text-aura-on-surface-variant"
                        }`}>
                          {isActive ? "ĐANG HOẠT ĐỘNG" : "BẢN NHÁP"}
                        </span>
                      </div>

                      <div className="flex gap-4 mb-4 text-xs text-aura-on-surface-variant">
                        <span className="flex items-center gap-1">
                          <span className="text-base">👥</span>
                          {isActive ? `${p.video_count * 12}k` : "--"}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="text-base">♥</span>
                          {isActive ? "4.2%" : "--"}
                        </span>
                      </div>

                      {telegramBotUrl ? (
                        <a
                          href={telegramBotUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="w-full py-2 bg-aura-surface-container text-aura-on-surface font-bold rounded-full text-sm hover:bg-aura-primary hover:text-white transition-colors flex items-center justify-center gap-2"
                        >
                          <span className="text-base">💬</span>
                          {isActive ? "Mở Bot hội thoại" : "Tiếp tục thiết lập"}
                        </a>
                      ) : (
                        <button
                          type="button"
                          className="w-full py-2 bg-aura-surface-container text-aura-on-surface font-bold rounded-full text-sm hover:bg-aura-primary hover:text-white transition-colors"
                        >
                          {isActive ? "Xem chi tiết" : "Tiếp tục thiết lập"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Add new card */}
              <div className="group relative overflow-hidden rounded-2xl border-2 border-dashed border-aura-outline-variant/40 flex flex-col items-center justify-center p-12 text-center hover:border-aura-primary/50 transition-colors cursor-pointer min-h-[400px]">
                <div className="w-16 h-16 rounded-full bg-aura-surface-container-high flex items-center justify-center mb-4 group-hover:bg-aura-primary-container/50 transition-colors">
                  <span className="text-3xl text-aura-primary">+</span>
                </div>
                <h3 className="text-lg font-bold text-aura-on-surface mb-2">Tạo Nhân Vật Mới</h3>
                <p className="text-sm text-aura-on-surface-variant mb-6">
                  Ra mắt một AI cá tính hoàn toàn mới để mở rộng phạm vi tiếp cận.
                </p>
                {telegramBotUrl ? (
                  <a
                    href={telegramBotUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="px-6 py-2 bg-aura-surface-container-high text-aura-on-surface font-bold rounded-full text-sm hover:bg-aura-primary hover:text-white transition-all"
                  >
                    Bắt đầu tạo
                  </a>
                ) : (
                  <button
                    type="button"
                    className="px-6 py-2 bg-aura-surface-container-high text-aura-on-surface font-bold rounded-full text-sm hover:bg-aura-primary hover:text-white transition-all"
                  >
                    Bắt đầu tạo
                  </button>
                )}
              </div>
            </div>

            {/* Management section */}
            <section className="bg-aura-surface-container-low rounded-2xl p-8">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-2xl font-bold text-aura-on-surface font-headline">Cài đặt Vận hành Chung</h2>
                <button type="button" className="text-aura-primary font-bold text-sm hover:underline underline-offset-4">Quản lý tất cả</button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                  {
                    icon: "✨",
                    title: "Tự động hóa nội dung",
                    desc: "Lên lịch đăng bài tự động cho tất cả các persona đang hoạt động.",
                    badge: null,
                    toggle: true,
                  },
                  {
                    icon: "🌐",
                    title: "Đa ngôn ngữ",
                    desc: "Tự động dịch thuật để tiếp cận khán giả quốc tế.",
                    badge: { text: "12 Ngôn ngữ đã kích hoạt", color: "text-aura-primary" },
                    toggle: false,
                  },
                  {
                    icon: "✅",
                    title: "Bộ lọc an toàn",
                    desc: "Giám sát phản hồi AI nghiêm ngặt để bảo vệ thương hiệu.",
                    badge: { text: "Cấp độ Doanh nghiệp", color: "text-aura-tertiary" },
                    toggle: false,
                  },
                ].map(item => (
                  <div key={item.title} className="bg-white p-6 rounded-xl shadow-aura-sm">
                    <span className="text-2xl mb-3 block">{item.icon}</span>
                    <h4 className="font-bold text-aura-on-surface mb-1 text-sm">{item.title}</h4>
                    <p className="text-xs text-aura-on-surface-variant">{item.desc}</p>
                    {item.toggle && (
                      <div className="mt-4 flex items-center gap-2">
                        <div className="w-8 h-4 bg-aura-primary rounded-full relative">
                          <div className="w-3 h-3 bg-white rounded-full absolute right-0.5 top-0.5" />
                        </div>
                        <span className="text-[10px] font-bold text-aura-on-surface-variant uppercase">BẬT</span>
                      </div>
                    )}
                    {item.badge && (
                      <p className={`mt-4 text-xs font-bold ${item.badge.color}`}>{item.badge.text}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>

          </div>
        )}

        {activeTab === "memory" && (
          <div className="space-y-10 animate-fade-in">

            {/* Page header */}
            <header>
              <h1 className="text-4xl font-extrabold text-aura-on-surface font-headline tracking-tight mb-2">Dự án &amp; Memory</h1>
              <p className="text-aura-on-surface-variant max-w-2xl text-sm font-body">
                Xác định bản sắc cốt lõi của thương hiệu kỹ thuật số. Các thông số này định hình cách AI học hỏi, ghi nhớ và giao tiếp trên mọi kênh.
              </p>
            </header>

            {/* Bento grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

              {/* ── Left: Brand Context (8 col) ── */}
              <section className="lg:col-span-8 space-y-8">

                {/* Brand Context card */}
                <div className="bg-white rounded-2xl p-8 shadow-aura">
                  <div className="flex items-center gap-3 mb-8">
                    <div className="w-12 h-12 rounded-2xl bg-aura-primary/10 flex items-center justify-center">
                      <span className="text-xl">📖</span>
                    </div>
                    <h3 className="text-xl font-bold text-aura-on-surface font-headline">Bối cảnh Thương hiệu</h3>
                  </div>

                  <form className="space-y-6" onSubmit={handleBrandSave}>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="block text-sm font-semibold text-aura-on-surface-variant px-1">Tên Thương hiệu</label>
                        <input
                          type="text"
                          value={brandForm.product_name || ""}
                          onChange={e => setBrandForm(c => ({ ...c, product_name: e.target.value }))}
                          placeholder="Nhập tên thương hiệu..."
                          className="w-full bg-aura-surface-container border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-aura-primary/20 text-aura-on-surface font-body font-medium transition-all outline-none"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="block text-sm font-semibold text-aura-on-surface-variant px-1">Đối tượng Mục tiêu</label>
                        <input
                          type="text"
                          value={brandForm.audience || ""}
                          onChange={e => setBrandForm(c => ({ ...c, audience: e.target.value }))}
                          placeholder="Mô tả đối tượng mục tiêu..."
                          className="w-full bg-aura-surface-container border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-aura-primary/20 text-aura-on-surface font-body font-medium transition-all outline-none"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <label className="block text-sm font-semibold text-aura-on-surface-variant px-1">Tóm tắt Giá trị</label>
                      <textarea
                        value={brandForm.offer_summary || ""}
                        onChange={e => setBrandForm(c => ({ ...c, offer_summary: e.target.value }))}
                        placeholder="Tóm tắt về sản phẩm hoặc dịch vụ của bạn..."
                        rows={4}
                        className="w-full bg-aura-surface-container border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-aura-primary/20 text-aura-on-surface font-body font-medium transition-all resize-none outline-none"
                      />
                    </div>

                    <div className="flex justify-end">
                      <button
                        type="submit"
                        disabled={busyKey === "brand-save"}
                        className="px-10 py-3.5 bg-aura-primary text-aura-on-primary font-bold rounded-full hover:opacity-90 transition-all shadow-aura-md active:scale-95 disabled:opacity-50"
                      >
                        {busyKey === "brand-save" ? "Đang lưu…" : "Lưu Bối cảnh"}
                      </button>
                    </div>
                  </form>
                </div>

                {/* Intelligence Mode + System Bridge */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                  {/* Intelligence Mode */}
                  <div className="bg-white rounded-2xl p-8 shadow-aura flex flex-col justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 rounded-xl bg-aura-tertiary/10 flex items-center justify-center">
                          <span className="text-lg">🧠</span>
                        </div>
                        <h3 className="font-bold text-aura-on-surface font-headline">Chế độ Trí tuệ</h3>
                      </div>
                      <p className="text-sm text-aura-on-surface-variant mb-6 leading-relaxed font-body">
                        Xác định cách AI truy cập và sử dụng kho lưu trữ bộ nhớ trong các cuộc hội thoại.
                      </p>
                    </div>
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center justify-between w-full p-5 bg-aura-surface-container-lowest rounded-2xl border-2 border-aura-primary shadow-aura-sm">
                        <span className="font-bold text-aura-on-surface text-sm">
                          {aiBackbone?.access_mode.replace(/_/g, " ") || "Platform Managed"}
                        </span>
                        <span className="text-aura-tertiary text-lg">✓</span>
                      </div>
                      <div className="flex items-center justify-between w-full p-5 bg-aura-surface-container-low rounded-2xl border-2 border-transparent">
                        <span className="font-medium text-aura-on-surface-variant text-sm">
                          {aiBackbone?.effective_status.message || "Initializing…"}
                        </span>
                        <span className={`w-2 h-2 rounded-full ${aiBackbone?.effective_status.ready ? "bg-aura-tertiary" : "bg-aura-secondary animate-pulse"}`} />
                      </div>
                    </div>
                  </div>

                  {/* System Bridge — Telegram */}
                  <div className="bg-white rounded-2xl p-8 shadow-aura flex flex-col justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 rounded-xl bg-aura-secondary/10 flex items-center justify-center">
                          <span className="text-lg">🔗</span>
                        </div>
                        <h3 className="font-bold text-aura-on-surface font-headline">Cầu nối Hệ thống</h3>
                      </div>
                      <p className="text-sm text-aura-on-surface-variant mb-6 leading-relaxed font-body">
                        Cho phép điều khiển và giám sát trực tiếp thông qua các giao thức tin nhắn bảo mật.
                      </p>
                    </div>

                    {telegramLink?.linked ? (
                      <div className="p-5 bg-blue-50 rounded-2xl flex items-center gap-4">
                        <div className="w-10 h-10 bg-[#0088cc] text-white rounded-full flex items-center justify-center text-lg flex-shrink-0">✈</div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-bold text-aura-on-surface">@{telegramLink.link?.telegram_username || "Linked Account"}</p>
                          <p className="text-[10px] text-aura-on-surface-variant">ID: {telegramLink.link?.chat_id}</p>
                          <p className="text-[10px] text-aura-tertiary font-bold uppercase tracking-wide mt-0.5">Đã kết nối</p>
                        </div>
                        <button
                          type="button"
                          onClick={handleStartTelegramLink}
                          className="text-aura-on-surface-variant hover:text-aura-primary transition-colors text-sm"
                        >↻</button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <button
                          type="button"
                          onClick={handleStartTelegramLink}
                          disabled={busyKey === "telegram-link"}
                          className="w-full py-3 bg-[#0088cc] text-white font-bold rounded-full hover:opacity-90 active:scale-95 transition-all disabled:opacity-50"
                        >
                          {busyKey === "telegram-link" ? "Đang tạo liên kết…" : "Kết nối Telegram"}
                        </button>
                        {linkToken && telegramVerificationUrl && (
                          <div className="p-4 bg-aura-secondary-container/30 border border-aura-secondary/20 rounded-xl text-center">
                            <p className="text-xs text-aura-secondary mb-3 font-medium">
                              {isPollingTelegramLink ? "Chờ xác nhận Telegram…" : "Liên kết sẵn sàng. Xác nhận trên Telegram."}
                            </p>
                            <a
                              href={telegramVerificationUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-block px-6 py-2 bg-aura-secondary text-aura-on-secondary rounded-full font-bold text-xs hover:opacity-90 active:scale-95 transition-all"
                            >
                              Xác nhận ngay
                            </a>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </section>

              {/* ── Right: Social Grid + Persona visual (4 col) ── */}
              <aside className="lg:col-span-4 space-y-8">

                {/* Social Grid */}
                <div className="bg-aura-surface-container-high rounded-2xl p-8">
                  <h3 className="text-lg font-bold font-headline text-aura-on-surface mb-2">Mạng lưới Xã hội</h3>
                  <p className="text-xs text-aura-on-surface-variant mb-8 font-body">
                    Bật/tắt các mục tiêu đăng bài tự động cho chu kỳ nội dung được tối ưu bởi bộ nhớ.
                  </p>

                  <div className="grid grid-cols-2 gap-4">
                    {SUPPORTED_PLATFORMS.map(p => {
                      const acc = accounts.find(a => a.platform === p);
                      const platformIcons: Record<string, { emoji: string; color: string; bg: string }> = {
                        linkedin:  { emoji: "🔷", color: "text-blue-600",  bg: "bg-blue-50"  },
                        twitter:   { emoji: "🐦", color: "text-stone-900", bg: "bg-stone-100" },
                        x:         { emoji: "✖",  color: "text-stone-900", bg: "bg-stone-100" },
                        youtube:   { emoji: "▶",  color: "text-red-600",   bg: "bg-red-50"   },
                        instagram: { emoji: "📸", color: "text-pink-600",  bg: "bg-pink-50"  },
                        tiktok:    { emoji: "🎵", color: "text-stone-900", bg: "bg-stone-100" },
                        facebook:  { emoji: "📘", color: "text-blue-700",  bg: "bg-blue-50"  },
                      };
                      const meta = platformIcons[p.toLowerCase()] ?? { emoji: "🌐", color: "text-aura-primary", bg: "bg-aura-surface-container" };
                      return (
                        <div
                          key={p}
                          className="bg-white/60 backdrop-blur p-4 rounded-3xl flex flex-col items-center justify-center gap-3 hover:bg-white cursor-pointer group shadow-aura-sm transition-all"
                        >
                          <div className={`w-12 h-12 ${meta.bg} ${meta.color} rounded-full flex items-center justify-center group-hover:scale-110 transition-transform text-xl`}>
                            {meta.emoji}
                          </div>
                          <span className="text-xs font-bold text-aura-on-surface capitalize">{p}</span>
                          {acc ? (
                            <div className="w-10 h-5 bg-aura-primary rounded-full relative">
                              <div className="absolute right-1 top-1 w-3 h-3 bg-white rounded-full" />
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleConnect(p)}
                              className="w-10 h-5 bg-aura-surface-container-high rounded-full relative hover:bg-aura-primary/30 transition-colors"
                            >
                              <div className="absolute left-1 top-1 w-3 h-3 bg-white rounded-full" />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Memory capacity bar */}
                  <div className="mt-8 pt-8 border-t border-aura-outline-variant/20">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-bold text-aura-on-surface-variant">Khả năng Ghi nhớ</span>
                      <span className="text-xs font-bold text-aura-primary">84%</span>
                    </div>
                    <div className="w-full bg-aura-surface-container-lowest h-2 rounded-full overflow-hidden">
                      <div className="bg-gradient-to-r from-aura-primary to-aura-primary-container h-full w-[84%] rounded-full" />
                    </div>
                    <p className="text-[10px] text-aura-on-surface-variant mt-4 leading-relaxed italic font-body">
                      Tỷ lệ lưu giữ cao hơn cho phép AI nhớ lại các sở thích thương hiệu sắc thái từ các tương tác trước đó chính xác hơn.
                    </p>
                  </div>
                </div>

                {/* Persona visual card */}
                {personas.length > 0 && (
                  <div className="relative group cursor-pointer">
                    <div className="aspect-[4/5] rounded-2xl overflow-hidden shadow-aura-md transition-transform group-hover:scale-[1.02] duration-300 bg-aura-surface-container-high">
                      {personas[0]?.avatar_image_url ? (
                        <img
                          src={personas[0].avatar_image_url}
                          alt={personas[0].display_name}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full bg-gradient-to-br from-aura-primary/20 to-aura-primary-container/30 flex items-center justify-center">
                          <span className="text-8xl font-extrabold text-aura-primary/20 font-headline">
                            {personas[0]?.display_name?.charAt(0) || "A"}
                          </span>
                        </div>
                      )}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                      <div className="absolute bottom-0 left-0 right-0 p-6" style={{ backdropFilter: "blur(12px)", background: "rgba(255,255,255,0.08)", borderTop: "1px solid rgba(255,255,255,0.15)" }}>
                        <h4 className="text-white font-bold text-xl font-headline">{personas[0]?.display_name}</h4>
                        <p className="text-white/70 text-xs font-body mt-0.5">Persona đang hoạt động</p>
                        <div className="mt-4 flex items-center gap-2">
                          <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                          <span className="text-[10px] text-white/90 font-body font-medium uppercase tracking-widest">
                            {personas[0]?.status === "active" ? "Đã tối ưu & Đồng bộ" : "Chờ kích hoạt"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

              </aside>
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
                  <p className="text-xs font-semibold uppercase tracking-widest text-aura-on-surface-variant">
                    Runtime Workflows
                  </p>
                  {systemWorkflows.length === 0 && (
                    <p className="text-sm text-aura-on-surface-variant">No active workflow telemetry right now.</p>
                  )}
                  {systemWorkflows.map((workflow) => (
                    <div
                      key={workflow.id}
                      className="rounded-[16px] border border-aura-outline-variant/30 bg-aura-surface-container-low p-4"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="font-medium text-aura-on-surface">{workflow.name}</p>
                          <p className="text-xs uppercase tracking-widest text-aura-on-surface-variant">
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
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-aura-surface-container-highest">
                        <div
                          className="h-full rounded-full bg-emerald-400 shadow-aura-sm"
                          style={{ width: `${Math.max(0, Math.min(workflow.progress, 100))}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-widest text-aura-on-surface-variant">
                    Recent Output
                  </p>
                  {content.slice(0, 5).map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-4 rounded-[16px] border border-aura-outline-variant/30 bg-aura-surface-container-high p-4"
                    >
                      <div>
                        <p className="font-medium text-aura-on-surface">{item.title}</p>
                        <p className="text-xs uppercase tracking-widest text-aura-on-surface-variant">
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
    return <p className="text-sm text-aura-on-surface-variant">{emptyMessage}</p>;
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
        className="w-full rounded-[14px] border border-aura-outline-variant bg-aura-surface-container-high px-4 py-3 text-sm text-aura-on-surface placeholder:text-aura-outline transition-colors focus:border-aura-primary focus:ring-1 focus:ring-aura-primary"
      />
    </label>
  );
}

function StatusBadge({ label }: { label: string }) {
  const normalizedLabel = label.toLowerCase().replaceAll("_", " ");
  
  // Determine badge style based on status
  const isSuccess = ["connected", "online", "completed", "approved", "published", "linked"].some(
    keyword => normalizedLabel.includes(keyword)
  );
  const isWarning = ["pending", "waiting", "scheduled"].some(
    keyword => normalizedLabel.includes(keyword)
  );
  const isError = ["error", "failed", "rejected", "disconnected"].some(
    keyword => normalizedLabel.includes(keyword)
  );
  
  let badgeClasses = "bg-aura-surface-container-highest text-aura-on-surface-variant border-aura-outline-variant/30";
  if (isSuccess) {
    badgeClasses = "bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-400 dark:border-emerald-500/20";
  } else if (isWarning) {
    badgeClasses = "bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-500/15 dark:text-amber-400 dark:border-amber-500/20";
  } else if (isError) {
    badgeClasses = "bg-rose-50 text-rose-600 border-rose-200 dark:bg-rose-500/15 dark:text-rose-400 dark:border-rose-500/20";
  }
  
  return (
    <span className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-widest ${badgeClasses}`}>
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

  (systemWorkflows || []).slice(0, 3).forEach((workflow) => {
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

  (approvals || []).slice(0, 2).forEach((approval) => {
    items.push({
      id: `approval-${approval.id}`,
      title: `Approval pending: ${approval.name}`,
      detail: `${approval.target_platforms.join(", ") || "No platform"} • ${approval.approval_status}`,
      tone: "warning",
    });
  });

  (content || []).slice(0, 3).forEach((item) => {
    items.push({
      id: `content-${item.id}`,
      title: `Content: ${item.title}`,
      detail: `${item.platform.join(", ") || "No platform"} • ${describeContentTiming(item)}`,
      tone: item.status === "published" ? "success" : "default",
    });
  });

  (campaigns || []).slice(0, 2).forEach((campaign) => {
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

function auraActivityDotClass(tone: ActivityItemTone = "default"): string {
  if (tone === "success") return "bg-aura-tertiary";
  if (tone === "warning") return "bg-aura-secondary";
  return "bg-aura-primary-container";
}
