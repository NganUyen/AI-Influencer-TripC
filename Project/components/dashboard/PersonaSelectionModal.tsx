"use client";

import React from "react";
import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { type ReviewEnginePersonaOption } from "@/lib/review-engine";

interface PersonaSelectionModalProps {
  isOpen: boolean;
  validationResult: any;
  personas: ReviewEnginePersonaOption[];
  selectedPersonaIds: string[];
  onChangeSelectedPersonaIds: (personaIds: string[]) => void;
  onClose: () => void;
  onConfirm: (personaIds: string[]) => void;
}

function PersonaSelectionModal({
  isOpen,
  validationResult,
  personas,
  selectedPersonaIds,
  onChangeSelectedPersonaIds,
  onClose,
  onConfirm,
}: PersonaSelectionModalProps) {
  if (!isOpen) {
    return null;
  }

  const togglePersona = (personaId: string) => {
    onChangeSelectedPersonaIds(
      selectedPersonaIds.includes(personaId)
        ? selectedPersonaIds.filter((id) => id !== personaId)
        : [...selectedPersonaIds, personaId],
    );
  };

  const toggleAll = () => {
    if (selectedPersonaIds.length === personas.length) {
      onChangeSelectedPersonaIds([]);
      return;
    }
    onChangeSelectedPersonaIds(personas.map((persona) => persona.persona_id));
  };

  const pageTitle = validationResult?.page_title || "Source validated";
  const normalizedUrl = validationResult?.normalized_url || "";
  const visibleFeatures = validationResult?.visible_features || [];

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-aura-on-surface/30 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Select personas"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div className="bg-white rounded-3xl shadow-2xl w-full max-w-6xl max-h-[90vh] p-6 md:p-8 space-y-6 overflow-hidden">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-xl font-black text-aura-on-surface font-headline">
                Select Personas
              </h3>
              <p className="text-xs text-aura-on-surface-variant mt-1">
                Confirm persona selection after URL validation.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close persona selection modal"
              className="w-10 h-10 rounded-full bg-aura-surface-container text-aura-on-surface-variant hover:bg-aura-surface-container-high flex items-center justify-center"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="rounded-2xl border border-aura-outline-variant/20 p-4 space-y-2 bg-aura-surface-container-low">
            <p className="text-sm font-bold text-aura-on-surface">{pageTitle}</p>
            {normalizedUrl ? (
              <p className="text-xs text-aura-on-surface-variant break-all">{normalizedUrl}</p>
            ) : null}
            {visibleFeatures.length > 0 ? (
              <div className="flex flex-wrap gap-2 pt-1">
                {visibleFeatures.slice(0, 8).map((feature: any, index: number) => (
                  <span
                    key={`${feature.name || "feature"}-${index}`}
                    className="rounded-full bg-aura-primary/10 px-3 py-1 text-[11px] font-bold text-aura-primary"
                  >
                    {feature.name || feature.label || "Feature"}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-bold text-aura-on-surface">
              {selectedPersonaIds.length} of {personas.length} selected
            </span>
            <button
              type="button"
              onClick={toggleAll}
              className={cn(
                "btn-secondary btn-sm",
                selectedPersonaIds.length === personas.length
                  ? "bg-aura-error/10 text-aura-error border-aura-error/30 hover:bg-aura-error/20"
                  : "",
              )}
            >
              {selectedPersonaIds.length === personas.length ? "Deselect All" : "Select All"}
            </button>
          </div>

          <div className="overflow-y-auto pr-1 max-h-[42vh]">
            {personas.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                {personas.map((persona) => {
                  const isSelected = selectedPersonaIds.includes(persona.persona_id);
                  const activeChannels = persona.tiktok_integration?.active_channels || 0;
                  const language = persona.language || "Unknown";
                  const region = persona.region_label || persona.market_default || "Global";
                  const tone = persona.tone_default || "neutral";

                  return (
                    <button
                      key={persona.persona_id}
                      type="button"
                      onClick={() => togglePersona(persona.persona_id)}
                      className={cn(
                        "dashboard-panel p-4 text-left transition-all border-2 relative overflow-hidden",
                        isSelected
                          ? "border-aura-primary bg-aura-primary/8 shadow-lg shadow-aura-primary/20"
                          : "border-aura-outline-variant/30 hover:border-aura-primary/50 hover:bg-aura-surface-container/50",
                      )}
                    >
                      {isSelected ? (
                        <div className="absolute top-3 right-3 z-10 bg-aura-primary rounded-full p-1.5 shadow-lg">
                          <Check className="w-4 h-4 text-white" />
                        </div>
                      ) : null}

                      <img
                        alt={persona.display_name}
                        className={cn(
                          "w-full aspect-[4/5] rounded-2xl object-cover mb-4",
                          isSelected ? "ring-2 ring-aura-primary/50" : "",
                        )}
                        src={
                          persona.selection_image_url ||
                          persona.image_url ||
                          "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop"
                        }
                        onError={(e) => {
                          const img = e.target as HTMLImageElement;
                          if (!img.src?.includes("images.unsplash.com")) {
                            img.src =
                              "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop";
                          }
                        }}
                      />
                      <div className="space-y-2">
                        <p className="font-black text-aura-on-surface truncate text-sm">
                          {persona.display_name}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-aura-surface-container border border-aura-outline-variant/40 text-[10px] font-semibold uppercase tracking-tight text-aura-on-surface-variant">
                            <span>📍</span>
                            <span>{region}</span>
                          </span>
                          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-aura-surface-container border border-aura-outline-variant/40 text-[10px] font-semibold uppercase tracking-tight text-aura-on-surface-variant">
                            <span>🌐</span>
                            <span>{language}</span>
                          </span>
                          {tone ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-aura-surface-container border border-aura-outline-variant/40 text-[10px] font-semibold uppercase tracking-tight text-aura-on-surface-variant">
                              <span>💬</span>
                              <span>{tone}</span>
                            </span>
                          ) : null}
                        </div>
                        <p className="text-xs text-aura-on-surface-variant line-clamp-2 leading-relaxed">
                          {persona.description || "Ready for regional app review production."}
                        </p>
                        <span
                          className={cn(
                            "inline-flex rounded-full border px-2 py-1.5 text-[10px] font-bold uppercase tracking-tight whitespace-nowrap",
                            activeChannels > 0
                              ? "border-emerald-200/60 bg-emerald-50/80 text-emerald-700"
                              : "border-amber-200/60 bg-amber-50/80 text-amber-700",
                          )}
                        >
                          <span className="inline-block mr-1">
                            {activeChannels > 0 ? "✓" : "○"}
                          </span>
                          {activeChannels > 0 ? `TikTok (${activeChannels})` : "TikTok Inactive"}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="dashboard-panel-soft p-10 text-center text-aura-on-surface-variant">
                No personas found yet.
              </div>
            )}
          </div>

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="btn-secondary btn-sm">
              Cancel
            </button>
            <button
              type="button"
              onClick={() => onConfirm(selectedPersonaIds)}
              disabled={selectedPersonaIds.length === 0}
              className="btn-primary btn-sm disabled:opacity-50"
            >
              Confirm Selection
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default PersonaSelectionModal;

