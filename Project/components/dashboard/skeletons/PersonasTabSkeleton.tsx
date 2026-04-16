/**
 * Simple skeleton for Personas tab
 */
export function PersonasTabSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="h-8 bg-aura-surface-container rounded-lg w-1/4"></div>
        <div className="h-10 bg-aura-surface-container rounded-full w-32"></div>
      </div>

      {/* Grid of persona cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="bg-white rounded-2xl shadow-sm overflow-hidden">
            <div className="h-40 bg-aura-surface-container"></div>
            <div className="p-4 space-y-3">
              <div className="h-5 bg-aura-surface-container rounded w-3/4"></div>
              <div className="h-4 bg-aura-surface-container rounded w-1/2"></div>
              <div className="h-10 bg-aura-surface-container rounded w-full"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
