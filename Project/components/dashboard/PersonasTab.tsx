"use client";

import React, { useState } from "react";
import {
  Plus,
  Search,
  ArrowUp,
  Brain,
  Sparkles,
  Video,
  Share2,
  Loader2,
  X,
  Link,
  RefreshCw,
  Check,
  AlertTriangle,
  Globe,
  Mic,
  Palette,
  Clock,
  Activity,
  ChevronRight,
  ExternalLink,
  CheckCircle2,
} from "lucide-react";
import { customerApiRequest } from "@/lib/customer-api";
import { cn } from "@/lib/utils";
import { PersonaGroup } from "./personas/PersonaGroup";
import { PersonaSkeleton } from "./personas/PersonaSkeleton";
import { PersonaStudioPanel } from "./personas/PersonaStudioPanel";
import type {
  PersonaStudioAction,
  PersonaStudioSessionState,
} from "@/types/persona-studio";

/* ── Types ────────────────────────────────────────────────────────────────── */

interface Persona {
  persona_id: string;
  display_name: string;
  avatar_image_url: string | null;
  status: string;
  video_count: number;
  location?: string;
  tts_voice?: string;
  language?: string;
  appearance_prompt_or_photo?: string;
  selection_image_url?: string | null;
  region_label?: string | null;
  description?: string | null;
  market_default?: string | null;
  tone_default?: string | null;
  is_preset_catalog?: boolean;
  user_id?: string | null;
  gender?: string | null;
  channel_configs?: Record<string, any> | null;
}

interface PersonasTabProps {
  defaultPersonas: Persona[];
  userPersonas: Persona[];
  telegramBotUrl?: string | null;
  onNavigateToCreateVideo?: () => void;
  onRefreshPersonas?: () => Promise<void>;
}

type TikTokConnectionState = "connected_demo" | "not_connected" | "needs_reconnect";
type TikTokActiveState = "active" | "inactive";

interface TikTokChannelStatus {
  activeState: TikTokActiveState;
  connectionState: TikTokConnectionState;
  channelHandle?: string;
  displayName?: string;
  lastSyncLabel?: string;
}

/* ── Demo TikTok Adapter ────────────────────────────────────────────────────
   In Phase 3: replace body of toTikTokChannelStatus() with real API mapping.
   Component interface stays unchanged.
  ──────────────────────────────────────────────────────────────────────────── */
function toTikTokChannelStatus(persona: Persona): TikTokChannelStatus {
  const demoFixtures: Record<string, TikTokChannelStatus> = {
    default: {
      activeState: "active",
      connectionState: "connected_demo",
      channelHandle: `@${persona.display_name.toLowerCase().replace(/\s+/g, "_")}_tt`,
      displayName: persona.display_name,
      lastSyncLabel: "2 hours ago",
    },
  };
  return demoFixtures[persona.persona_id] ?? demoFixtures.default;
}

/* ── Main Component ─────────────────────────────────────────────────────── */

