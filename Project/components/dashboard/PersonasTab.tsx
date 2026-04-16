"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Globe,
  Loader2,
  Mic,
  PenSquare,
  Plus,
  RefreshCw,
  Sparkles,
  Video,
  X,
} from "lucide-react";
import { customerApiRequest } from "@/lib/customer-api";
import { cn } from "@/lib/utils";
import {
  type ReviewEnginePersonaOption,
  type ReviewEngineSetup,
} from "@/lib/review-engine";

interface Persona {
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
}

interface PersonasTabProps {
  personas: Persona[];
  setup: ReviewEngineSetup | null;
  onNavigateToCreateVideo?: () => void;
  onPersonasChanged?: () => Promise<void> | void;
}

type CreatePersonaForm = {
  display_name: string;
  language: string;
  tts_voice: string;
  appearance_prompt_or_photo: string;
  tone_default: string;
  market_default: string;
  description: string;
};

const EMPTY_CREATE_FORM: CreatePersonaForm = {
  display_name: "",
  language: "English",
  tts_voice: "",
  appearance_prompt_or_photo: "",
  tone_default: "confident",
  market_default: "american",
  description: "",
};

export function PersonasTab({
  personas,
  setup,
  onNavigateToCreateVideo,
  onPersonasChanged,
}: PersonasTabProps) {
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [isCreatingPersona, setIsCreatingPersona] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    display_name: "",
    tts_voice: "",
    appearance_prompt_or_photo: "",
    language: "English",
  });
  const [createForm, setCreateForm] = useState<CreatePersonaForm>(EMPTY_CREATE_FORM);

  const personaSetupMap = useMemo(() => {
    const map = new Map<string, ReviewEnginePersonaOption>();
    (setup?.persona_options || []).forEach((persona) => {
      map.set(persona.persona_id, persona);
    });
    (setup?.custom_personas || []).forEach((persona) => {
      map.set(persona.persona_id, persona);
    });
    return map;
  }, [setup]);

  const filteredPersonas = useMemo(
    () =>
      personas.filter((persona) =>
        `${persona.display_name} ${persona.region_label || ""} ${persona.language || ""}`
          .toLowerCase()
          .includes(searchQuery.toLowerCase()),
      ),
    [personas, searchQuery],
  );

  const selectedPersona = useMemo(
    () =>
      filteredPersonas.find((persona) => persona.persona_id === selectedPersonaId) ||
      personas.find((persona) => persona.persona_id === selectedPersonaId) ||
      personas[0] ||
      null,
    [filteredPersonas, personas, selectedPersonaId],
  );

  useEffect(() => {
    if (!selectedPersonaId && personas[0]?.persona_id) {
      setSelectedPersonaId(personas[0].persona_id);
    }
  }, [personas, selectedPersonaId]);

  useEffect(() => {
    if (!selectedPersona) return;
    setEditForm({
      display_name: selectedPersona.display_name || "",
      tts_voice: selectedPersona.tts_voice || "",
      appearance_prompt_or_photo: selectedPersona.appearance_prompt_or_photo || "",
      language: selectedPersona.language || "English",
    });
  }, [selectedPersona]);

  const selectedSetup = selectedPersona
    ? personaSetupMap.get(selectedPersona.persona_id)
    : null;
  const isEditable = Boolean(selectedPersona && !selectedPersona.is_preset_catalog);
  const selectedImage =
    selectedPersona?.selection_image_url ||
    selectedSetup?.selection_image_url ||
    selectedSetup?.image_url ||
    selectedPersona?.avatar_image_url ||
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop";

  const handleSave = async () => {
    if (!selectedPersona || !isEditable) return;
    setPageError(null);
    setIsSaving(true);
    try {
      await customerApiRequest(`/api/customer/personas/${selectedPersona.persona_id}`, {
        method: "PATCH",
        body: JSON.stringify(editForm),
      });
      await onPersonasChanged?.();
      setIsEditing(false);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to update persona");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRebuildAvatar = async () => {
    if (!selectedPersona || !isEditable || !editForm.appearance_prompt_or_photo.trim()) return;
    setPageError(null);
    setIsRebuilding(true);
    try {
      await customerApiRequest(
        `/api/customer/personas/${selectedPersona.persona_id}/rebuild-avatar`,
        {
          method: "POST",
          body: JSON.stringify({
            appearance_prompt_or_photo: editForm.appearance_prompt_or_photo.trim(),
          }),
        },
      );
      await onPersonasChanged?.();
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Failed to rebuild avatar",
      );
    } finally {
      setIsRebuilding(false);
    }
  };

  const handleCreatePersona = async () => {
    if (!createForm.display_name.trim()) {
      setPageError("Persona display name is required.");
      return;
    }
    setPageError(null);
    setIsCreatingPersona(true);
    try {
      await customerApiRequest("/api/customer/personas", {
        method: "POST",
        body: JSON.stringify(createForm),
      });
      setCreateForm(EMPTY_CREATE_FORM);
      setIsCreating(false);
      await onPersonasChanged?.();
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Failed to create persona",
      );
    } finally {
      setIsCreatingPersona(false);
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[320px_minmax(0,1fr)] gap-8 animate-fade-in">
      <aside className="dashboard-panel-soft p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-black text-aura-on-surface font-headline">
              Personas
            </h2>
            <p className="text-xs text-aura-on-surface-variant mt-1">
              {personas.length} available
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsCreating(true)}
            className="btn-primary btn-sm flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create
          </button>
        </div>

        <input
          type="search"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Search personas"
          className="w-full rounded-2xl bg-white px-4 py-3 outline-none text-sm text-aura-on-surface"
        />

        <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
          {filteredPersonas.map((persona) => {
            const personaPreview =
              persona.selection_image_url ||
              persona.avatar_image_url ||
              personaSetupMap.get(persona.persona_id)?.selection_image_url ||
              "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop";
            return (
              <button
                key={persona.persona_id}
                type="button"
                onClick={() => {
                  setSelectedPersonaId(persona.persona_id);
                  setIsEditing(false);
                }}
                className={cn(
                  "w-full rounded-3xl p-4 text-left transition-all border",
                  selectedPersona?.persona_id === persona.persona_id
                    ? "border-aura-primary bg-white shadow-aura-sm"
                    : "border-transparent bg-aura-surface-container-low hover:border-aura-outline-variant/20",
                )}
              >
                <div className="flex items-center gap-4">
                  <img
                    alt={persona.display_name}
                    className="w-14 h-14 rounded-2xl object-cover"
                    src={personaPreview}
                    width={56}
                    height={56}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-black text-aura-on-surface truncate">
                      {persona.display_name}
                    </p>
                    <p className="text-[11px] uppercase tracking-widest text-aura-on-surface-variant mt-1">
                      {persona.region_label || persona.language || "Global"}
                    </p>
                    <p className="text-xs text-aura-on-surface-variant mt-1">
                      {persona.video_count} videos
                    </p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      <section className="space-y-6">
        {pageError && (
          <div className="dashboard-banner dashboard-banner-error text-sm font-semibold">
            {pageError}
          </div>
        )}

        {selectedPersona ? (
          <>
            <div className="dashboard-panel p-8 grid grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)] gap-8">
              <img
                alt={selectedPersona.display_name}
                className="w-full max-w-[220px] aspect-[4/5] rounded-[2rem] object-cover"
                src={selectedImage}
              />
              <div className="space-y-5">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <h1 className="text-3xl font-black text-aura-on-surface font-headline">
                      {selectedPersona.display_name}
                    </h1>
                    <p className="text-sm text-aura-on-surface-variant mt-2">
                      {selectedSetup?.description ||
                        selectedPersona.description ||
                        "Regional persona for app review production."}
                    </p>
                  </div>
                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={() => setIsEditing((current) => !current)}
                      disabled={!isEditable}
                      className="btn-secondary btn-sm flex items-center gap-2"
                    >
                      <PenSquare className="w-4 h-4" />
                      {isEditable ? (isEditing ? "Close Edit" : "Edit") : "Preset"}
                    </button>
                    {onNavigateToCreateVideo && (
                      <button
                        type="button"
                        onClick={onNavigateToCreateVideo}
                        className="btn-primary btn-sm"
                      >
                        Generate Video
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <StatChip icon={<Globe className="w-4 h-4" />} label="Region" value={selectedPersona.region_label || selectedPersona.language || "Global"} />
                  <StatChip icon={<Mic className="w-4 h-4" />} label="Voice" value={selectedPersona.tts_voice || "Default"} />
                  <StatChip icon={<Video className="w-4 h-4" />} label="Videos" value={String(selectedPersona.video_count)} />
                  <StatChip icon={<Sparkles className="w-4 h-4" />} label="Status" value={selectedPersona.status} />
                </div>

                {!isEditable && (
                  <div className="rounded-3xl bg-aura-primary/5 border border-aura-primary/10 px-5 py-4 text-sm text-aura-on-surface-variant">
                    Preset catalog personas are selectable for video generation, but profile editing is reserved for customer-created personas.
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="rounded-3xl bg-aura-surface-container-low p-5 space-y-3">
                    <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
                      TikTok Integration
                    </p>
                    <p className="text-lg font-black text-aura-on-surface">
                      {selectedSetup?.tiktok_integration?.status || "inactive"}
                    </p>
                    <p className="text-sm text-aura-on-surface-variant">
                      Active channels: {selectedSetup?.tiktok_integration?.active_channels || 0}
                    </p>
                  </div>
                  <div className="rounded-3xl bg-aura-surface-container-low p-5 space-y-3">
                    <p className="text-[10px] uppercase tracking-widest text-aura-on-surface-variant font-bold">
                      Demo
                    </p>
                    <p className="text-lg font-black text-aura-on-surface">
                      {selectedSetup?.demo?.available ? "Available" : "Not available"}
                    </p>
                    <p className="text-sm text-aura-on-surface-variant">
                      {selectedSetup?.demo?.summary || "Preview-ready persona demo metadata."}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {isEditing && isEditable && (
              <div className="dashboard-panel p-8 space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <Field
                    label="Display Name"
                    value={editForm.display_name}
                    onChange={(value) => setEditForm((current) => ({ ...current, display_name: value }))}
                  />
                  <Field
                    label="Language"
                    value={editForm.language}
                    onChange={(value) => setEditForm((current) => ({ ...current, language: value }))}
                  />
                  <Field
                    label="TTS Voice"
                    value={editForm.tts_voice}
                    onChange={(value) => setEditForm((current) => ({ ...current, tts_voice: value }))}
                  />
                </div>
                <TextField
                  label="Appearance Prompt"
                  value={editForm.appearance_prompt_or_photo}
                  onChange={(value) =>
                    setEditForm((current) => ({
                      ...current,
                      appearance_prompt_or_photo: value,
                    }))
                  }
                />
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => void handleSave()}
                    disabled={isSaving}
                    className="btn-primary btn-sm disabled:opacity-50"
                  >
                    {isSaving ? "Saving..." : "Save Persona"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleRebuildAvatar()}
                    disabled={isRebuilding || !editForm.appearance_prompt_or_photo.trim()}
                    className="btn-secondary btn-sm disabled:opacity-50 flex items-center gap-2"
                  >
                    {isRebuilding ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <RefreshCw className="w-4 h-4" />
                    )}
                    Rebuild Avatar
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="dashboard-panel-soft p-12 text-center text-aura-on-surface-variant">
            No persona selected.
          </div>
        )}
      </section>

      {isCreating && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/25 backdrop-blur-sm"
            onClick={() => setIsCreating(false)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl rounded-[2rem] bg-white shadow-2xl p-8 space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-black text-aura-on-surface font-headline">
                    Create Your Own Persona
                  </h2>
                  <p className="text-sm text-aura-on-surface-variant mt-1">
                    This creates a customer-owned persona available in the review engine.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="btn-secondary btn-sm"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <Field
                  label="Display Name"
                  value={createForm.display_name}
                  onChange={(value) =>
                    setCreateForm((current) => ({ ...current, display_name: value }))
                  }
                />
                <Field
                  label="Language"
                  value={createForm.language}
                  onChange={(value) =>
                    setCreateForm((current) => ({ ...current, language: value }))
                  }
                />
                <Field
                  label="TTS Voice"
                  value={createForm.tts_voice}
                  onChange={(value) =>
                    setCreateForm((current) => ({ ...current, tts_voice: value }))
                  }
                />
                <Field
                  label="Market Default"
                  value={createForm.market_default}
                  onChange={(value) =>
                    setCreateForm((current) => ({ ...current, market_default: value }))
                  }
                />
                <Field
                  label="Tone Default"
                  value={createForm.tone_default}
                  onChange={(value) =>
                    setCreateForm((current) => ({ ...current, tone_default: value }))
                  }
                />
              </div>

              <TextField
                label="Description"
                value={createForm.description}
                onChange={(value) =>
                  setCreateForm((current) => ({ ...current, description: value }))
                }
              />
              <TextField
                label="Appearance Prompt"
                value={createForm.appearance_prompt_or_photo}
                onChange={(value) =>
                  setCreateForm((current) => ({
                    ...current,
                    appearance_prompt_or_photo: value,
                  }))
                }
              />

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="btn-secondary btn-sm"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void handleCreatePersona()}
                  disabled={isCreatingPersona}
                  className="btn-primary btn-sm disabled:opacity-50"
                >
                  {isCreatingPersona ? "Creating..." : "Create Persona"}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2 block">
      <span className="text-[11px] font-black uppercase tracking-widest text-aura-on-surface-variant">
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl bg-aura-surface-container px-4 py-3 outline-none text-sm text-aura-on-surface"
      />
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2 block">
      <span className="text-[11px] font-black uppercase tracking-widest text-aura-on-surface-variant">
        {label}
      </span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl bg-aura-surface-container px-4 py-3 min-h-[120px] outline-none text-sm text-aura-on-surface"
      />
    </label>
  );
}

function StatChip({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-3xl bg-aura-surface-container-low px-4 py-4">
      <div className="flex items-center gap-2 text-aura-on-surface-variant">
        {icon}
        <span className="text-[10px] uppercase tracking-widest font-bold">{label}</span>
      </div>
      <p className="mt-2 text-sm font-black text-aura-on-surface">{value}</p>
    </div>
  );
}
