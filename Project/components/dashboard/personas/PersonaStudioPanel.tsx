"use client";

import React from "react";
import { ArrowUp, Brain, Check, Loader2, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  PersonaStudioAction,
  PersonaStudioMessage,
  PersonaStudioSessionState,
} from "@/types/persona-studio";

interface PersonaStudioPanelProps {
  isOpen: boolean;
  state: PersonaStudioSessionState | null;
  busy: boolean;
  error: string | null;
  draftSaved: boolean;
  onClose: () => void;
  onSendText: (content: string) => Promise<void>;
  onAction: (action: PersonaStudioAction) => Promise<void>;
  onSaveDraft: () => Promise<void>;
  onFinalize: () => Promise<void>;
}

export function PersonaStudioPanel({
  isOpen,
  state,
  busy,
  error,
  draftSaved,
  onClose,
  onSendText,
  onAction,
  onSaveDraft,
  onFinalize,
}: PersonaStudioPanelProps) {
  const [composer, setComposer] = React.useState("");

  React.useEffect(() => {
    if (!isOpen) {
      setComposer("");
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const submitComposer = async () => {
    const value = composer.trim();
    if (!value || !state?.composer?.enabled || busy) {
      return;
    }
    setComposer("");
    await onSendText(value);
  };

  const latestPreview =
    state?.preview ||
    [...(state?.messages || [])].reverse().find((message) => message.preview)?.preview ||
    null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-aura-on-surface/20 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Create new persona"
        className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-2xl bg-white shadow-2xl flex flex-col animate-slide-in border-l border-aura-outline-variant/10"
      >
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
              onClick={() => void onSaveDraft()}
              disabled={busy || !state}
              className="btn-secondary btn-sm disabled:opacity-50"
              aria-label="Save draft"
            >
              {busy ? "Working..." : "Save Draft"}
            </button>
            <button
              type="button"
              onClick={() => void onFinalize()}
              disabled={busy || !state?.can_finalize}
              className="btn-primary btn-sm disabled:opacity-50"
              aria-label="Finalize AI persona"
            >
              {busy ? "Working..." : "Finalize Persona"}
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close creation studio"
              className="w-10 h-10 rounded-full bg-aura-surface-container text-aura-on-surface-variant hover:bg-aura-surface-container-high transition-colors flex items-center justify-center cursor-pointer min-h-[44px]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-8 space-y-6 scrollbar-hide">
          {error ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
              {error}
            </div>
          ) : null}
          {draftSaved ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
              Draft saved. Closing the drawer keeps this session available during this visit.
            </div>
          ) : null}

          {!state ? (
            <div className="flex min-h-[240px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-aura-primary" />
            </div>
          ) : (
            <>
              {state.messages.map((message) => (
                <PersonaStudioMessageView
                  key={message.id}
                  message={message}
                  busy={busy}
                  onAction={onAction}
                />
              ))}

              {busy ? (
                <div className="flex gap-4">
                  <div className="w-9 h-9 rounded-xl bg-aura-primary shrink-0 mt-1 flex items-center justify-center text-[10px] text-white font-black shadow-lg">
                    OC
                  </div>
                  <div className="bg-aura-surface-container-low rounded-3xl rounded-tl-none p-6 border border-aura-outline-variant/5 shadow-sm">
                    <Loader2 className="h-5 w-5 animate-spin text-aura-primary" />
                  </div>
                </div>
              ) : null}

              {latestPreview ? (
                <PersonaStudioPreview preview={latestPreview} />
              ) : null}
            </>
          )}
        </div>

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
              placeholder={state?.composer?.placeholder || "Describe your persona..."}
              className="flex-1 py-4 px-6 pr-14 rounded-full bg-aura-surface-container border border-aura-outline-variant/20 font-medium text-aura-on-surface focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all text-sm shadow-sm disabled:opacity-60"
              value={composer}
              onChange={(e) => setComposer(e.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void submitComposer();
                }
              }}
              disabled={!state?.composer?.enabled || busy}
            />
            <button
              type="button"
              aria-label="Send persona prompt"
              disabled={!state?.composer?.enabled || busy || !composer.trim()}
              onClick={() => void submitComposer()}
              className="absolute right-3 w-11 h-11 rounded-full bg-gradient-to-tr from-aura-primary to-aura-primary text-white flex items-center justify-center shadow-lg hover:scale-105 active:scale-95 transition-transform cursor-pointer disabled:opacity-50 disabled:hover:scale-100"
            >
              <ArrowUp className="w-5 h-5" />
            </button>
          </div>
          {!state?.composer?.enabled && state?.actions?.length ? (
            <p className="mt-3 text-xs text-aura-on-surface-variant">
              Choose one of the options above to continue.
            </p>
          ) : null}
        </div>
      </div>
    </>
  );
}

