/**
 * Simple skeleton for Live Feed tab
 */
export function LiveFeedTabSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="h-8 bg-aura-surface-container rounded-lg w-1/4"></div>

      {/* List of feed items */}
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="bg-white p-4 rounded-2xl shadow-sm">
            <div className="flex gap-4">
              <div className="w-20 h-20 bg-aura-surface-container rounded"></div>
              <div className="flex-1 space-y-3">
                <div className="h-5 bg-aura-surface-container rounded w-3/4"></div>
                <div className="h-4 bg-aura-surface-container rounded w-full"></div>
                <div className="h-4 bg-aura-surface-container rounded w-2/3"></div>
                <div className="h-8 bg-aura-surface-container rounded w-20"></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
