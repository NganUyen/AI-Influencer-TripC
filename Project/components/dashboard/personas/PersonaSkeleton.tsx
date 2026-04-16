"use client";

/**
 * PersonaSkeleton
 *
 * Skeleton placeholder for persona list items during initial load.
 * Matches PersonaListItem height and structure for smooth transition.
 *
 * Animation: Fade in/out pulse effect to signal active loading
 */

export function PersonaSkeleton() {
  return (
    <div className="group flex items-center gap-3 p-3 rounded-lg">
      {/* Avatar Placeholder */}
      <div className="w-10 h-10 bg-aura-surface-container/30 rounded-full animate-pulse shrink-0" />

      {/* Text Content Placeholders */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* Display Name Line */}
        <div className="h-3 bg-aura-surface-container/30 rounded animate-pulse w-32" />

        {/* Status/Meta Line */}
        <div className="h-2 bg-aura-surface-container/20 rounded animate-pulse w-24" />
      </div>

      {/* Right Action Indicator */}
      <div className="w-5 h-5 bg-aura-surface-container/20 rounded animate-pulse shrink-0" />
    </div>
  );
}