export function PersonasTab({
  defaultPersonas,
  userPersonas,
  onNavigateToCreateVideo,
  onRefreshPersonas,
}: PersonasTabProps) {
  // Combine personas for backward compatibility with existing logic
  const personas = [...defaultPersonas, ...userPersonas];

  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(
    personas[0]?.persona_id ?? null
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreationOpen, setIsCreationOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingPersonas, setIsLoadingPersonas] = useState(false);
  const [editForm, setEditForm] = useState({
    display_name: "",
    tts_voice: "",
    appearance_prompt_or_photo: "",
    gender: "",
    tiktok_username: "",
    youtube_channel_id: "",
  });

  const [isSaving, setIsSaving] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [tiktokBannerMsg, setTiktokBannerMsg] = useState<string | null>(null);
  // TikTok Manage Modal
  const [isTiktokModalOpen, setIsTiktokModalOpen] = useState(false);
  const [tiktokUrlDraft, setTiktokUrlDraft] = useState("");
  const [composer, setComposer] = useState("");
  const [studioState, setStudioState] = useState<PersonaStudioSessionState | null>(null);
  const [studioError, setStudioError] = useState<string | null>(null);
  const [isStudioBusy, setIsStudioBusy] = useState(false);
  const [draftSaved, setDraftSaved] = useState(false);

  React.useEffect(() => {
    const selected = personas.find((p) => p.persona_id === selectedPersonaId);
    if (selected) {
      setEditForm({
        display_name: selected.display_name || "",
        tts_voice: selected.tts_voice || "",
        appearance_prompt_or_photo: selected.appearance_prompt_or_photo || "",
        gender: selected.gender || "",
        tiktok_username: selected.channel_configs?.tiktok?.username || "",
        youtube_channel_id: selected.channel_configs?.youtube?.channel_id || "",
      });
      setIsEditing(false);
    }
  }, [selectedPersonaId, personas]);

  React.useEffect(() => {
    if (!selectedPersonaId && personas[0]?.persona_id) {
      setSelectedPersonaId(personas[0].persona_id);
      return;
    }
    if (
      selectedPersonaId &&
      !personas.some((persona) => persona.persona_id === selectedPersonaId)
    ) {
      setSelectedPersonaId(personas[0]?.persona_id ?? null);
    }
  }, [personas, selectedPersonaId]);

  const handleSave = async () => {
    if (!selectedPersonaId) return;
    setIsSaving(true);
    try {
      const payload = {
        ...editForm,
        channel_configs: {
          tiktok: { username: editForm.tiktok_username },
          youtube: { channel_id: editForm.youtube_channel_id },
        }
      };
      
      await customerApiRequest<any>(`/api/customer/personas/${selectedPersonaId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setIsEditing(false);
      await onRefreshPersonas?.();
    } catch (e: any) {
      alert("Error saving adjustments: " + e.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRebuildAvatar = async () => {
    if (!selectedPersonaId) return;
    setIsRebuilding(true);
    try {
      await customerApiRequest<any>(
        `/api/customer/personas/${selectedPersonaId}/rebuild-avatar`,
        {
          method: "POST",
          body: JSON.stringify({
            appearance_prompt_or_photo: editForm.appearance_prompt_or_photo,
          }),
        }
      );
      setIsEditing(false);
      await onRefreshPersonas?.();
    } catch (e: any) {
      alert("Error rebuilding avatar: " + e.message);
    } finally {
      setIsRebuilding(false);
    }
  };

  const filteredPersonas = personas.filter((p) =>
    p.display_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedPersona = personas.find((p) => p.persona_id === selectedPersonaId);
  const tiktokStatus = selectedPersona ? toTikTokChannelStatus(selectedPersona) : null;

  const tiktokActionLabel = (() => {
    if (!tiktokStatus) return "";
    if (tiktokStatus.activeState === "inactive") return "Activate Channel";
    if (tiktokStatus.connectionState === "not_connected") return "Connect TikTok";
    if (tiktokStatus.connectionState === "needs_reconnect") return "Reconnect TikTok";
    return "View Connection Details";
  })();

  const handleTiktokAction = () => {
    setTiktokBannerMsg(
      "This action will be available once the backend integration is complete."
    );
  };

  const handleOpenTiktokManage = () => {
    setTiktokUrlDraft(tiktokStatus?.channelHandle ?? "");
    setIsTiktokModalOpen(true);
  };

  const handleTiktokModalSave = () => {
    // Phase 1: demo no-op — show inline confirmation then close
    setTiktokBannerMsg("Channel settings saved (demo). Backend integration pending.");
    setIsTiktokModalOpen(false);
  };

  const runStudioMutation = async (
    operation: () => Promise<PersonaStudioSessionState>,
  ) => {
    setIsStudioBusy(true);
    setStudioError(null);
    try {
      const nextState = await operation();
      setStudioState(nextState);
      return nextState;
    } catch (error) {
      setStudioError(
        error instanceof Error ? error.message : "Persona studio request failed",
      );
      throw error;
    } finally {
      setIsStudioBusy(false);
    }
  };

  const handleOpenStudio = async () => {
    setIsCreationOpen(true);
    setDraftSaved(false);
    if (studioState) {
      return;
    }
    try {
      await runStudioMutation(() =>
        customerApiRequest<PersonaStudioSessionState>(
          "/api/customer/persona-studio/sessions",
          {
            method: "POST",
            body: JSON.stringify({}),
          },
        ),
      );
    } catch {}
  };

  const handleStudioText = async (content: string) => {
    if (!studioState?.session_id) return;
    setDraftSaved(false);
    try {
      await runStudioMutation(() =>
        customerApiRequest<PersonaStudioSessionState>(
          `/api/customer/persona-studio/sessions/${studioState.session_id}/messages`,
          {
            method: "POST",
            body: JSON.stringify({
              kind: "text",
              content,
            }),
          },
        ),
      );
    } catch {}
  };

  const handleStudioAction = async (action: PersonaStudioAction) => {
    if (!studioState?.session_id) return;
    setDraftSaved(false);
    try {
      await runStudioMutation(() =>
        customerApiRequest<PersonaStudioSessionState>(
          `/api/customer/persona-studio/sessions/${studioState.session_id}/messages`,
          {
            method: "POST",
            body: JSON.stringify({
              kind: "action",
              action: action.value,
              value: action.value,
            }),
          },
        ),
      );
    } catch {}
  };

  const handleSaveDraft = async () => {
    if (!studioState?.session_id) return;
    try {
      await runStudioMutation(() =>
        customerApiRequest<PersonaStudioSessionState>(
          `/api/customer/persona-studio/sessions/${studioState.session_id}/commit`,
          {
            method: "POST",
            body: JSON.stringify({
              mode: "save_draft",
            }),
          },
        ),
      );
      setDraftSaved(true);
    } catch {}
  };

  const handleFinalizeStudio = async () => {
    if (!studioState?.session_id || !studioState.can_finalize) return;
    let nextState: PersonaStudioSessionState | null = null;
    try {
      nextState = await runStudioMutation(() =>
        customerApiRequest<PersonaStudioSessionState>(
          `/api/customer/persona-studio/sessions/${studioState.session_id}/commit`,
          {
            method: "POST",
            body: JSON.stringify({
              mode: "finalize",
            }),
          },
        ),
      );
    } catch {
      return;
    }
    if (!nextState) return;
    const personaId =
      typeof nextState.persona?.persona_id === "string"
        ? nextState.persona.persona_id
        : null;
    await onRefreshPersonas?.();
    if (personaId) {
      setSelectedPersonaId(personaId);
    }
    setStudioState(null);
    setDraftSaved(false);
    setIsCreationOpen(false);
  };

  return (
    <div className="relative flex h-full max-h-[calc(100vh-120px)] flex-col gap-4 overflow-hidden animate-fade-in lg:flex-row">
      {/* ─── Left: Persona List ─────────────────────────────────────── */}
      <section className="w-full flex flex-col gap-4 overflow-hidden lg:w-72 lg:flex-shrink-0">
        <div className="dashboard-panel-soft flex-1 flex flex-col overflow-hidden p-6">
          {/* Header */}
          <div className="flex justify-between items-center mb-5">
            <div>
              <h3 className="text-xl font-black text-aura-on-surface font-headline">
                Your Personas
              </h3>
              <p className="text-xs text-aura-on-surface-variant/60 font-body mt-0.5">
                {personas.length} influencer{personas.length !== 1 ? "s" : ""} configured
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleOpenStudio()}
              aria-label="Create new persona"
              className="w-10 h-10 rounded-full bg-aura-primary text-white flex items-center justify-center shadow-lg hover:bg-aura-primary-hover transition-colors cursor-pointer min-h-[44px] min-w-[44px]"
            >
              <Plus className="w-5 h-5" />
            </button>
          </div>

          {/* Search */}
          <div className="relative mb-5 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-aura-on-surface-variant/50 group-focus-within:text-aura-primary transition-colors" />
            <label className="sr-only" htmlFor="persona-search">
              Search personas
            </label>
            <input
              id="persona-search"
              name="personaSearch"
              type="search"
              autoComplete="off"
              placeholder="Search personas…"
              className="w-full py-3 pl-11 pr-4 text-sm font-medium bg-aura-surface-container rounded-2xl border border-aura-outline-variant/20 focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Persona Groups with Expandable Sections */}
          <div className="flex-1 overflow-y-auto scrollbar-hide space-y-4 pr-1">
            {/* Default Personas Group */}
            <PersonaGroup
              title="System Personas"
              subtitle="AI-powered defaults"
              personas={defaultPersonas}
              selectedPersonaId={selectedPersonaId}
              onSelectPersona={setSelectedPersonaId}
              isExpandedByDefault={true}
              isLoading={isLoadingPersonas}
            >
              {isLoadingPersonas ? (
                <>
                  {Array.from({ length: 2 }).map((_, i) => (
                    <PersonaSkeleton key={`default-skeleton-${i}`} />
                  ))}
                </>
              ) : (
                defaultPersonas.map((p) => (
                  <PersonaListItem
                    key={p.persona_id}
                    persona={p}
                    isActive={selectedPersonaId === p.persona_id}
                    onClick={() => setSelectedPersonaId(p.persona_id)}
                  />
                ))
              )}
            </PersonaGroup>

            {/* User Personas Group */}
            <PersonaGroup
              title="Your Personas"
              subtitle="Custom influencers"
              personas={userPersonas}
              selectedPersonaId={selectedPersonaId}
              onSelectPersona={setSelectedPersonaId}
              isExpandedByDefault={true}
              isLoading={isLoadingPersonas}
            >
              {isLoadingPersonas ? (
                <>
                  {Array.from({ length: 2 }).map((_, i) => (
                    <PersonaSkeleton key={`user-skeleton-${i}`} />
                  ))}
                </>
              ) : userPersonas.length === 0 ? (
                <div className="py-8 text-center space-y-2">
                  <p className="text-xs text-aura-on-surface-variant font-body">
                    No custom personas yet.
                  </p>
                  <button
                    type="button"
                    onClick={() => void handleOpenStudio()}
                    className="text-xs text-aura-primary font-bold hover:underline cursor-pointer"
                  >
                    Create one
                  </button>
                </div>
              ) : (
                userPersonas.map((p) => (
                  <PersonaListItem
                    key={p.persona_id}
                    persona={p}
                    isActive={selectedPersonaId === p.persona_id}
                    onClick={() => setSelectedPersonaId(p.persona_id)}
                  />
                ))
              )}
            </PersonaGroup>

            {/* Create new dashed button */}
            <button
              type="button"
              onClick={() => void handleOpenStudio()}
              className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-aura-outline-variant/30 p-4 text-sm font-bold text-aura-on-surface-variant transition-all hover:border-aura-primary/40 hover:bg-aura-primary/5 cursor-pointer min-h-[44px] group mt-2"
            >
              <Plus className="w-4 h-4 text-aura-primary group-hover:scale-110 transition-transform" />
              Build New Persona
            </button>
          </div>
        </div>
      </section>

      {/* ─── Right: Detail Panel ────────────────────────────────────── */}
      <section className="flex h-full w-full min-h-0 flex-1 flex-col gap-5 overflow-y-auto scrollbar-hide pb-4">
        {selectedPersona ? (
          <div className="space-y-5 animate-fade-in">
            {/* ── Persona Hero Card ─────────────────────────────────── */}
            <div className="dashboard-panel p-8 flex flex-col gap-6 md:flex-row md:items-start md:gap-8">
              <div className="relative shrink-0">
                <img
                  src={selectedPersona.avatar_image_url || "/placeholder-avatar.png"}
                  alt={selectedPersona.display_name}
                  width={96}
                  height={96}
                  className="w-24 h-24 rounded-[1.75rem] object-cover ring-4 ring-aura-primary/10 shadow-lg"
                />
                {selectedPersona.status === "active" && (
                  <span className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-emerald-500 border-4 border-white rounded-full" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-black text-aura-on-surface font-headline leading-tight">
                      {selectedPersona.display_name}
                    </h2>
                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                      <span
                        className={cn(
                          "px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-widest border font-label",
                          selectedPersona.status === "active"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : "bg-aura-surface-container text-aura-on-surface-variant border-aura-outline-variant/30"
                        )}
                      >
                        {selectedPersona.status}
                      </span>
                      <span className="text-xs text-aura-on-surface-variant font-body">
                        {selectedPersona.video_count} videos generated
                      </span>
                      {selectedPersona.location && (
                        <span className="flex items-center gap-1 text-xs text-aura-on-surface-variant/60 font-body">
                          <Globe className="w-3 h-3" />
                          {selectedPersona.location}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-3">
                    {isEditing ? (
                      <button
                        type="button"
                        onClick={() => setIsEditing(false)}
                        className="btn-secondary btn-sm"
                        aria-label="Cancel editing"
                      >
                        Cancel
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setIsEditing(true)}
                        className="btn-secondary btn-sm"
                        aria-label="Edit persona metadata"
                      >
                        Edit Core
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={onNavigateToCreateVideo}
                      className="btn-primary btn-sm"
                      aria-label="Generate video with this persona"
                    >
                      Generate Video
                    </button>
                  </div>
                </div>

                {/* Metadata row */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-6">
                  <MetaChip
                    icon={<Mic className="w-3.5 h-3.5" />}
                    label="Voice"
                    value={selectedPersona.tts_voice || "Default"}
                  />
                  <MetaChip
                    icon={<Globe className="w-3.5 h-3.5" />}
                    label="Language"
                    value={selectedPersona.language || "Auto"}
                  />
                  <MetaChip
                    icon={<Video className="w-3.5 h-3.5" />}
                    label="Videos"
                    value={String(selectedPersona.video_count)}
                  />
                </div>
              </div>
            </div>

            {/* ── Edit Form (conditional) ────────────────────────────── */}
            {isEditing && (
              <div className="dashboard-panel p-8 space-y-6 animate-fade-in">
                <h3 className="text-sm font-black uppercase tracking-widest text-aura-on-surface-variant font-label">
                  Edit Persona Core
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="block text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant font-label">
                      Persona Name
                    </label>
                    <input
                      type="text"
                      aria-label="Persona display name"
                      className="w-full py-3 px-4 rounded-2xl bg-aura-surface-container border border-aura-outline-variant/20 font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all text-sm"
                      value={editForm.display_name}
                      onChange={(e) =>
                        setEditForm({ ...editForm, display_name: e.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant font-label">
                      TTS Voice
                      <span className="ml-2 text-aura-on-surface-variant/50 normal-case tracking-normal font-normal">
                        (Google Cloud TTS format)
                      </span>
                    </label>
                    <input
                      type="text"
                      aria-label="Text-to-speech voice"
                      placeholder="e.g. en-US-Journey-F"
                      className="w-full py-3 px-4 rounded-2xl bg-aura-surface-container border border-aura-outline-variant/20 font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all text-sm"
                      value={editForm.tts_voice}
                      onChange={(e) =>
                        setEditForm({ ...editForm, tts_voice: e.target.value })
                      }
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="block text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant font-label">
                      Gender
                    </label>
                    <select
                      aria-label="Persona Gender"
                      className="w-full py-3 px-4 rounded-2xl bg-aura-surface-container border border-aura-outline-variant/20 font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all text-sm appearance-none"
                      value={editForm.gender}
                      onChange={(e) =>
                        setEditForm({ ...editForm, gender: e.target.value })
                      }
                    >
                      <option value="">Auto Select / Not specified</option>
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant font-label">
                      Channel Settings
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        aria-label="TikTok Username"
                        placeholder="@tiktok_user"
                        className="w-1/2 py-3 px-4 rounded-2xl bg-aura-surface-container border border-aura-outline-variant/20 font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all text-sm"
                        value={editForm.tiktok_username}
                        onChange={(e) =>
                          setEditForm({ ...editForm, tiktok_username: e.target.value })
                        }
                      />
                      <input
                        type="text"
                        aria-label="YouTube Channel ID"
                        placeholder="YouTube ID"
                        className="w-1/2 py-3 px-4 rounded-2xl bg-aura-surface-container border border-aura-outline-variant/20 font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all text-sm"
                        value={editForm.youtube_channel_id}
                        onChange={(e) =>
                          setEditForm({ ...editForm, youtube_channel_id: e.target.value })
                        }
                      />
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="block text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant font-label">
                    Appearance / Visual Prompt
                  </label>
                  <textarea
                    aria-label="Appearance prompt or photo URL"
                    className="w-full py-3 px-4 rounded-2xl bg-aura-surface-container border border-aura-outline-variant/20 font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all text-sm h-28 resize-none"
                    placeholder="Describe the visual identity…"
                    value={editForm.appearance_prompt_or_photo}
                    onChange={(e) =>
                      setEditForm({
                        ...editForm,
                        appearance_prompt_or_photo: e.target.value,
                      })
                    }
                  />
                </div>
                <div className="flex flex-wrap gap-4 pt-2">
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={isSaving || isRebuilding}
                    className="btn-primary min-w-[140px] flex items-center gap-2 disabled:opacity-50"
                    aria-label="Save persona adjustments"
                  >
                    {isSaving ? (
                      <Loader2 className="w-5 h-5 animate-spin mx-auto" />
                    ) : (
                      <>
                        <Check className="w-4 h-4" />
                        Save Adjustments
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={handleRebuildAvatar}
                    disabled={isSaving || isRebuilding}
                    className="btn-secondary min-w-[140px] flex items-center gap-2 disabled:opacity-50"
                    aria-label="Rebuild avatar via HeyGen"
                  >
                    {isRebuilding ? (
                      <Loader2 className="w-5 h-5 animate-spin mx-auto" />
                    ) : (
                      <>
                        <RefreshCw className="w-4 h-4" />
                        Rebuild Avatar
                      </>
                    )}
                  </button>
                  <p className="text-xs text-aura-on-surface-variant/60 font-body self-center">
                    Rebuild prompts HeyGen to recreate this persona. May take 60s.
                  </p>
                </div>
              </div>
            )}



            {/* ── TikTok Channel Card ────────────────────────────────── */}
            {tiktokStatus && (
              <TikTokChannelCard
                status={tiktokStatus}
                actionLabel={tiktokActionLabel}
                onAction={handleTiktokAction}
                onManage={handleOpenTiktokManage}
                bannerMessage={tiktokBannerMsg}
                onDismissBanner={() => setTiktokBannerMsg(null)}
              />
            )}

            {/* ── Channel Integration Summary ────────────────────────── */}
            {!isEditing && (
              <div className="dashboard-panel p-8 space-y-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-black uppercase tracking-widest text-aura-on-surface-variant font-label">
                    Platform Connections
                  </h3>
                  <button
                    type="button"
                    aria-label="Manage integrations"
                    className="text-xs text-aura-primary font-bold hover:underline underline-offset-2 flex items-center gap-1 min-h-[44px] px-2 cursor-pointer transition-colors"
                  >
                    Manage <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
                <div className="space-y-3">
                  <IntegrationRow
                    name="TikTok"
                    handle={tiktokStatus?.channelHandle ?? "Not configured"}
                    state={tiktokStatus?.connectionState ?? "not_connected"}
                  />
                  <IntegrationRow
                    name="YouTube Shorts"
                    handle="Coming soon"
                    state="not_connected"
                    comingSoon
                  />
                  <IntegrationRow
                    name="Instagram Reels"
                    handle="Coming soon"
                    state="not_connected"
                    comingSoon
                  />
                </div>
              </div>
            )}

            {/* ── Knowledge Base CTA ─────────────────────────────────── */}
            {!isEditing && (
              <button
                type="button"
                className="dashboard-panel-soft flex aspect-[21/9] w-full items-center justify-center border-2 border-dashed border-aura-outline-variant/30 bg-aura-surface-container-highest/20 transition-all group hover:bg-aura-surface-container-highest/30 cursor-pointer rounded-3xl"
                aria-label="View training knowledge base"
              >
                <div className="text-center space-y-3">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-white shadow-lg transition-transform group-hover:scale-110">
                    <Sparkles className="w-7 h-7 text-aura-primary" />
                  </div>
                  <p className="font-bold text-aura-on-surface text-sm">
                    View Training Knowledge Base
                  </p>
                  <p className="text-xs text-aura-on-surface-variant/60 font-body">
                    Data this persona learns from
                  </p>
                </div>
              </button>
            )}
          </div>
        ) : (
          /* ── Empty / No persona selected ───────────────────────────── */
          <div className="flex flex-1 h-full items-center justify-center">
            <div className="text-center space-y-4 max-w-sm">
              <div className="w-16 h-16 rounded-3xl bg-aura-surface-container mx-auto flex items-center justify-center">
                <Share2 className="w-8 h-8 text-aura-on-surface-variant/40" />
              </div>
              <p className="text-aura-on-surface font-bold">Select a persona</p>
              <p className="text-sm text-aura-on-surface-variant/60 font-body">
                Choose a persona from the list to view and manage their details.
              </p>
            </div>
          </div>
        )}
      </section>

      {/* ── TikTok Manage Modal ─────────────────────────────────────── */}
      {isTiktokModalOpen && (
        <>
          <div
            className="fixed inset-0 z-50 bg-aura-on-surface/30 backdrop-blur-sm animate-fade-in"
            onClick={() => setIsTiktokModalOpen(false)}
            aria-hidden="true"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Manage TikTok channel"
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg animate-fade-in p-8 space-y-6">
              {/* Modal header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-11 h-11 rounded-xl bg-aura-on-surface flex items-center justify-center shrink-0">
                    <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                      <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.32 6.32 0 0 0-.79-.05A6.34 6.34 0 0 0 3.15 15.3a6.34 6.34 0 0 0 6.34 6.35 6.34 6.34 0 0 0 6.33-6.35V8.89a8.27 8.27 0 0 0 4.83 1.54V7a4.85 4.85 0 0 1-1.06-.31Z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-black text-aura-on-surface font-headline">Manage TikTok Channel</h3>
                    <p className="text-xs text-aura-on-surface-variant font-body mt-0.5">
                      {selectedPersona?.display_name}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsTiktokModalOpen(false)}
                  aria-label="Close modal"
                  className="w-10 h-10 rounded-full bg-aura-surface-container text-aura-on-surface-variant hover:bg-aura-surface-container-high transition-colors flex items-center justify-center cursor-pointer min-h-[44px]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Form fields */}
              <div className="space-y-5">
                <div className="space-y-2">
                  <label htmlFor="tiktok-handle" className="block text-xs font-black uppercase tracking-widest text-aura-on-surface-variant font-label">
                    TikTok Handle
                  </label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-aura-on-surface-variant/50 font-bold text-sm">@</span>
                    <input
                      id="tiktok-handle"
                      type="text"
                      autoComplete="off"
                      placeholder="your_channel_handle"
                      value={tiktokUrlDraft.replace(/^@/, "")}
                      onChange={(e) => setTiktokUrlDraft("@" + e.target.value.replace(/^@/, ""))}
                      className="w-full pl-8 pr-4 py-3 rounded-2xl bg-aura-surface-container border border-aura-outline-variant/20 text-sm font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all"
                      aria-label="TikTok channel handle"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="tiktok-profile-url" className="block text-xs font-black uppercase tracking-widest text-aura-on-surface-variant font-label">
                    Profile URL
                    <span className="ml-2 text-aura-on-surface-variant/50 normal-case tracking-normal font-normal">optional</span>
                  </label>
                  <input
                    id="tiktok-profile-url"
                    type="url"
                    autoComplete="url"
                    placeholder="https://www.tiktok.com/@handle"
                    className="w-full px-4 py-3 rounded-2xl bg-aura-surface-container border border-aura-outline-variant/20 text-sm font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all"
                    aria-label="TikTok profile URL"
                  />
                </div>

                <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl">
                  <p className="text-xs text-amber-800 font-medium leading-relaxed">
                    Channel settings are saved locally (demo). Full TikTok OAuth integration is available in Phase 3.
                  </p>
                </div>
              </div>

              {/* Modal actions */}
              <div className="flex gap-3 justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setIsTiktokModalOpen(false)}
                  className="btn-secondary btn-sm"
                  aria-label="Cancel"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleTiktokModalSave}
                  className="btn-primary flex items-center gap-2 min-h-[44px]"
                  aria-label="Save TikTok channel settings"
                >
                  <Check className="w-4 h-4" />
                  Save Settings
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Creation Studio Slide Drawer ────────────────────────────── */}
      {false && isCreationOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40 bg-aura-on-surface/20 backdrop-blur-sm animate-fade-in"
            onClick={() => setIsCreationOpen(false)}
            aria-hidden="true"
          />
          {/* Drawer */}
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Create new persona"
            className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-2xl bg-white shadow-2xl flex flex-col animate-slide-in border-l border-aura-outline-variant/10"
          >
            {/* Drawer Header */}
            <div className="flex items-center justify-between p-8 border-b border-aura-outline-variant/10 bg-aura-surface-container-lowest">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-aura-primary/10 flex items-center justify-center">
                  <Brain className="w-6 h-6 text-aura-primary" />
                </div>
                <div>
                  <h2 className="text-xl font-black text-aura-on-surface font-headline leading-tight">
                    Creation Studio
                  </h2>
                  <p className="text-xs text-aura-on-surface-variant font-bold uppercase tracking-widest mt-0.5">
                    Co-creating with OpenClaw Engine
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  aria-label="Save draft"
                >
                  Save Draft
                </button>
                <button
                  type="button"
                  className="btn-primary btn-sm"
                  aria-label="Finalize AI persona"
                >
                  Finalize Persona
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreationOpen(false)}
                  aria-label="Close creation studio"
                  className="w-10 h-10 rounded-full bg-aura-surface-container text-aura-on-surface-variant hover:bg-aura-surface-container-high transition-colors flex items-center justify-center cursor-pointer min-h-[44px]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-8 space-y-8 scrollbar-hide">
              {/* AI opener */}
              <div className="flex gap-4">
                <div className="w-9 h-9 rounded-xl bg-aura-primary shrink-0 mt-1 flex items-center justify-center text-[10px] text-white font-black shadow-lg">
                  OC
                </div>
                <div className="bg-aura-surface-container-low rounded-3xl rounded-tl-none p-6 border border-aura-outline-variant/5 shadow-sm max-w-xl">
                  <p className="text-base leading-relaxed text-aura-on-surface font-medium">
                    Hello! I'm OpenClaw AI. Let's design your next digital icon.{" "}
                    <span className="text-aura-primary font-black">
                      What kind of aesthetic or "vibe" should your new persona radiate?
                    </span>
                  </p>
                  <div className="mt-5 flex flex-wrap gap-2">
                    {["High-Fashion Ethereal", "Cyberpunk Gamer", "Mindful Wellness"].map(
                      (label) => (
                        <button
                          key={label}
                          type="button"
                          className="px-4 py-2 rounded-full border border-aura-primary/20 bg-aura-primary/5 text-aura-primary text-xs font-bold hover:bg-aura-primary hover:text-white transition-all cursor-pointer min-h-[44px]"
                        >
                          {label}
                        </button>
                      )
                    )}
                  </div>
                </div>
              </div>

              {/* Demo user reply */}
              <div className="flex gap-4 justify-end">
                <div className="bg-aura-primary text-white rounded-3xl rounded-tr-none p-6 shadow-lg ring-4 ring-aura-primary/5 max-w-lg">
                  <p className="text-base leading-relaxed font-medium italic">
                    "I'm thinking of a coastal photographer living in a van. Grainy film
                    aesthetic, vintage surf vibes, very chill and organic."
                  </p>
                </div>
                <div className="w-9 h-9 rounded-xl bg-aura-surface-container-highest shrink-0 mt-1 overflow-hidden shadow-sm">
                  <img
                    src="https://randomuser.me/api/portraits/men/32.jpg"
                    alt="User"
                    className="w-full h-full object-cover"
                    width={36}
                    height={36}
                  />
                </div>
              </div>

              {/* AI mood boards */}
              <div className="flex gap-4">
                <div className="w-9 h-9 rounded-xl bg-aura-primary shrink-0 mt-1 flex items-center justify-center text-[10px] text-white font-black">
                  OC
                </div>
                <div className="bg-aura-surface-container-low rounded-3xl rounded-tl-none p-6 shadow-sm border border-aura-outline-variant/5 w-full max-w-xl">
                  <p className="text-base leading-relaxed text-aura-on-surface font-medium">
                    That sounds incredibly aesthetic. I've generated a few{" "}
                    <span className="text-aura-primary font-black">visual mood sets</span>{" "}
                    based on "Coastal Vintage Photographer." Which one captures the soul of
                    your AI-Influencer?
                  </p>
                  <div className="mt-6 grid grid-cols-2 gap-4">
                    {[
                      {
                        img: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
                        label: "Style A",
                        alt: "Coastal mood A",
                      },
                      {
                        img: "https://images.unsplash.com/photo-1533107862482-0e6974b06017?auto=format&fit=crop&w=800&q=80",
                        label: "Style B",
                        alt: "Coastal mood B",
                      },
                    ].map(({ img, label, alt }) => (
                      <button
                        key={label}
                        type="button"
                        className="group relative aspect-square rounded-2xl overflow-hidden ring-4 ring-transparent hover:ring-aura-primary/30 transition-all cursor-pointer"
                        aria-label={`Select ${label}`}
                      >
                        <img
                          src={img}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                          alt={alt}
                          width={280}
                          height={280}
                        />
                        <div className="absolute inset-0 bg-aura-on-surface/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                          <span className="text-white font-black uppercase tracking-widest text-sm">
                            Select {label}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Input Bar */}
            <div className="border-t border-aura-outline-variant/10 bg-white p-6">
              <div className="relative flex items-center gap-3">
                <label className="sr-only" htmlFor="persona-composer">
                  Describe your persona
                </label>
                <input
                  id="persona-composer"
                  name="personaComposer"
                  type="text"
                  autoComplete="off"
                  placeholder="Describe a trait, a location, or give feedback…"
                  className="flex-1 py-4 px-6 pr-14 rounded-full bg-aura-surface-container border border-aura-outline-variant/20 font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all text-sm shadow-sm"
                  value={composer}
                  onChange={(e) => setComposer(e.target.value)}
                />
                <button
                  type="button"
                  aria-label="Send persona prompt"
                  className="absolute right-3 w-11 h-11 rounded-full bg-gradient-to-tr from-aura-primary to-aura-primary text-white flex items-center justify-center shadow-lg hover:scale-105 active:scale-95 transition-transform cursor-pointer"
                >
                  <ArrowUp className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </>
      )}
      <PersonaStudioPanel
        isOpen={isCreationOpen}
        state={studioState}
        busy={isStudioBusy}
        error={studioError}
        draftSaved={draftSaved}
        onClose={() => setIsCreationOpen(false)}
        onSendText={handleStudioText}
        onAction={handleStudioAction}
        onSaveDraft={handleSaveDraft}
        onFinalize={handleFinalizeStudio}
      />
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────────────────────── */

function PersonaListItem({
  persona,
  isActive,
  onClick,
}: {
  persona: Persona;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isActive}
      className={cn(
        "group relative w-full overflow-hidden rounded-2xl p-4 text-left transition-all duration-200 cursor-pointer min-h-[44px]",
        isActive
          ? "bg-white shadow-md border border-aura-primary/15 ring-2 ring-aura-primary/10"
          : "border border-transparent hover:bg-aura-surface-container hover:border-aura-outline-variant/20"
      )}
    >
      <div className="flex items-center gap-4 relative z-10">
        <div className="relative shrink-0">
          <img
            src={persona.avatar_image_url || "/placeholder-avatar.png"}
            alt={persona.display_name}
            width={48}
            height={48}
            className={cn(
              "w-12 h-12 rounded-[1rem] object-cover transition-all duration-300 shadow-sm",
              !isActive && "grayscale-[30%] opacity-80"
            )}
          />
          {persona.status === "active" && (
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 border-2 border-white rounded-full" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h4
            className={cn(
              "font-black font-headline truncate leading-tight text-sm",
              isActive ? "text-aura-on-surface" : "text-aura-on-surface/70"
            )}
          >
            {persona.display_name}
          </h4>
          <p className="text-[10px] font-bold text-aura-on-surface-variant uppercase tracking-widest mt-0.5">
            {persona.location || "Global AI Core"}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span
            className={cn(
              "text-[9px] font-black uppercase tracking-[0.2em]",
              persona.status === "active" ? "text-aura-primary" : "text-aura-on-surface-variant/40"
            )}
          >
            {persona.status}
          </span>
          <ChevronRight
            className={cn(
              "w-3.5 h-3.5 transition-colors",
              isActive ? "text-aura-primary" : "text-aura-on-surface-variant/20"
            )}
          />
        </div>
      </div>
      {isActive && (
        <div className="absolute top-0 right-0 w-20 h-20 bg-aura-primary/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl" />
      )}
    </button>
  );
}

function MetaChip({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2 bg-aura-surface-container rounded-2xl px-4 py-3">
      <span className="text-aura-on-surface-variant/60">{icon}</span>
      <div className="min-w-0">
        <p className="text-[10px] font-black uppercase tracking-widest text-aura-on-surface-variant/50 font-label">
          {label}
        </p>
        <p className="text-xs font-bold text-aura-on-surface truncate">{value}</p>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  delta,
  color,
}: {
  label: string;
  value: string;
  delta: string;
  color: "primary" | "secondary" | "tertiary";
}) {
  const colorMap = {
    primary: "text-aura-primary",
    secondary: "text-aura-secondary",
    tertiary: "text-aura-tertiary",
  };
  return (
    <div className="dashboard-card-muted p-6 space-y-2">
      <p
        className={cn(
          "text-[10px] font-black uppercase tracking-[0.2em] font-label",
          colorMap[color]
        )}
      >
        {label}
      </p>
      <p className="text-3xl font-black text-aura-on-surface">{value}</p>
      <p className="text-xs text-aura-on-surface-variant font-medium">{delta}</p>
    </div>
  );
}

function TikTokChannelCard({
  status,
  actionLabel,
  onAction,
  onManage,
  bannerMessage,
  onDismissBanner,
}: {
  status: TikTokChannelStatus;
  actionLabel: string;
  onAction: () => void;
  onManage: () => void;
  bannerMessage: string | null;
  onDismissBanner: () => void;
}) {
  const connectionBadge: Record<TikTokConnectionState, { label: string; cls: string; icon: React.ReactNode }> = {
    connected_demo: {
      label: "Connected (demo)",
      cls: "bg-emerald-50 text-emerald-700 border-emerald-200",
      icon: <CheckCircle2 className="w-3 h-3" />,
    },
    not_connected: {
      label: "Not connected",
      cls: "bg-aura-surface-container text-aura-on-surface-variant/70 border-aura-outline-variant/30",
      icon: <Globe className="w-3 h-3 opacity-50" />,
    },
    needs_reconnect: {
      label: "Needs reconnect",
      cls: "bg-red-50 text-red-700 border-red-200",
      icon: <AlertTriangle className="w-3 h-3" />,
    },
  };

  const conn = connectionBadge[status.connectionState];

  return (
    // ✨ Enhanced Card with Left Border Accent
    <div className="dashboard-panel border-l-4 border-l-aura-primary p-6 space-y-4">
      {/* Header: Icon + Status */}
      <div className="flex items-start gap-4">
        {/* Icon Container (40x40px) */}
        <div className="relative w-12 h-12 rounded-xl bg-aura-surface-container/40 flex items-center justify-center flex-shrink-0">
          <svg
            viewBox="0 0 24 24"
            className="w-6 h-6 fill-aura-on-surface"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.32 6.32 0 0 0-.79-.05A6.34 6.34 0 0 0 3.15 15.3a6.34 6.34 0 0 0 6.34 6.35 6.34 6.34 0 0 0 6.33-6.35V8.89a8.27 8.27 0 0 0 4.83 1.54V7a4.85 4.85 0 0 1-1.06-.31Z" />
          </svg>

          {/* Connection Status Dot */}
          {status.connectionState === "connected_demo" && (
            <div className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-white bg-emerald-500 animate-pulse-slow" />
          )}
        </div>

        {/* Title + Status Label Stack */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-bold text-aura-on-surface font-headline">
            TikTok Channel
          </h3>
          <span className={cn(
            "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border mt-1.5",
            conn.cls
          )}>
            {conn.icon}
            {conn.label}
          </span>
        </div>

        {/* Active/Inactive Badge */}
        <span
          className={cn(
            "px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-widest border font-label flex-shrink-0",
            status.activeState === "active"
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : "bg-aura-surface-container text-aura-on-surface-variant border-aura-outline-variant/30"
          )}
        >
          {status.activeState === "active" ? "Active" : "Inactive"}
        </span>
      </div>

      {/* Banner message */}
      {bannerMessage && (
        <div
          role="status"
          className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-amber-800 animate-fade-in"
        >
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="flex-1 font-medium">{bannerMessage}</span>
          <button
            type="button"
            onClick={onDismissBanner}
            aria-label="Dismiss message"
            className="text-amber-700 hover:text-amber-900 cursor-pointer min-h-[44px] px-1 flex items-center"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Metadata: Vertical Stacks (Improved Scannability) */}
      <div className="space-y-2.5 pt-1">
        <div className="flex justify-between items-baseline gap-2">
          <p className="text-[10px] font-black uppercase tracking-widest text-aura-on-surface-variant/60 font-label flex-shrink-0">
            Channel Handle
          </p>
          <p className="text-sm font-bold text-aura-on-surface text-right truncate">
            {status.channelHandle ?? "—"}
          </p>
        </div>

        <div className="flex justify-between items-baseline gap-2">
          <p className="text-[10px] font-black uppercase tracking-widest text-aura-on-surface-variant/60 font-label flex-shrink-0">
            Display Name
          </p>
          <p className="text-sm font-bold text-aura-on-surface text-right truncate">
            {status.displayName ?? "—"}
          </p>
        </div>

        <div className="flex justify-between items-baseline gap-2">
          <p className="text-[10px] font-black uppercase tracking-widest text-aura-on-surface-variant/60 font-label flex-shrink-0">
            Last Sync
          </p>
          <p className="text-sm font-bold text-aura-on-surface text-right truncate">
            {status.lastSyncLabel ?? "—"}
          </p>
        </div>
      </div>

      {/* CTA Buttons: Full Width with Icon + Label */}
      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onAction}
          className="btn-primary flex-1 flex items-center justify-center gap-2 min-h-[44px]"
          aria-label={actionLabel}
        >
          <Link className="w-4 h-4" />
          <span className="font-bold">{actionLabel}</span>
        </button>
        <button
          type="button"
          onClick={onManage}
          className="btn-secondary flex items-center gap-2 min-h-[44px] px-5"
          aria-label="Manage TikTok channel settings"
        >
          Manage
        </button>
      </div>
    </div>
  );
}

function IntegrationRow({
  name,
  handle,
  state,
  comingSoon,
}: {
  name: string;
  handle: string;
  state: TikTokConnectionState;
  comingSoon?: boolean;
}) {
  const dotColor =
    state === "connected_demo"
      ? "bg-emerald-500"
      : state === "needs_reconnect"
        ? "bg-red-500"
        : "bg-aura-on-surface-variant/20";

  return (
    <div className="flex items-center gap-4 py-3 border-b border-aura-outline-variant/10 last:border-0">
      <span className={cn("w-2 h-2 rounded-full shrink-0", dotColor)} />
      <span className="text-sm font-bold text-aura-on-surface flex-1">{name}</span>
      <span
        className={cn(
          "text-xs font-medium",
          comingSoon
            ? "text-aura-on-surface-variant/40"
            : state === "connected_demo"
              ? "text-emerald-600"
              : "text-aura-on-surface-variant/60"
        )}
      >
        {handle}
      </span>
      {!comingSoon && (
        <ChevronRight className="w-4 h-4 text-aura-on-surface-variant/20 shrink-0" />
      )}
    </div>
  );
}
