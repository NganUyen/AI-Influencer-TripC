"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Bot,
  Database,
  LayoutDashboard,
  Radio,
  Users,
  Check,
  Cpu,
  BookOpen,
  Brain,
  Link2,
  RefreshCw,
  X,
  AlertCircle,
  Video,
  Send,
  type LucideIcon,
} from "lucide-react";
import { SocialIcon } from "@/components/ui/SocialIcon";

import { customerApiRequest } from "@/lib/customer-api";
import { getClientTelegramBotLaunchUrl } from "@/lib/public-env";
import { useCustomerAuthStore } from "@/store/customer-auth-store";
import { DashboardHeader } from "@/components/DashboardHeader";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import openClawLogo from "@/app/dashboard/openclaw-logo.svg";
import { FormField } from "@/components/ui/FormField";
import { SelectField } from "@/components/ui/SelectField";
import { TextAreaField } from "@/components/ui/TextAreaField";
import {
  type ReviewEngineJob,
  type ReviewEngineJobResponse,
  type ReviewEngineSetup,
  getReviewJobPersonaImage,
  getReviewJobStatusLabel,
  getReviewJobTone,
} from "@/lib/review-engine";

import { OverviewTab } from "./dashboard/OverviewTab";
import { PersonasTab } from "./dashboard/PersonasTab";
import { LiveFeedTab } from "./dashboard/LiveFeedTab";
import { PublishingTab } from "./dashboard/PublishingTab";


