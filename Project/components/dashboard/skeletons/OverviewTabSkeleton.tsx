/**
 * Simple skeleton for Overview tab
 * Basic gray boxes without exact layout matching
 */
export function OverviewTabSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header skeleton */}
      <div className="h-8 bg-aura-surface-container rounded-lg w-1/4"></div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white p-4 rounded-2xl shadow-sm">
            <div className="h-4 bg-aura-surface-container rounded w-3/4 mb-3"></div>
            <div className="h-6 bg-aura-surface-container rounded w-1/2"></div>
          </div>
        ))}
      </div>

      {/* Large content area */}
      <div className="bg-white p-6 rounded-2xl shadow-sm">
        <div className="h-6 bg-aura-surface-container rounded w-1/4 mb-4"></div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-aura-surface-container rounded"></div>
          ))}
        </div>
      </div>
    </div>
  );
}