function PersonaStudioMessageView({
  message,
  busy,
  onAction,
}: {
  message: PersonaStudioMessage;
  busy: boolean;
  onAction: (action: PersonaStudioAction) => Promise<void>;
}) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <div className={cn("flex gap-4", isUser && "justify-end")}>
      {!isUser ? (
        <div
          className={cn(
            "w-9 h-9 rounded-xl shrink-0 mt-1 flex items-center justify-center text-[10px] font-black shadow-lg",
            isSystem ? "bg-amber-100 text-amber-700" : "bg-aura-primary text-white",
          )}
        >
          {isSystem ? <Sparkles className="w-4 h-4" /> : "OC"}
        </div>
      ) : null}
      <div
        className={cn(
          "max-w-xl rounded-3xl p-6 shadow-sm border",
          isUser
            ? "bg-aura-primary text-white rounded-tr-none border-aura-primary/10 shadow-lg ring-4 ring-aura-primary/5"
            : isSystem
              ? "bg-amber-50 text-amber-900 border-amber-200 rounded-tl-none"
              : "bg-aura-surface-container-low text-aura-on-surface border-aura-outline-variant/5 rounded-tl-none",
        )}
      >
        <p className={cn("text-base leading-relaxed font-medium whitespace-pre-wrap", isUser && "italic")}>
          {message.content}
        </p>
        {message.actions?.length ? (
          <div className="mt-5 flex flex-wrap gap-2">
            {message.actions.map((action) => (
              <button
                key={action.id}
                type="button"
                onClick={() => void onAction(action)}
                disabled={busy}
                className={cn(
                  "px-4 py-2 rounded-full border text-xs font-bold transition-all cursor-pointer min-h-[44px] disabled:opacity-50",
                  isSystem || !isUser
                    ? "border-aura-primary/20 bg-aura-primary/5 text-aura-primary hover:bg-aura-primary hover:text-white"
                    : "border-white/20 bg-white/10 text-white hover:bg-white/15",
                )}
              >
                {action.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {isUser ? (
        <div className="w-9 h-9 rounded-xl bg-aura-surface-container-highest shrink-0 mt-1 flex items-center justify-center text-xs font-black text-aura-on-surface-variant shadow-sm">
          You
        </div>
      ) : null}
    </div>
  );
}

function PersonaStudioPreview({
  preview,
}: {
  preview: NonNullable<PersonaStudioSessionState["preview"]>;
}) {
  const persona = preview.persona || {};
  const readiness = preview.readiness || {};
  const checks = readiness.checks || {};
  const readinessPills = [
    { key: "status_ready", label: "Status Ready" },
    { key: "has_tts_voice", label: "Voice" },
    { key: "has_avatar_image", label: "Avatar Image" },
    { key: "has_avatar_asset", label: "Media Asset" },
    { key: "has_heygen_avatar_id", label: "HeyGen" },
  ];

  return (
    <div className="rounded-3xl border border-aura-outline-variant/10 bg-aura-surface-container-low p-6 shadow-sm">
      <div className="flex flex-col gap-5 md:flex-row">
        <div className="w-full md:w-44 shrink-0">
          <div className="aspect-[4/5] overflow-hidden rounded-2xl bg-aura-surface-container-high">
            {preview.image_url ? (
              <img
                src={preview.image_url}
                alt={String(persona.display_name || "Persona preview")}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-aura-on-surface-variant">
                <Sparkles className="h-6 w-6" />
              </div>
            )}
          </div>
        </div>
        <div className="flex-1 space-y-4">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-aura-on-surface-variant">
              Persona Preview
            </p>
            <h3 className="mt-2 text-xl font-black text-aura-on-surface font-headline">
              {String(persona.display_name || persona.persona_id || "Untitled Persona")}
            </h3>
            <p className="mt-1 text-sm text-aura-on-surface-variant">
              {String(persona.language || "Language pending")} - {String(persona.tts_voice || "Voice pending")}
            </p>
          </div>
          {persona.avatar_prompt ? (
            <p className="text-sm leading-relaxed text-aura-on-surface">
              {String(persona.avatar_prompt)}
            </p>
          ) : null}
          {readiness.blocking_reason ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {String(readiness.blocking_reason)}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {readinessPills.map((item) => {
              const active = Boolean(checks[item.key]);
              return (
                <span
                  key={item.key}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-[11px] font-bold uppercase tracking-tight",
                    active
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-aura-outline-variant/30 bg-white text-aura-on-surface-variant",
                  )}
                >
                  {active ? <Check className="h-3.5 w-3.5" /> : null}
                  {item.label}
                </span>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
