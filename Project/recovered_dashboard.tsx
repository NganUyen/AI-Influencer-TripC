"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { customerApiRequest } from "@/lib/customer-api";
import { useCustomerAuthStore } from "@/store/customer-auth-store";

type BrandProfile = {
  brand_profile_id?: string;
  product_name: string;
  website_url?: string | null;
  audience?: string | null;
  offer_summary?: string | null;
  tone_voice?: string | null;
  campaign_goals?: string[];
  asset_urls?: string[];
  timezone?: string;
  telegram_contact?: string | null;
};

type SocialAccount = {
  id: string;
  platform: string;
  display_name?: string | null;
  account_handle?: string | null;
  connection_status: string;
};

type AssistantThread = {
  id: string;
  title: string;
  last_message_preview?: string | null;
};

type AssistantMessage = {
  id: string;
  role: string;
  content: string;
};

type AssistantArtifact = {
  id: string;
  title: string;
  payload: Record<string, unknown>;
};

type Campaign = {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  approval_status: string;
  target_platforms: string[];
  active_workflow_id?: string | null;
};

type ContentItem = {
  id: string;
  title: string;
  status: string;
  platform: string[];
  published_at?: string | null;
  scheduled_at?: string | null;
};

type Persona = {
  persona_id: string;
  display_name: string;
  language?: string | null;
  tts_voice?: string | null;
  avatar_image_url?: string | null;
  status: string;
  video_count: number;
  created_at: string;
};

type AIBackboneAccessMode =
  | "platform_managed"
  | "customer_api_key"
  | "chatgpt_oauth";

type AIBackboneSettings = {
  access_mode: AIBackboneAccessMode;
  platform_managed: {
    api_url: string;
    has_api_key: boolean;
  };
  customer_api: {
    api_url: string;
    has_api_key: boolean;
    updated_at?: string | null;
  };
  chatgpt_oauth: {
    linked: boolean;
    session_ready: boolean;
    chatgpt_subject?: string | null;
    display_name?: string | null;
    subscription_tier?: string | null;
    linked_at?: string | null;
    last_used_at?: string | null;
    session_expires_at?: string | null;
  };
  effective_status: {
    ready: boolean;
    message: string;
  };
};

type AIBackboneForm = {
  accessMode: AIBackboneAccessMode;
  customerApiUrl: string;
  customerApiKey: string;
  chatgptSubject: string;
  chatgptDisplayName: string;
  chatgptSubscriptionTier: "plus" | "pro";
};

type TelegramLinkStatus = {
  linked: boolean;
  link?: {
    chat_id: number;
    user_id: string;
    telegram_username?: string | null;
    linked_at: string;
    last_verified_at: string;
    revoked_at?: string | null;
  } | null;
};

type TelegramLinkToken = {
  start_token: string;
  expires_at: string;
};

const SUPPORTED_PLATFORMS = ["linkedin", "facebook", "twitter", "youtube"];
const AI_BACKBONE_OPTIONS: Array<{
  value: AIBackboneAccessMode;
  title: string;
  description: string;
}> = [
  {
    value: "platform_managed",
    title: "Workspace Managed",
    description: "Use the shared OpenClaw backbone managed by the platform.",
  },
  {
    value: "customer_api_key",
    title: "Bring Your API",
    description: "Store your own OpenClaw API key and route assistant runs through it.",
  },
  {
    value: "chatgpt_oauth",
    title: "GPT Plus / Pro OAuth",
    description: "Use the connector-backed GPT OAuth path for customer-owned access.",
  },
];
const EMPTY_BRAND: BrandProfile = {
  product_name: "",
  website_url: "",
  audience: "",
  offer_summary: "",
  tone_voice: "",
  campaign_goals: [],
  asset_urls: [],
  timezone: "UTC",
  telegram_contact: "",
};
const EMPTY_AI_BACKBONE: AIBackboneSettings = {
  access_mode: "platform_managed",
  platform_managed: {
    api_url: "",
    has_api_key: false,
  },
  customer_api: {
    api_url: "",
    has_api_key: false,
    updated_at: null,
  },
  chatgpt_oauth: {
    linked: false,
    session_ready: false,
    chatgpt_subject: "",
    display_name: "",
    subscription_tier: "plus",
    linked_at: null,
    last_used_at: null,
    session_expires_at: null,
  },
  effective_status: {
    ready: true,
    message: "Using workspace-managed OpenClaw access.",
  },
};
const TELEGRAM_BOT_URL = buildTelegramBotUrl();

