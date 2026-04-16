"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

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
}

interface PersonaGroupProps {
  title: string;
  subtitle?: string;
  personas: Persona[];
  children?: React.ReactNode;
  selectedPersonaId: string | null;
  onSelectPersona: (id: string) => void;
  isExpandedByDefault?: boolean;
  isLoading?: boolean;
}

/**
 * PersonaGroup
 *
 * Expandable/collapsible persona group container.
 * Displays group header with toggle and count badge.
 * Renders persona items or skeleton loaders based on loading state.
 *
 * Behavior:
 * - Click header to expand/collapse
 * - Shows count of personas in badge
 * - Displays skeleton items during loading
 * - All personas visible by default (both groups start expanded)
 *
 * @param title - Group label (e.g., "Default Personas", "Your Personas")
 * @param subtitle - Optional helper text
 * @param personas - Array of personas to display
 * @param children - Custom render function or content
 * @param selectedPersonaId - Currently selected persona ID
 * @param onSelectPersona - Callback when persona is selected
 * @param isExpandedByDefault - Start expanded (default: true)
 * @param isLoading - Show skeleton items instead of personas
 */
export function PersonaGroup({
  title,
  subtitle,
  personas,
  children,
  selectedPersonaId,
  onSelectPersona,
  isExpandedByDefault = true,
  isLoading = false,
}: PersonaGroupProps) {
  const [isExpanded, setIsExpanded] = useState(isExpandedByDefault);

  const skeletonCount = Math.max(2, Math.min(personas.length, 4));

  return (
    <div className="flex flex-col gap-3">
      {/* Group Header - Toggle & Count Badge */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between px-3 py-2 hover:bg-aura-surface-container/30 rounded-lg transition-colors group/header"
        aria-expanded={isExpanded}
        aria-controls={`group-${title}`}
      >
        <div className="flex items-center gap-2 min-w-0">
          {/* Toggle Icon */}
          <div className="flex identity-center text-aura-on-surface-variant/60 group-hover/header:text-aura-on-surface/80 transition-colors">
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </div>

          {/* Title & Subtitle */}
          <div className="flex flex-col gap-0.5 min-w-0">
            <p className="text-xs font-black uppercase tracking-widest text-aura-on-surface-variant font-label">
              {title}
            </p>
            {subtitle && (
              <p className="text-[10px] text-aura-on-surface-variant/50 font-body">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        {/* Count Badge */}
        <div className="inline-flex items-center justify-center min-w-max px-2 py-0.5 rounded-full bg-aura-surface-container text-[10px] font-bold text-aura-on-surface-variant uppercase tracking-widest ml-2">
          {personas.length}
        </div>
      </button>

      {/* Group Content - Visible when expanded */}
      {isExpanded && (
        <div
          id={`group-${title}`}
          className="flex-1 overflow-y-auto space-y-2 scrollbar-hide pr-1"
        >
          {isLoading ? (
            // Skeleton Loading State
            <>
              {Array.from({ length: skeletonCount }).map((_, i) => (
                <div
                  key={`skeleton-${i}`}
                  className="animate-fade-in"
                  style={{ animationDelay: `${i * 50}ms` }}
                >
                  {children}
                </div>
              ))}
            </>
          ) : personas.length === 0 ? (
            // Empty State
            <div className="flex flex-col items-center justify-center py-8 px-3 text-center">
              <div className="w-10 h-10 rounded-full bg-aura-surface-container/50 flex items-center justify-center mb-3">
                <span className="text-xs text-aura-on-surface-variant/50">−</span>
              </div>
              <p className="text-xs text-aura-on-surface-variant font-body">
                No personas in this group
              </p>
            </div>
          ) : (
            // Actual Content
            <>
              {children}
            </>
          )}
        </div>
      )}

      {/* Optional Divider Between Groups */}
      {/* Already handled by parent spacing, can be removed */}
    </div>
  );
}
