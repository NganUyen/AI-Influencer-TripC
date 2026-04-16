/**
 * Simple skeleton for Publishing tab
 */
export function PublishingTabSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="h-8 bg-aura-surface-container rounded-lg w-1/4"></div>

      {/* Search/filter bar */}
      <div className="h-10 bg-white rounded-xl shadow-sm"></div>

      {/* Table rows */}
      <div className="space-y-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="bg-white p-4 rounded-lg shadow-sm flex justify-between">
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-aura-surface-container rounded w-1/2"></div>
              <div className="h-3 bg-aura-surface-container rounded w-1/3"></div>
            </div>
            <div className="h-6 bg-aura-surface-container rounded w-20"></div>
          </div>
        ))}
      </div>
    </div>
  );
}