function buildAiBackboneForm(
  settings: AIBackboneSettings,
  fallbackDisplayName: string,
): AIBackboneForm {
  return {
    accessMode: settings.access_mode,
    customerApiUrl:
      settings.customer_api.api_url || settings.platform_managed.api_url || "",
    customerApiKey: "",
    chatgptSubject: settings.chatgpt_oauth.chatgpt_subject || "",
    chatgptDisplayName:
      settings.chatgpt_oauth.display_name || fallbackDisplayName || "",
    chatgptSubscriptionTier:
      settings.chatgpt_oauth.subscription_tier === "pro" ? "pro" : "plus",
  };
}

export default function CustomerDashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    user,
    isAuthenticated,
    isLoading,
    initialized,
    error: authError,
    initialize,
    logout,
  } = useCustomerAuthStore((state) => ({
    user: state.user,
    isAuthenticated: state.isAuthenticated,
    isLoading: state.isLoading,
    initialized: state.initialized,
    error: state.error,
    initialize: state.initialize,
    logout: state.logout,
  }));

  const [brandForm, setBrandForm] = useState<BrandProfile>(EMPTY_BRAND);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [threads, setThreads] = useState<AssistantThread[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [artifacts, setArtifacts] = useState<AssistantArtifact[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [approvals, setApprovals] = useState<Campaign[]>([]);
  const [content, setContent] = useState<ContentItem[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [telegramLink, setTelegramLink] = useState<TelegramLinkStatus | null>(
    null,
  );
  const [linkToken, setLinkToken] = useState<TelegramLinkToken | null>(null);
  const [aiBackbone, setAiBackbone] =
    useState<AIBackboneSettings>(EMPTY_AI_BACKBONE);
  const [aiBackboneForm, setAiBackboneForm] = useState<AIBackboneForm>(
    buildAiBackboneForm(EMPTY_AI_BACKBONE, ""),
  );
  const [composer, setComposer] = useState("");
  const [campaignDraft, setCampaignDraft] = useState({
    name: "",
    description: "",
    targetPlatforms: "linkedin,facebook,twitter",
  });
  const [banner, setBanner] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const formattedTelegramContact = formatTelegramContact(
    brandForm.telegram_contact,
  );
  const telegramSetupComplete = Boolean(formattedTelegramContact);

  useEffect(() => {
    void initialize();
  }, [initialize]);

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
      ] =
        await Promise.all([
          customerApiRequest<{ brand_profile: BrandProfile | null }>(
            "/api/customer/brand",
          ),
          customerApiRequest<{ accounts: SocialAccount[] }>(
            "/api/customer/social-accounts",
          ),
          customerApiRequest<{ threads: AssistantThread[] }>(
            "/api/customer/assistant/threads",
          ),
          customerApiRequest<{ campaigns: Campaign[] }>(
            "/api/customer/campaigns",
          ),
          customerApiRequest<{ approvals: Campaign[] }>(
            "/api/customer/approvals",
          ),
          customerApiRequest<{ items: ContentItem[] }>("/api/customer/content"),
          customerApiRequest<{ settings: AIBackboneSettings }>(
            "/api/customer/ai-backbone",
          ),
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
      setAiBackbone(aiBackboneResponse.settings);
      setAiBackboneForm(
        buildAiBackboneForm(
          aiBackboneResponse.settings,
          user?.name || user?.email || "",
        ),
      );

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
    if (!selectedThreadId || !composer.trim() || !aiBackbone.effective_status.ready) {
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
      setPageError(
        error instanceof Error ? error.message : "Failed to start Telegram link",
      );
    } finally {
      setBusyKey(null);
    }
  }

  if (isLoading || !initialized) {
    return (
      <div className="min-h-screen bg-slate-950 text-stone-100 flex items-center justify-center">
        <p className="text-lg tracking-wide">Loading your workspace...</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#1f4f46_0%,#091018_38%,#05070b_100%)] text-stone-100">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <header className="mb-8 flex flex-col gap-4 rounded-[28px] border border-emerald-200/10 bg-white/5 p-6 backdrop-blur md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-emerald-200/70">
              Customer Workspace
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">
              Launch campaigns from one guided control room
            </h1>
            <p className="mt-3 max-w-2xl text-sm text-stone-300">
              Connect your official accounts, shape the campaign with OpenClaw,
              review the plan, and launch the workflow into Temporal without exposing
              Postiz or GrowChief directly.
            </p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-black/20 px-5 py-4 text-sm text-stone-200">
            <p className="font-medium text-white">{user?.name || user?.email}</p>
            <p>{user?.email}</p>
            <button
              type="button"
              onClick={() => void logout().then(() => router.replace("/auth"))}
              className="mt-3 rounded-full border border-white/15 px-4 py-2 text-xs uppercase tracking-[0.2em] text-stone-100 transition hover:border-emerald-300 hover:text-emerald-200"
            >
              Sign Out
            </button>
          </div>
        </header>

        {(banner || pageError || authError) && (
          <div className="mb-6 rounded-2xl border border-white/10 bg-black/30 p-4 text-sm">
            {banner && <p className="text-emerald-200">{banner}</p>}
            {(pageError || authError) && (
              <p className="text-rose-200">{pageError || authError}</p>
            )}
          </div>
        )}

        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <section className="space-y-6">
            <Panel title="Brand Onboarding" subtitle="This becomes the canonical planning input for weekly strategy generation.">
              <form className="grid gap-4 md:grid-cols-2" onSubmit={handleBrandSave}>
                <Field
                  label="Product Name"
                  value={brandForm.product_name || ""}
                  onChange={(value) => setBrandForm((current) => ({ ...current, product_name: value }))}
                />
                <Field
                  label="Website"
                  value={brandForm.website_url || ""}
                  onChange={(value) => setBrandForm((current) => ({ ...current, website_url: value }))}
                />
                <Field
                  label="Audience"
                  value={brandForm.audience || ""}
                  onChange={(value) => setBrandForm((current) => ({ ...current, audience: value }))}
                />
                <Field
                  label="Offer"
                  value={brandForm.offer_summary || ""}
                  onChange={(value) => setBrandForm((current) => ({ ...current, offer_summary: value }))}
                />
                <Field
                  label="Tone"
                  value={brandForm.tone_voice || ""}
                  onChange={(value) => setBrandForm((current) => ({ ...current, tone_voice: value }))}
                />
                <Field
                  label="Timezone"
                  value={brandForm.timezone || "UTC"}
                  onChange={(value) => setBrandForm((current) => ({ ...current, timezone: value }))}
                />
                <TextAreaField
                  className="md:col-span-2"
                  label="Campaign Goals"
                  value={(brandForm.campaign_goals || []).join(", ")}
                  onChange={(value) =>
                    setBrandForm((current) => ({ ...current, campaign_goals: splitList(value) }))
                  }
                />
                <TextAreaField
                  className="md:col-span-2"
                  label="Asset URLs"
                  value={(brandForm.asset_urls || []).join(", ")}
                  onChange={(value) =>
                    setBrandForm((current) => ({ ...current, asset_urls: splitList(value) }))
                  }
                />
                <Field
                  label="Telegram Contact"
                  value={brandForm.telegram_contact || ""}
                  onChange={(value) => setBrandForm((current) => ({ ...current, telegram_contact: value }))}
                />
                <div className="flex items-end">
                  <button
                    type="submit"
                    disabled={busyKey === "brand"}
                    className="w-full rounded-full bg-emerald-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busyKey === "brand" ? "Saving..." : "Save Brand Profile"}
                  </button>
                </div>
              </form>
            </Panel>

            <Panel title="In-App OpenClaw Assistant" subtitle="Use this thread to refine positioning, weekly plans, and campaign artifacts before launch.">
              <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                <div className="space-y-3 rounded-3xl border border-white/10 bg-black/20 p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-300">
                      Threads
                    </h3>
                    <button
                      type="button"
                      onClick={() => void handleCreateThread()}
                      disabled={busyKey === "thread"}
                      className="rounded-full border border-emerald-300/40 px-3 py-1 text-xs uppercase tracking-[0.18em] text-emerald-200 transition hover:border-emerald-200"
                    >
                      New
                    </button>
                  </div>
                  <div className="space-y-2">
                    {threads.length === 0 && (
                      <p className="text-sm text-stone-400">
                        Create your first planning thread to brief OpenClaw.
                      </p>
                    )}
                    {threads.map((thread) => (
                      <button
                        key={thread.id}
                        type="button"
                        onClick={() => setSelectedThreadId(thread.id)}
                        className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                          selectedThreadId === thread.id
                            ? "border-emerald-300 bg-emerald-200/10"
                            : "border-white/8 bg-white/5 hover:border-white/20"
                        }`}
                      >
                        <p className="font-medium text-white">{thread.title}</p>
                        <p className="mt-1 text-xs text-stone-400">
                          {thread.last_message_preview || "No messages yet"}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-4 rounded-3xl border border-white/10 bg-black/20 p-4">
                  <div className="max-h-[420px] space-y-3 overflow-y-auto pr-2">
                    {messages.length === 0 && (
                      <p className="text-sm text-stone-400">
                        Ask for a weekly content angle, a launch narrative, or a plan built from your brand profile.
                      </p>
                    )}
                    {messages.map((message) => (
                      <div
                        key={message.id}
                        className={`rounded-3xl px-4 py-3 text-sm ${
                          message.role === "assistant"
                            ? "bg-emerald-200/10 text-stone-100"
                            : "bg-white/8 text-stone-200"
                        }`}
                      >
                        <p className="mb-2 text-[11px] uppercase tracking-[0.2em] text-stone-400">
                          {message.role}
                        </p>
                        <p className="whitespace-pre-wrap">{message.content}</p>
                      </div>
                    ))}
                  </div>

                  <form className="space-y-3" onSubmit={handleSendMessage}>
                    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-stone-300">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-emerald-200/80">
                        Backbone Status
                      </p>
                      <p className="mt-1">{aiBackbone.effective_status.message}</p>
                    </div>
                    <textarea
                      value={composer}
                      onChange={(event) => setComposer(event.target.value)}
                      placeholder="Create a review-first weekly launch plan for my current brand profile and propose target platforms."
                      className="min-h-[120px] w-full rounded-3xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-emerald-300"
                    />
                    <button
                      type="submit"
                      disabled={
                        !selectedThreadId ||
                        busyKey === "assistant" ||
                        !aiBackbone.effective_status.ready
                      }
                      className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busyKey === "assistant"
                        ? "Running OpenClaw..."
                        : aiBackbone.effective_status.ready
                          ? "Send To OpenClaw"
                          : "Resolve AI Access First"}
                    </button>
                  </form>

                  {artifacts.length > 0 && (
                    <div className="rounded-3xl border border-emerald-300/20 bg-emerald-300/5 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-emerald-200/80">
                        Latest Assistant Artifact
                      </p>
                      <p className="mt-2 text-sm font-medium text-white">
                        {artifacts[0].title}
                      </p>
                      <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-stone-300">
                        {JSON.stringify(artifacts[0].payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </Panel>

            <Panel
              title="My AI Personas"
              subtitle="Personas linked to your account via Telegram. Sync happens automatically when you create them in the bot."
            >
              {personas.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-3xl border border-white/5 bg-white/5 py-10 text-center">
                  <p className="text-sm text-stone-400">
                    No personas linked yet.
                  </p>
                  <p className="mt-2 text-xs text-stone-500">
                    Chat with your bot to create your first AI influencer.
                  </p>
                  {TELEGRAM_BOT_URL && (
                    <a
                      href={TELEGRAM_BOT_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-6 rounded-full border border-emerald-300/40 px-4 py-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald-200 transition hover:bg-emerald-300/10"
                    >
                      Open Bot
                    </a>
                  )}
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {personas.map((persona) => (
                    <div
                      key={persona.persona_id}
                      className="group flex items-center gap-4 rounded-3xl border border-white/8 bg-black/20 p-4 transition hover:border-white/20"
                    >
                      <div className="relative h-16 w-16 overflow-hidden rounded-2xl bg-slate-800">
                        {persona.avatar_image_url ? (
                          <img
                            src={persona.avatar_image_url}
                            alt={persona.display_name}
                            className="h-full w-full object-cover transition duration-500 group-hover:scale-110"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-xl font-bold text-stone-600">
                            {persona.display_name.charAt(0)}
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="truncate text-base font-medium text-white">
                          {persona.display_name}
                        </h4>
                        <div className="mt-1 flex items-center gap-3">
                          <StatusBadge label={persona.status} />
                          <span className="text-[10px] uppercase tracking-widest text-stone-500">
                            {persona.video_count} videos
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Campaign Control" subtitle="Create a draft from your connected accounts, approve it, then launch it into Temporal.">
              <form className="grid gap-4 md:grid-cols-3" onSubmit={handleCreateCampaign}>
                <Field
                  label="Campaign Name"
                  value={campaignDraft.name}
                  onChange={(value) => setCampaignDraft((current) => ({ ...current, name: value }))}
                />
                <Field
                  label="Platforms"
                  value={campaignDraft.targetPlatforms}
                  onChange={(value) => setCampaignDraft((current) => ({ ...current, targetPlatforms: value }))}
                />
                <div className="flex items-end">
                  <button
                    type="submit"
                    disabled={busyKey === "campaign"}
                    className="w-full rounded-full bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busyKey === "campaign" ? "Saving..." : "Create Draft"}
                  </button>
                </div>
                <TextAreaField
                  className="md:col-span-3"
                  label="Description"
                  value={campaignDraft.description}
                  onChange={(value) => setCampaignDraft((current) => ({ ...current, description: value }))}
                />
              </form>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <div className="space-y-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-400">
                    Active Campaigns
                  </p>
                  {campaigns.length === 0 && (
                    <p className="text-sm text-stone-400">
                      No campaign drafts yet. Use the assistant, then create a draft here.
                    </p>
                  )}
                  {campaigns.map((campaign) => (
                    <div
                      key={campaign.id}
                      className="rounded-3xl border border-white/10 bg-black/20 p-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-lg font-medium text-white">{campaign.name}</p>
                          <p className="mt-1 text-sm text-stone-400">
                            {campaign.description || "No description"}
                          </p>
                        </div>
                        <StatusBadge label={`${campaign.approval_status} / ${campaign.status}`} />
                      </div>
                      <p className="mt-3 text-xs uppercase tracking-[0.18em] text-stone-500">
                        {campaign.target_platforms.join(" • ") || "No platforms set"}
                      </p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void handleApprove(campaign.id, true)}
                          disabled={busyKey === `approve-${campaign.id}`}
                          className="rounded-full border border-emerald-300/40 px-4 py-2 text-xs font-medium uppercase tracking-[0.16em] text-emerald-200 transition hover:border-emerald-200"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleApprove(campaign.id, false)}
                          disabled={busyKey === `approve-${campaign.id}`}
                          className="rounded-full border border-rose-300/30 px-4 py-2 text-xs font-medium uppercase tracking-[0.16em] text-rose-200 transition hover:border-rose-200"
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleLaunch(campaign.id)}
                          disabled={campaign.approval_status !== "approved" || busyKey === `launch-${campaign.id}`}
                          className="rounded-full bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Launch
                        </button>
                      </div>
                      {campaign.active_workflow_id && (
                        <p className="mt-3 text-xs text-emerald-200">
                          Workflow: {campaign.active_workflow_id}
                        </p>
                      )}
                    </div>
                  ))}
                </div>

                <div className="space-y-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-400">
                    Pending Review
                  </p>
                  {approvals.length === 0 && (
                    <p className="text-sm text-stone-400">
                      Nothing is waiting for approval right now.
                    </p>
                  )}
                  {approvals.map((campaign) => (
                    <div
                      key={campaign.id}
                      className="rounded-3xl border border-amber-300/20 bg-amber-300/5 p-4"
                    >
                      <p className="font-medium text-white">{campaign.name}</p>
                      <p className="mt-1 text-sm text-stone-300">
                        Ready for review across {campaign.target_platforms.join(", ")}.
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </Panel>
          </section>

          <section className="space-y-6">
            <Panel 
              title="Telegram Connection" 
              subtitle="Link your Telegram account to enable approvals, persona syncing, and automated workflows."
            >
              <div className="space-y-4">
                {telegramLink?.linked ? (
                  <div className="rounded-3xl border border-emerald-300/15 bg-emerald-300/5 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-emerald-100/80">
                          Linked Account
                        </p>
                        <p className="mt-2 text-sm text-stone-200">
                          {telegramLink.link?.telegram_username
                            ? `@${telegramLink.link.telegram_username}`
                            : `Chat ID: ${telegramLink.link?.chat_id}`}
                        </p>
                      </div>
                      <StatusBadge label="linked" />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <p className="text-sm text-stone-300">
                      Linking your Telegram allows the bot to know exactly which
                      personas belong to you.
                    </p>
                    {linkToken ? (
                      <div className="space-y-3 rounded-3xl border border-amber-300/20 bg-amber-300/5 p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-amber-200/80">
                          Magic Link Generated
                        </p>
                        <p className="text-sm text-white">
                          Click the button below to open the bot and link your
                          chat.
                        </p>
                        <a
                          href={`${TELEGRAM_BOT_URL}?start=${linkToken.start_token}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex w-full items-center justify-center rounded-full bg-amber-200 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-100"
                        >
                          Link Telegram Now
                        </a>
                        <p className="text-[10px] text-stone-500">
                          Expires at:{" "}
                          {new Date(linkToken.expires_at).toLocaleTimeString()}
                        </p>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => void handleStartTelegramLink()}
                        disabled={busyKey === "telegram-link"}
                        className="w-full rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:opacity-50"
                      >
                        {busyKey === "telegram-link"
                          ? "Generating Token..."
                          : "Link My Telegram"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </Panel>

            <Panel title="AI Backbone Access" subtitle="Choose whether customer runs use the shared OpenClaw backbone, a customer-provided API key, or the connector-backed GPT OAuth path.">
              <form className="space-y-5" onSubmit={handleAiBackboneSave}>
                <div className="grid gap-3">
                  {AI_BACKBONE_OPTIONS.map((option) => (
                    <label
                      key={option.value}
                      className={`cursor-pointer rounded-3xl border p-4 transition ${
                        aiBackboneForm.accessMode === option.value
                          ? "border-emerald-300 bg-emerald-200/10"
                          : "border-white/10 bg-black/20 hover:border-white/20"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="radio"
                          name="ai-backbone-access-mode"
                          checked={aiBackboneForm.accessMode === option.value}
                          onChange={() =>
                            setAiBackboneForm((current) => ({
                              ...current,
                              accessMode: option.value,
                            }))
                          }
                          className="mt-1 h-4 w-4 border-white/30 bg-slate-950 text-emerald-300 focus:ring-emerald-300"
                        />
                        <div>
                          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-white">
                            {option.title}
                          </p>
                          <p className="mt-2 text-sm text-stone-300">
                            {option.description}
                          </p>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>

                <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-emerald-200/80">
                        Effective Status
                      </p>
                      <p className="mt-2 text-sm text-stone-200">
                        {aiBackbone.effective_status.message}
                      </p>
                    </div>
                    <StatusBadge
                      label={aiBackbone.effective_status.ready ? "ready" : "attention"}
                    />
                  </div>
                </div>

                {aiBackboneForm.accessMode === "customer_api_key" && (
                  <div className="grid gap-4">
                    <Field
                      label="Customer OpenClaw URL"
                      value={aiBackboneForm.customerApiUrl}
                      onChange={(value) =>
                        setAiBackboneForm((current) => ({
                          ...current,
                          customerApiUrl: value,
                        }))
                      }
                      placeholder={aiBackbone.platform_managed.api_url}
                    />
                    <Field
                      label="Customer OpenClaw API Key"
                      value={aiBackboneForm.customerApiKey}
                      onChange={(value) =>
                        setAiBackboneForm((current) => ({
                          ...current,
                          customerApiKey: value,
                        }))
                      }
                      type="password"
                      placeholder={
                        aiBackbone.customer_api.has_api_key
                          ? "Saved key on file. Leave blank to keep it."
                          : "Paste the customer OpenClaw API key"
                      }
                    />
                    {aiBackbone.customer_api.has_api_key && (
                      <p className="text-xs text-stone-400">
                        A customer API key is already stored. Leave the field blank to keep the existing secret.
                      </p>
                    )}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={
                    busyKey === "ai-backbone" ||
                    (aiBackboneForm.accessMode === "chatgpt_oauth" &&
                      !aiBackbone.chatgpt_oauth.session_ready)
                  }
                  className="w-full rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {busyKey === "ai-backbone"
                    ? "Saving..."
                    : aiBackboneForm.accessMode === "chatgpt_oauth"
                      ? "Use Linked GPT OAuth"
                      : "Save AI Backbone"}
                </button>
              </form>

              <form className="mt-5 space-y-4 rounded-3xl border border-cyan-300/15 bg-cyan-300/5 p-4" onSubmit={handleLinkChatgptOAuth}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-cyan-100/80">
                      GPT OAuth Link
                    </p>
                    <p className="mt-2 text-sm text-stone-200">
                      {aiBackbone.chatgpt_oauth.linked
                        ? `${aiBackbone.chatgpt_oauth.chatgpt_subject || "Linked GPT account"} connected`
                        : "No GPT Plus or Pro account linked yet."}
                    </p>
                  </div>
                  <StatusBadge
                    label={
                      aiBackbone.chatgpt_oauth.session_ready
                        ? "linked"
                        : aiBackbone.chatgpt_oauth.linked
                          ? "reconnect"
                          : "not_linked"
                    }
                  />
                </div>

                <Field
                  label="ChatGPT Account"
                  value={aiBackboneForm.chatgptSubject}
                  onChange={(value) =>
                    setAiBackboneForm((current) => ({
                      ...current,
                      chatgptSubject: value,
                    }))
                  }
                  placeholder="customer@company.com"
                />
                <Field
                  label="Display Name"
                  value={aiBackboneForm.chatgptDisplayName}
                  onChange={(value) =>
                    setAiBackboneForm((current) => ({
                      ...current,
                      chatgptDisplayName: value,
                    }))
                  }
                  placeholder={user?.name || user?.email || "Customer name"}
                />
                <SelectField
                  label="Subscription Tier"
                  value={aiBackboneForm.chatgptSubscriptionTier}
                  onChange={(value) =>
                    setAiBackboneForm((current) => ({
                      ...current,
                      chatgptSubscriptionTier: value as "plus" | "pro",
                    }))
                  }
                  options={[
                    { value: "plus", label: "GPT Plus" },
                    { value: "pro", label: "GPT Pro" },
                  ]}
                />

                <div className="grid gap-3 sm:grid-cols-2">
                  <button
                    type="submit"
                    disabled={busyKey === "chatgpt-link"}
                    className="rounded-full bg-cyan-200 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busyKey === "chatgpt-link" ? "Linking..." : "Link GPT OAuth"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDisconnectChatgptOAuth()}
                    disabled={
                      busyKey === "chatgpt-disconnect" ||
                      !aiBackbone.chatgpt_oauth.linked
                    }
                    className="rounded-full border border-rose-300/30 px-4 py-3 text-sm font-semibold text-rose-200 transition hover:border-rose-200 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busyKey === "chatgpt-disconnect"
                      ? "Disconnecting..."
                      : "Disconnect GPT OAuth"}
                  </button>
                </div>

                {aiBackbone.chatgpt_oauth.session_expires_at && (
                  <p className="text-xs text-stone-400">
                    Session expires at {new Date(aiBackbone.chatgpt_oauth.session_expires_at).toUTCString()}.
                  </p>
                )}
              </form>
            </Panel>

            <Panel title="Connected Accounts" subtitle="Official OAuth-first account links for customer-owned publishing.">
              <div className="grid gap-3">
                {SUPPORTED_PLATFORMS.map((platform) => {
                  const account = accounts.find((item) => item.platform === platform);
                  return (
                    <div key={platform} className="rounded-3xl border border-white/10 bg-black/20 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-lg font-medium capitalize text-white">{platform}</p>
                          <p className="text-sm text-stone-400">
                            {account
                              ? account.display_name || account.account_handle || "Connected"
                              : "Not connected yet"}
                          </p>
                        </div>
                        <StatusBadge label={account?.connection_status || "disconnected"} />
                      </div>
                      <div className="mt-4 flex gap-2">
                        {!account || account.connection_status !== "connected" ? (
                          <button
                            type="button"
                            onClick={() => void handleConnect(platform)}
                            disabled={busyKey === `connect-${platform}`}
                            className="rounded-full bg-emerald-300 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-950 transition hover:bg-emerald-200"
                          >
                            Connect
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => void handleDisconnect(account.id)}
                            disabled={busyKey === `disconnect-${account.id}`}
                            className="rounded-full border border-rose-300/30 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-rose-200 transition hover:border-rose-200"
                          >
                            Disconnect
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Panel>

            <Panel title="Content Queue" subtitle="Customer-safe publish state pulled from persisted content records.">
              <div className="space-y-3">
                {content.length === 0 && (
                  <p className="text-sm text-stone-400">
                    Content will appear here once a campaign starts generating output.
                  </p>
                )}
                {content.map((item) => (
                  <div key={item.id} className="rounded-3xl border border-white/10 bg-black/20 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="font-medium text-white">{item.title}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.16em] text-stone-500">
                          {item.platform.join(" • ") || "No platform"}
                        </p>
                      </div>
                      <StatusBadge label={item.status} />
                    </div>
                    {item.scheduled_at && (
                      <p className="mt-2 text-sm text-stone-400">
                        Scheduled for {new Date(item.scheduled_at).toUTCString()}
                      </p>
                    )}
                    {item.published_at && (
                      <p className="mt-2 text-sm text-emerald-200">
                        Published at {new Date(item.published_at).toUTCString()}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </Panel>
          </section>
        </div>
      </div>
    </main>
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
        <p className="text-xs uppercase tracking-[0.24em] text-emerald-200/70">
          {title}
        </p>
        <p className="mt-2 max-w-2xl text-sm text-stone-400">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function TelegramDetail({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-stone-400">
        {label}
      </p>
      <p className="mt-2 text-sm text-stone-200">{value}</p>
    </div>
  );
}

function TelegramStep({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <p className="text-sm font-semibold text-white">{title}</p>
      <p className="mt-2 text-sm text-stone-300">{description}</p>
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
      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-stone-400">
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-emerald-300"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-stone-400">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-emerald-300"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
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
      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-stone-400">
        {label}
      </span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[92px] w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-emerald-300"
      />
    </label>
  );
}

function StatusBadge({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-stone-200">
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

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatTelegramContact(value?: string | null): string | null {
  const normalized = value?.trim();
  if (!normalized) {
    return null;
  }
  if (
    normalized.startsWith("@") ||
    normalized.startsWith("http://") ||
    normalized.startsWith("https://") ||
    normalized.startsWith("t.me/")
  ) {
    return normalized;
  }
  return `@${normalized}`;
}

function buildTelegramBotUrl(): string | null {
  const explicitUrl = process.env.NEXT_PUBLIC_TELEGRAM_BOT_URL?.trim();
  if (explicitUrl) {
    return explicitUrl;
  }

  const username = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME?.trim();
  if (!username) {
    return null;
  }

  return `https://t.me/${username.replace(/^@/, "")}`;
}