export type BrandProfile = {
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

export type SocialAccount = {
  id: string;
  platform: string;
  account_handle: string | null;
  display_name: string | null;
  connection_status: string;
};

export type AssistantThread = {
  id: string;
  title: string;
  created_at: string;
  last_message_preview: string | null;
};

export type AssistantMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type AssistantArtifact = {
  id: string;
  title: string;
  type: string;
  payload: any;
  created_at: string;
};

export type Campaign = {
  id: string;
  name: string;
  description: string | null;
  target_platforms: string[];
  status: string;
  approval_status: string;
  active_workflow_id: string | null;
};

export type ContentItem = {
  id: string;
  title: string;
  platform: string[];
  status: string;
  scheduled_at: string | null;
  published_at: string | null;
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

export type AIBackboneSettings = {
  access_mode: "platform_managed" | "customer_api_key" | "chatgpt_oauth";
  customer_api: {
    api_url: string | null;
    has_api_key: boolean;
  };
  platform_managed: {
    api_url: string;
    has_api_key?: boolean;
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

export type Persona = {
  persona_id: string;
  display_name: string;
  avatar_image_url: string | null;
  selection_image_url?: string | null;
  status: string;
  video_count: number;
  language?: string | null;
  tts_voice?: string | null;
  appearance_prompt_or_photo?: string | null;
  region_label?: string | null;
  description?: string | null;
  market_default?: string | null;
  tone_default?: string | null;
  is_preset_catalog?: boolean;
};

export type TelegramLinkStatus = {
  linked: boolean;
  link?: {
    telegram_username: string | null;
    chat_id: string;
  };
};

export type TelegramLinkToken = {
  start_token: string;
  expires_at: string;
};

export type SystemSummaryData = {
  services: { name: string; status: "online" | "warning" | "error"; latency: string }[];
  quota: { name: string; used: number; total: number; unit: string }[];
  telegram_bot_url?: string | null;
  recent_videos?: {
    asset_id: string;
    persona_id?: string | null;
    title?: string | null;
    access_url?: string | null;
    created_at?: string | null;
  }[];
};

export type SystemWorkflowData = {
  id: string;
  workflow_id?: string;
  name: string;
  status: string;
  progress: number;
  current_step?: string | null;
  channel?: string | null;
  approval_status?: string | null;
  updated_at?: string | null;
};

type CustomerWorkspaceResponse = {
  customer: {
    user_id: string;
    email: string;
    display_name: string | null;
  };
  brand: BrandProfile | null;
  social_accounts: SocialAccount[];
  assistant_threads: AssistantThread[];
  campaigns: Campaign[];
  approvals: Campaign[];
  approval_requests?: unknown[];
  content: ContentItem[];
  ai_backbone: AIBackboneSettings;
  personas: Persona[];
  telegram_link: TelegramLinkStatus | null;
  system_summary: SystemSummaryData | null;
  workflow_summary: {
    workflows: SystemWorkflowData[];
    status: string;
  };
};

export type DashboardTabId = "overview" | "ops" | "skills" | "memory" | "create_video" | "publishing";

export type DashboardTab = {
  id: DashboardTabId;
  label: string;
  icon: LucideIcon;
};

export type ActivityItemTone = "default" | "success" | "warning";

export type ActivityItem = {
  id: string;
  title: string;
  detail: string;
  tone?: ActivityItemTone;
  progress?: number;
  personaImage?: string | null;
  timeLabel?: string;
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
    value: "platform_managed",
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
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "ops", label: "AI Operations", icon: Bot },
  { id: "skills", label: "Personas", icon: Users },
  { id: "memory", label: "Project & Memory", icon: Database },
  { id: "create_video", label: "Create Video", icon: Video },
  { id: "publishing", label: "Publishing", icon: Send },
];

function buildAiBackboneForm(
  settings: AIBackboneSettings,
  defaultDisplayName: string,
) {
  return {
    accessMode: settings.access_mode,
    customerApiUrl:
      settings.customer_api.api_url || settings.platform_managed.api_url || "",
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

  const [activeTab, setActiveTab] = useState<DashboardTabId>("overview");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
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
        access_mode: "platform_managed",
        customer_api: { api_url: "", has_api_key: false },
        platform_managed: { api_url: "" },
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
  const [reviewEngineSetup, setReviewEngineSetup] = useState<ReviewEngineSetup | null>(null);
  const [reviewEngineJobs, setReviewEngineJobs] = useState<ReviewEngineJob[]>([]);

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

  const loadReviewEngineData = useCallback(async () => {
    if (typeof window === "undefined" || !isAuthenticated) {
      return;
    }

    try {
      const [setupPayload, jobsPayload] = await Promise.all([
        customerApiRequest<ReviewEngineSetup>("/api/customer/review-engine/setup"),
        customerApiRequest<ReviewEngineJobResponse>("/api/customer/review-engine/jobs"),
      ]);
      setReviewEngineSetup(setupPayload);
      setReviewEngineJobs(jobsPayload.jobs || []);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "";
      if (
        msg.includes("401") ||
        msg.includes("Unauthorized") ||
        msg.toLowerCase().includes("invalid or expired")
      ) {
        void logout();
        router.replace("/auth");
        return;
      }
      console.warn("Failed to refresh review engine data:", error);
    }
  }, [isAuthenticated, logout, router]);

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
    if (
      dashboardTabParam &&
      DASHBOARD_TABS.some((tab) => tab.id === dashboardTabParam)
    ) {
      setActiveTab(dashboardTabParam as DashboardTabId);
    }
  }, [dashboardTabParam]);

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
    void loadReviewEngineData();
  }, [initialized, isLoading, isAuthenticated, router, pageError, loadReviewEngineData]);

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
      const workspace = await customerApiRequest<CustomerWorkspaceResponse>(
        "/api/customer/workspace",
      );

      setBrandForm(workspace?.brand || EMPTY_BRAND);
      setAccounts(workspace?.social_accounts || []);
      setThreads(workspace?.assistant_threads || []);
      setCampaigns(workspace?.campaigns || []);
      setApprovals(workspace?.approvals || []);
      setContent(workspace?.content || []);
      setPersonas(workspace?.personas || []);
      setTelegramLink(workspace?.telegram_link || null);
      setSystemSummary(workspace?.system_summary || null);
      setSystemWorkflows(workspace?.workflow_summary?.workflows || []);

      const settings = workspace?.ai_backbone || {
        access_mode: "platform_managed",
        customer_api: { api_url: "", has_api_key: false },
        platform_managed: { api_url: "" },
        chatgpt_oauth: { linked: false, chatgpt_subject: null, session_ready: false, session_expires_at: null },
        effective_status: { ready: false, message: "Initializing..." },
      };
      setAiBackbone(settings);
      setAiBackboneForm(buildAiBackboneForm(settings, user?.name || user?.email || ""));

      const nextThreadId = selectedThreadId || workspace?.assistant_threads?.[0]?.id || null;
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

  const activityItems = useMemo(
    () =>
      buildActivityItems({
        campaigns,
        approvals,
        content,
        systemWorkflows,
        reviewJobs: reviewEngineJobs,
      }),
    [campaigns, approvals, content, systemWorkflows, reviewEngineJobs],
  );

  const quotaWarnings = useMemo(
    () =>
      (systemSummary?.quota || []).filter(
        (q) => q.total > 0 && q.used / q.total >= 0.8,
      ),
    [systemSummary?.quota],
  );

  const [quotaBannerDismissed, setQuotaBannerDismissed] = useState(false);
  const dashboardTabParam = searchParams.get("dashboard_tab");
  const reviewSourceUrl = searchParams.get("review_source_url") || "";
  const reviewPersonaIds = (searchParams.get("review_personas") || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  if (isLoading || !initialized) {
    return (
      <div className="dashboard-shell min-h-screen bg-aura-surface">
        <a
          href="#dashboard-main"
          className="sr-only fixed left-4 top-4 z-[70] rounded-full bg-white px-4 py-2 text-sm font-semibold text-aura-on-surface shadow-brand-md focus:not-sr-only"
        >
          Skip to main content
        </a>
        <DashboardHeader
          userName={undefined}
          userEmail={undefined}
          telegramBotUrl={null}
          onLogout={() => { }}
          isSigningOut={false}
        />
        <div className="flex pt-16">
          <DashboardSidebar
            tabs={DASHBOARD_TABS}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
          <main id="dashboard-main" className="flex-1 min-w-0 px-4 py-6 sm:px-6 md:px-10 md:py-8">
            <div className="mx-auto max-w-7xl h-[60vh] flex flex-col items-center justify-center space-y-4">
              <div className="animate-spin h-10 w-10 border-2 border-aura-primary border-t-transparent rounded-full" />
              <p className="text-sm text-aura-outline font-body">Loading workspace…</p>
            </div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-shell min-h-screen bg-aura-surface text-aura-on-surface">
      <a
        href="#dashboard-main"
        className="sr-only fixed left-4 top-4 z-[70] rounded-full bg-white px-4 py-2 text-sm font-semibold text-aura-on-surface shadow-brand-md focus:not-sr-only"
      >
        Skip to main content
      </a>
      <DashboardHeader
        userName={user?.name}
        userEmail={user?.email}
        telegramBotUrl={telegramBotUrl}
        onLogout={() => void handleLogout()}
        isSigningOut={busyKey === "signout"}
        onMobileMenuToggle={() => setIsMobileMenuOpen(prev => !prev)}
      />

      <div className="flex pt-16 min-h-[calc(100vh-64px)] relative">
        <DashboardSidebar
          tabs={DASHBOARD_TABS}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          telegramBotUrl={telegramBotUrl}
          isMobileOpen={isMobileMenuOpen}
          onMobileClose={() => setIsMobileMenuOpen(false)}
        />

        <main id="dashboard-main" className="flex-1 min-w-0 px-4 py-6 sm:px-6 md:px-10 md:py-8">
          <div className="mx-auto max-w-7xl space-y-4 md:space-y-6">


            {/* Success banner */}
            {banner && (
              <div className="dashboard-banner dashboard-banner-success text-sm font-medium" role="status" aria-live="polite">
                <span>✓ {banner}</span>
                <button onClick={() => setBanner(null)} className="ml-4 text-aura-tertiary/60 hover:text-aura-tertiary transition-colors">✕</button>
              </div>
            )}

            {/* Error banner */}
            {pageError && (
              <div className="dashboard-banner dashboard-banner-error animate-pulse-slow text-sm font-semibold" role="alert" aria-live="polite">
                <div className="flex items-center gap-3">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span>{pageError}</span>
                </div>
                <button type="button" onClick={() => setPageError(null)} className="ml-4 text-error/60 hover:text-error transition-colors" aria-label="Dismiss error message">
                  <X className="w-4 h-4 stroke-[2]" />
                </button>
              </div>
            )}

            {/* ─── Quota Warning Banner ─── */}
            {activeTab === "overview" && quotaWarnings.length > 0 && !quotaBannerDismissed && (
              <div className="dashboard-banner dashboard-banner-error animate-pulse-slow" role="status" aria-live="polite">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-error flex-shrink-0 mt-0.5 stroke-[2]" />
                  <div>
                    <p className="text-sm font-bold text-error">Quota threshold warning for today</p>
                    <p className="mt-1 text-xs text-error/80 font-medium leading-relaxed">
                      {quotaWarnings.map((q) => {
                        const pct = Math.round((q.used / q.total) * 100);
                        return `${q.name} (${pct}%)`;
                      }).join(" · ")}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setQuotaBannerDismissed(true)}
                  className="flex-shrink-0 text-error/60 hover:text-error transition-colors pt-1"
                  aria-label="Dismiss quota warning"
                >
                  <X className="w-4 h-4 stroke-[2]" />
                </button>
              </div>
            )}

            {activeTab === "overview" && (
              <OverviewTab
                campaigns={campaigns}
                approvals={approvals}
                content={content}
                personas={personas}
                systemSummary={systemSummary}
                onTabChange={setActiveTab}
                activityItems={activityItems}
                quotaWarnings={quotaWarnings}
                reviewJobs={reviewEngineJobs}
                onPublishJob={async (jobId) => {
                  try {
                    await customerApiRequest(`/api/customer/review-engine/jobs/${jobId}/publish`, {
                      method: "POST",
                      body: JSON.stringify({}),
                    });
                    setBanner("Publish started.");
                    await loadReviewEngineData();
                    await loadWorkspace();
                  } catch (error) {
                    setPageError(
                      error instanceof Error ? error.message : "Failed to publish review",
                    );
                  }
                }}
              />
            )}

            {activeTab === "ops" && (
              <div className="space-y-10 animate-fade-in">

                {/* ── Hero / Quick Stats Bento ── */}
                <section className="grid grid-cols-1 md:grid-cols-4 gap-4 md:gap-6">
                  {/* Hero card */}
                  <div className="md:col-span-2 bg-gradient-to-br from-white to-stone-50/50 p-6 md:p-8 rounded-[32px] md:rounded-[40px] flex flex-col justify-between border border-black/5 shadow-brand-sm min-h-[220px]">
                    <div>
                      <h2 className="text-2xl md:text-3xl font-semibold mb-2 text-brand-on-surface">AI Operations</h2>
                      <p className="text-brand-on-surface-variant max-w-xs text-sm leading-relaxed">
                        Integrated view of your AI Influencer ecosystem — campaigns, backbone, and real-time quota.
                      </p>
                    </div>
                    <div className="flex items-center gap-3 mt-6">
                      <button
                        type="button"
                        onClick={() => void handleCreateThread()}
                        disabled={busyKey === "thread"}
                        className="btn-primary"
                      >
                        + New Thread
                      </button>
                    </div>
                  </div>

                  {/* Quick stat cards */}
                  <div className="md:col-span-2 grid grid-cols-2 gap-4">
                    {[
                      {
                        label: "Active Campaigns",
                        value: campaigns.filter(c => c.status === "active").length,
                        target: 5,
                        delta: 2,
                        trend: "up",
                        emptyState: "Create your first campaign"
                      },
                      {
                        label: "Pending Approvals",
                        value: approvals.length,
                        target: 0,
                        delta: 0,
                        trend: "neutral",
                        emptyState: "All caught up!"
                      },
                      {
                        label: "Published Content",
                        value: content.filter(c => c.status === "published").length,
                        target: 10,
                        delta: 3,
                        trend: "up",
                        emptyState: "Publish your first piece"
                      },
                      {
                        label: "AI-Influencers",
                        value: personas?.length ?? 0,
                        target: 3,
                        delta: 0,
                        trend: "neutral",
                        emptyState: "Set up your first influencer"
                      },
                    ].map((stat, idx) => {
                      const bgColors = [
                        'bg-white', // Active Campaigns - neutral
                        'bg-amber-50', // Pending Approvals - warm accent
                        'bg-emerald-50', // Published Content - success
                        'bg-blue-50', // AI Personas - info
                      ];
                      return (
                        <div key={stat.label} className={`${bgColors[idx]} p-5 md:p-6 rounded-2xl border border-black/5 shadow-brand-sm flex min-h-[140px] md:min-h-[160px] flex-col justify-between hover:shadow-brand-md transition-shadow`}>
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <p className="text-[9px] font-semibold uppercase tracking-wider text-brand-on-surface-variant truncate mr-1">{stat.label}</p>
                              {stat.value > 0 && stat.delta > 0 && (
                                <span className="text-[9px] font-bold text-emerald-600 flex items-center gap-0.5">
                                  ↑ {stat.delta}
                                </span>
                              )}
                            </div>
                            <p className="text-[10px] text-brand-on-surface-variant font-medium">
                              {stat.value === 0 ? stat.emptyState : `Target: ${stat.target}`}
                            </p>
                          </div>
                          <div>
                            {stat.value === 0 ? (
                              <p className="text-3xl font-semibold text-brand-on-surface/30">—</p>
                            ) : (
                              <div className="flex items-end justify-between">
                                <p className="text-4xl font-semibold tracking-tight text-brand-on-surface">{stat.value}</p>
                                <span className="text-[10px] text-brand-on-surface-variant font-medium">/{stat.target}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* AI Backbone */}
                  <div className="lg:col-span-4 bg-white p-5 md:p-7 rounded-2xl flex flex-col justify-between border border-aura-outline/10 shadow-aura-sm">
                    <div className="space-y-5">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-aura-primary/10 rounded-lg flex items-center justify-center">
                          <Cpu className="w-5 h-5 text-aura-primary stroke-[1.5]" />
                        </div>
                        <div>
                          <h3 className="text-xl font-headline font-black text-aura-on-surface leading-tight">AI Backbone</h3>
                          <p className="text-[10px] text-aura-on-surface-variant mt-1 font-medium">Language model configuration</p>
                        </div>
                      </div>
                      <div className="space-y-3">
                        <div className="p-4 bg-aura-surface-container-low rounded-2xl">
                          <p className="text-[10px] text-aura-on-surface-variant mb-1.5 font-body uppercase tracking-wider font-semibold">Access Mode</p>
                          <p className="text-sm font-bold text-aura-on-surface capitalize">
                            {aiBackbone?.access_mode.replace(/_/g, " ") || "Loading…"}
                          </p>
                        </div>
                        {aiBackbone?.platform_managed.api_url ? (
                          <div className="p-4 bg-aura-surface-container-low rounded-2xl overflow-hidden">
                            <p className="text-[10px] text-aura-on-surface-variant mb-1.5 font-body uppercase tracking-wider font-semibold">Workspace Endpoint</p>
                            <code className="text-xs font-mono text-aura-primary truncate block break-all">
                              {aiBackbone.platform_managed.api_url}
                            </code>
                          </div>
                        ) : (
                          <div className="p-4 bg-aura-error/5 rounded-2xl border border-aura-error/20 flex items-start justify-between gap-3">
                            <div>
                              <p className="text-[10px] text-aura-on-surface-variant mb-1.5 font-body uppercase tracking-wider font-semibold">Workspace Endpoint</p>
                              <p className="text-sm font-semibold text-aura-error">Not configured</p>
                            </div>
                            <button
                              type="button"
                              onClick={() => setActiveTab("memory")}
                              className="text-[10px] min-h-[44px] font-bold px-4 py-2 bg-aura-error text-white rounded-lg hover:bg-aura-error/90 transition-all active:scale-95 flex-shrink-0 whitespace-nowrap cursor-pointer"
                            >
                              Configure
                            </button>
                          </div>
                        )}
                        <div className="p-4 bg-aura-surface-container-low rounded-2xl">
                          <p className="text-[10px] text-aura-on-surface-variant mb-1.5 font-body uppercase tracking-wider font-semibold">Status</p>
                          <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${aiBackbone?.effective_status.ready ? "bg-aura-tertiary animate-pulse" : "bg-aura-secondary animate-pulse"}`} />
                            <p className="text-[11px] leading-5 text-aura-on-surface font-semibold">
                              {aiBackbone?.effective_status.message || "Initializing…"}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveTab("memory")}
                      className="mt-6 w-full py-3 min-h-[44px] bg-aura-primary text-white rounded-xl text-sm font-body font-semibold hover:bg-aura-primary/90 transition-all active:scale-95 cursor-pointer"
                    >
                      Full Configuration
                    </button>
                  </div>

                  {/* Quota Snapshot */}
                  <div className="lg:col-span-3 bg-white p-5 md:p-7 rounded-2xl space-y-5 border border-aura-outline/10 shadow-aura-sm">
                    <div>
                      <h3 className="text-xl font-headline font-black text-aura-on-surface leading-tight">Quota Snapshot</h3>
                      <p className="text-[10px] text-aura-on-surface-variant mt-1.5 font-medium">Real-time usage metrics</p>
                    </div>
                    <div className="space-y-4">
                      {(systemSummary?.quota || []).length === 0 ? (
                        [
                          { name: "OpenAI", color: "bg-aura-primary", desc: "gpt-4-turbo" },
                          { name: "Anthropic", color: "bg-aura-secondary", desc: "Claude API" },
                          { name: "Google TTS", color: "bg-aura-tertiary", desc: "Text-to-speech" },
                          { name: "fal.ai", color: "bg-aura-error", desc: "Image generation" },
                          { name: "HeyGen", color: "bg-aura-primary-container", desc: "Video synthesis" },
                        ].map(q => (
                          <div key={q.name} className="space-y-2">
                            <div className="flex justify-between items-center">
                              <div>
                                <p className="text-sm font-semibold text-aura-on-surface">{q.name}</p>
                                <p className="text-[9px] text-aura-on-surface-variant">{q.desc}</p>
                              </div>
                              <span className="text-xs text-aura-on-surface-variant font-medium">—</span>
                            </div>
                            <div className="h-2.5 w-full bg-aura-surface-container rounded-full overflow-hidden shadow-sm">
                              <div className={`h-full ${q.color} animate-pulse`} style={{ width: "20%" }} />
                            </div>
                          </div>
                        ))
                      ) : (
                        (systemSummary?.quota || []).map(q => {
                          const pct = q.total > 0 ? Math.min((q.used / q.total) * 100, 100) : 0;
                          const isHigh = pct >= 80;
                          const isCritical = pct >= 95;
                          const barColor = isCritical ? "bg-aura-error" : isHigh ? "bg-aura-secondary" : "bg-aura-tertiary";
                          return (
                            <div key={q.name} className="space-y-2">
                              <div className="flex justify-between items-center">
                                <span className="text-sm font-semibold text-aura-on-surface flex items-center gap-2">
                                  {q.name}
                                  {isHigh && (
                                    <span className={`text-[8px] px-2 py-1 rounded-full font-bold tracking-wide ${isCritical ? "bg-aura-error/20 text-aura-error" : "bg-aura-secondary/20 text-aura-secondary"
                                      }`}>
                                      {isCritical ? "🚨 CRITICAL" : "⚠️ HIGH"}
                                    </span>
                                  )}
                                </span>
                                <span className={`text-sm font-bold ${isCritical ? "text-aura-error" : isHigh ? "text-aura-secondary" : "text-aura-on-surface-variant"}`}>
                                  {Math.round(pct)}%
                                </span>
                              </div>
                              <div className="h-2.5 w-full bg-aura-surface-container rounded-full overflow-hidden shadow-sm border border-aura-outline/5">
                                <div className={`h-full ${barColor} transition-all duration-700 rounded-full shadow-md`} style={{ width: `${pct}%` }} />
                              </div>
                              <div className="text-[9px] text-aura-on-surface-variant flex justify-between">
                                <span>{q.used.toLocaleString()} used</span>
                                <span>{q.total.toLocaleString()} {q.unit}</span>
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
                          width={1280}
                          height={720}
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
                    <h3 className="text-2xl md:text-3xl font-headline font-extrabold text-aura-on-surface leading-tight">
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
                                className="text-[10px] min-h-[44px] min-w-[44px] px-4 py-2 bg-aura-tertiary text-white rounded-full font-bold hover:opacity-90 active:scale-95 disabled:opacity-50 cursor-pointer flex items-center justify-center flex-shrink-0"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => handleApprove(a.id, false)}
                                disabled={busyKey === `approve-${a.id}`}
                                className="text-[10px] min-h-[44px] min-w-[44px] px-4 py-2 bg-aura-error/20 text-aura-error rounded-full font-bold hover:bg-aura-error/30 active:scale-95 disabled:opacity-50 cursor-pointer flex items-center justify-center flex-shrink-0"
                              >
                                Reject
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex flex-wrap gap-4">
                      <button
                        type="button"
                        onClick={() => void handleCreateThread()}
                        disabled={busyKey === "thread"}
                        className="bg-aura-primary text-aura-on-primary min-h-[44px] px-6 md:px-7 py-3 md:py-3.5 rounded-full font-body font-bold shadow-aura-md hover:scale-105 active:scale-95 transition-all disabled:opacity-50 cursor-pointer"
                      >
                        Launch Studio
                      </button>
                      <button
                        type="button"
                        onClick={() => setActiveTab("create_video")}
                        className="bg-aura-secondary-container text-aura-on-secondary-container min-h-[44px] px-6 md:px-7 py-3 md:py-3.5 rounded-full font-body font-bold hover:scale-105 active:scale-95 transition-all cursor-pointer"
                      >
                        Production Console
                      </button>
                    </div>
                  </div>
                </section>

                {/* ── Campaign Control + Output Stream ── */}
                <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-8">
                  <div className="bg-white rounded-2xl p-5 md:p-8 shadow-aura">
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
                            className="flex-shrink-0 text-[10px] min-h-[44px] min-w-[44px] px-5 py-2 bg-aura-tertiary text-white rounded-full font-bold hover:opacity-90 active:scale-95 disabled:opacity-40 transition-all cursor-pointer flex items-center justify-center"
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

                  <div className="bg-white rounded-2xl p-5 md:p-8 shadow-aura">
                    <h3 className="text-base font-headline font-bold text-aura-on-surface mb-5">Output Stream</h3>
                    <div className="space-y-2">
                      {content.slice(0, 6).map(item => (
                        <div key={item.id} className="p-3 bg-aura-surface-container-low border border-aura-outline-variant/15 rounded-xl flex justify-between items-center">
                          <span className="text-sm text-aura-on-surface truncate mr-2">{item.title}</span>
                          <span className={`flex-shrink-0 text-[10px] px-2.5 py-1 rounded-full font-bold ${item.status === "published"
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
              <PersonasTab
                personas={personas}
                setup={reviewEngineSetup}
                onNavigateToCreateVideo={() => setActiveTab("create_video")}
                onPersonasChanged={async () => {
                  await loadWorkspace();
                  await loadReviewEngineData();
                }}
              />
            )}

            {activeTab === "memory" && (
              <div className="space-y-10 animate-fade-in">

                {/* Page header */}
                <header>
                  <h1 className="text-4xl font-extrabold text-aura-on-surface font-headline tracking-tight mb-2">Project &amp; Memory</h1>
                  <p className="text-aura-on-surface-variant max-w-2xl text-sm font-body">
                    Define the core identity of your digital brand. These settings shape how AI learns, remembers, and communicates across every channel.
                  </p>
                </header>

                {/* Bento grid */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

                  {/* ── Left: Brand Context (8 col) ── */}
                  <section className="lg:col-span-8 space-y-8">

                    {/* Brand Context card */}
                    <div className="bg-white rounded-2xl p-5 md:p-8 shadow-aura">
                      <div className="flex items-center gap-3 mb-8">
                        <div className="w-12 h-12 rounded-2xl bg-aura-primary/10 flex items-center justify-center shrink-0">
                          <BookOpen className="w-5 h-5 text-aura-primary stroke-[1.5]" />
                        </div>
                        <h3 className="text-xl font-bold text-aura-on-surface font-headline">Brand Context</h3>
                      </div>

                      <form className="space-y-6" onSubmit={handleBrandSave}>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div className="space-y-2">
                            <label htmlFor="brand-name" className="block text-sm font-semibold text-aura-on-surface-variant px-1">Brand Name</label>
                            <input
                              id="brand-name"
                              name="brandName"
                              type="text"
                              value={brandForm.product_name || ""}
                              onChange={e => setBrandForm(c => ({ ...c, product_name: e.target.value }))}
                              placeholder="Enter brand name…"
                              autoComplete="organization"
                              className="w-full bg-aura-surface-container border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-aura-primary/20 text-aura-on-surface font-body font-medium transition-all outline-none"
                            />
                          </div>
                          <div className="space-y-2">
                            <label htmlFor="brand-audience" className="block text-sm font-semibold text-aura-on-surface-variant px-1">Target Audience</label>
                            <input
                              id="brand-audience"
                              name="targetAudience"
                              type="text"
                              value={brandForm.audience || ""}
                              onChange={e => setBrandForm(c => ({ ...c, audience: e.target.value }))}
                              placeholder="Describe your target audience…"
                              autoComplete="off"
                              className="w-full bg-aura-surface-container border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-aura-primary/20 text-aura-on-surface font-body font-medium transition-all outline-none"
                            />
                          </div>
                        </div>

                        <div className="space-y-2">
                          <label htmlFor="brand-summary" className="block text-sm font-semibold text-aura-on-surface-variant px-1">Value Summary</label>
                          <textarea
                            id="brand-summary"
                            name="valueSummary"
                            value={brandForm.offer_summary || ""}
                            onChange={e => setBrandForm(c => ({ ...c, offer_summary: e.target.value }))}
                            placeholder="Summarize your product or service…"
                            rows={4}
                            autoComplete="off"
                            className="w-full bg-aura-surface-container border-none rounded-2xl px-4 py-4 focus:ring-2 focus:ring-aura-primary/20 text-aura-on-surface font-body font-medium transition-all resize-none outline-none"
                          />
                        </div>

                        <div className="flex justify-end">
                          <button
                            type="submit"
                            disabled={busyKey === "brand"}
                            className="w-full md:w-auto min-h-[44px] px-10 py-3.5 bg-aura-primary text-aura-on-primary font-bold rounded-full hover:opacity-90 transition-all shadow-aura-md active:scale-95 disabled:opacity-50 cursor-pointer"
                          >
                            {busyKey === "brand" ? "Saving..." : "Save Context"}
                          </button>
                        </div>
                      </form>
                    </div>

                    {/* Intelligence Mode + System Bridge */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                      {/* Intelligence Mode */}
                      <div className="bg-white rounded-2xl p-5 md:p-8 shadow-aura flex flex-col justify-between">
                        <div>
                          <div className="flex items-center gap-3 mb-6">
                            <div className="w-10 h-10 rounded-xl bg-aura-tertiary/10 flex items-center justify-center shrink-0">
                              <Brain className="w-5 h-5 text-aura-tertiary stroke-[1.5]" />
                            </div>
                            <h3 className="font-bold text-aura-on-surface font-headline">Intelligence Mode</h3>
                          </div>
                          <p className="text-sm text-aura-on-surface-variant mb-6 leading-relaxed font-body">
                            Define how AI accesses and uses stored memory in conversations.
                          </p>
                        </div>
                        <div className="flex flex-col gap-3">
                          <div className="flex items-center justify-between w-full p-5 bg-aura-surface-container-lowest rounded-2xl border-2 border-aura-primary shadow-aura-sm">
                            <span className="font-bold text-aura-on-surface text-sm">
                              {aiBackbone?.access_mode.replace(/_/g, " ") || "Platform Managed"}
                            </span>
                            <Check className="w-4 h-4 text-aura-tertiary stroke-[2.5]" />
                          </div>
                          <div className="flex items-center justify-between w-full p-5 bg-aura-surface-container-low rounded-2xl border-2 border-transparent">
                            <span className="text-sm font-medium text-aura-on-surface-variant/80">
                              {aiBackbone?.effective_status.message || "Initializing…"}
                            </span>
                            <span className={`w-2 h-2 rounded-full ${aiBackbone?.effective_status.ready ? "bg-aura-tertiary" : "bg-aura-secondary animate-pulse"}`} />
                          </div>
                        </div>
                      </div>

                      {/* System Bridge — Telegram */}
                      <div className="bg-white rounded-2xl p-5 md:p-8 shadow-aura flex flex-col justify-between">
                        <div>
                          <div className="flex items-center gap-3 mb-6">
                            <div className="w-10 h-10 rounded-xl bg-aura-secondary/10 flex items-center justify-center shrink-0">
                              <Link2 className="w-5 h-5 text-aura-secondary stroke-[1.5]" />
                            </div>
                            <h3 className="font-bold text-aura-on-surface font-headline">System Bridge</h3>
                          </div>
                          <p className="text-sm text-aura-on-surface-variant mb-6 leading-relaxed font-body">
                            Enable direct control and monitoring through secure messaging protocols.
                          </p>
                        </div>

                        {telegramLink?.linked ? (
                          <div className="p-5 bg-aura-surface-container rounded-2xl flex items-center gap-4">
                            <div className="w-10 h-10 bg-aura-surface-container rounded-full flex items-center justify-center flex-shrink-0 shadow-aura-sm">
                              <SocialIcon platform="telegram" size={20} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-bold text-aura-on-surface">@{telegramLink.link?.telegram_username || "Linked Account"}</p>
                              <p className="text-[10px] text-aura-on-surface-variant">ID: {telegramLink.link?.chat_id}</p>
                              <p className="text-[10px] text-aura-tertiary font-bold uppercase tracking-wide mt-0.5">Connected</p>
                            </div>
                            <button
                              type="button"
                              onClick={handleStartTelegramLink}
                              className="text-aura-on-surface-variant hover:text-aura-primary transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center cursor-pointer shrink-0"
                              aria-label="Re-link Telegram"
                            ><RefreshCw className="w-4 h-4 stroke-[1.75]" /></button>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <button
                              type="button"
                              onClick={handleStartTelegramLink}
                              disabled={busyKey === "telegram-link"}
                              className="w-full min-h-[44px] py-3 bg-white text-aura-on-surface border border-aura-outline/20 font-bold rounded-full hover:bg-aura-surface-container-low active:scale-95 transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-aura-sm cursor-pointer"
                            >
                              {busyKey !== "telegram-link" && <SocialIcon platform="telegram" size={18} />}
                              {busyKey === "telegram-link" ? "Generating link..." : "Connect Telegram"}
                            </button>
                            {linkToken && telegramVerificationUrl && (
                              <div className="p-4 bg-aura-secondary-container/30 border border-aura-secondary/20 rounded-xl text-center">
                                <p className="text-xs text-aura-secondary mb-3 font-medium">
                                  {isPollingTelegramLink ? "Waiting for Telegram confirmation..." : "Link is ready. Confirm on Telegram."}
                                </p>
                                <a
                                  href={telegramVerificationUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 bg-aura-secondary text-aura-on-secondary rounded-full font-bold text-xs hover:opacity-90 active:scale-95 transition-all cursor-pointer"
                                >
                                  Confirm Now
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
                    <div className="bg-aura-surface-container-high rounded-2xl p-5 md:p-8">
                      <h3 className="text-lg font-bold font-headline text-aura-on-surface mb-2">Social Network</h3>
                      <p className="text-xs text-aura-on-surface-variant mb-8 font-body">
                        Enable or disable automatic posting targets for the memory-optimized content cycle.
                      </p>

                      <div className="grid grid-cols-2 gap-4">
                        {SUPPORTED_PLATFORMS.map(p => {
                          const acc = accounts.find(a => a.platform === p);
                          return (
                            <div
                              key={p}
                              className="bg-white/60 backdrop-blur p-4 rounded-3xl flex flex-col items-center justify-center gap-3 shadow-aura-sm transition-all"
                            >
                              <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center border border-aura-outline/5">
                                <SocialIcon platform={p} size={24} />
                              </div>
                              <span className="text-xs font-bold text-aura-on-surface capitalize">{p}</span>
                              {acc ? (
                                <button
                                  type="button"
                                  onClick={() => handleConnect(p)} // Typically opens disconnect modal or something, matching toggle pattern
                                  aria-label={`Manage ${p} connection`}
                                  aria-pressed={true}
                                  className="w-12 h-6 bg-aura-primary rounded-full relative cursor-pointer hover:bg-aura-primary/90 transition-colors flex items-center justify-end px-1"
                                >
                                  <div className="w-4 h-4 bg-white rounded-full" />
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleConnect(p)}
                                  aria-label={`Manage ${p} connection`}
                                  aria-pressed={false}
                                  className="w-12 h-6 bg-aura-surface-container-high border border-aura-outline/20 rounded-full relative cursor-pointer hover:bg-aura-outline/20 transition-colors flex items-center justify-start px-1"
                                >
                                  <div className="w-4 h-4 bg-white rounded-full shadow-sm" />
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>

                      {/* Memory capacity bar */}
                      <div className="mt-8 pt-8 border-t border-aura-outline-variant/20">
                        <div className="flex items-end justify-between mb-3">
                          <span className="text-[10px] font-semibold uppercase tracking-widest text-aura-on-surface-variant">Memory Capacity</span>
                          <span className="text-5xl font-black text-aura-primary leading-none">84%</span>
                        </div>
                        <div className="w-full bg-aura-surface-container-lowest h-2 rounded-full overflow-hidden">
                          <div className="bg-gradient-to-r from-aura-primary to-aura-primary-container h-full w-[84%] rounded-full shadow-aura-sm" />
                        </div>
                        <p className="text-[10px] text-aura-on-surface-variant mt-4 leading-relaxed italic font-body">
                          Higher retention lets AI recall nuanced brand preferences from past interactions more accurately.
                        </p>
                      </div>
                    </div>

                    {/* Persona visual card */}
                    {personas.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setActiveTab("skills")}
                        className="relative block w-full text-left group"
                      >
                        <div className="aspect-[4/5] rounded-2xl overflow-hidden shadow-aura-md transition-transform group-hover:scale-[1.02] duration-300 bg-aura-surface-container-high">
                          {personas[0]?.avatar_image_url ? (
                            <img
                              src={personas[0].avatar_image_url}
                              alt={personas[0].display_name}
                              width={800}
                              height={1000}
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
                            <p className="text-white/70 text-xs font-body mt-0.5">Active Persona</p>
                            <div className="mt-4 flex items-center gap-2">
                              <span className="w-2 h-2 bg-aura-tertiary rounded-full animate-pulse" />
                              <span className="text-[10px] text-white/90 font-body font-medium uppercase tracking-widest">
                                {personas[0]?.status === "active" ? "Optimized & Synced" : "Awaiting Activation"}
                              </span>
                            </div>
                          </div>
                        </div>
                      </button>
                    )}

                  </aside>
                </div>

              </div>
            )}

            {activeTab === "create_video" && (
              <LiveFeedTab
                activityItems={activityItems}
                systemWorkflows={systemWorkflows}
                content={content}
                personas={personas}
                setup={reviewEngineSetup}
                jobs={reviewEngineJobs}
                initialSourceUrl={reviewSourceUrl}
                initialPersonaIds={reviewPersonaIds}
                onRefresh={async () => {
                  await loadReviewEngineData();
                  await loadWorkspace();
                }}
                onNavigateToPersonas={() => setActiveTab("skills")}
                onNavigateToPublishing={() => setActiveTab("publishing")}
              />
            )}

            {activeTab === "publishing" && (
              <PublishingTab content={content} />
            )}
          </div>

          {/* Page Footer branding */}
          <footer className="mt-12 py-10 border-t border-aura-outline-variant/10 flex justify-center">
            <div className="flex items-center gap-2">
              <img
                src={openClawLogo.src}
                alt="OpenClaw"
                width={96}
                height={16}
                className="h-4 w-auto opacity-75"
              />
              <span className="text-xs text-aura-on-surface-variant font-body">
                Operated by OpenClaw
              </span>
            </div>
          </footer>
        </main>
      </div>
    </div>
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
  reviewJobs,
}: {
  campaigns: Campaign[];
  approvals: Campaign[];
  content: ContentItem[];
  systemWorkflows: SystemWorkflowData[];
  reviewJobs: ReviewEngineJob[];
}): ActivityItem[] {
  const items: ActivityItem[] = [];

  (reviewJobs || []).slice(0, 6).forEach((job) => {
    items.push({
      id: `review-job-${job.job_id}`,
      title:
        job.content?.title ||
        job.page_title ||
        job.persona?.display_name ||
        "App review",
      detail: `${getReviewJobStatusLabel(job)} • ${job.progress}% complete`,
      tone: getReviewJobTone(job),
      progress: job.progress,
      personaImage: getReviewJobPersonaImage(job),
      timeLabel: job.updated_at || job.started_at || "",
    });
  });

  if (items.length >= 8) {
    return items.slice(0, 8);
  }

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
