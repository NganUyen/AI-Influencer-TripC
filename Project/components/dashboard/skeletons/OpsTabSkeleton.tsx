/**
 * Simple skeleton for Ops (AI Operations) tab
 */
export function OpsTabSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Title */}
      <div className="h-8 bg-aura-surface-container rounded-lg w-1/4"></div>

      {/* Main content area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sidebar */}
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 bg-white rounded-xl shadow-sm p-3">
              <div className="h-4 bg-aura-surface-container rounded w-full"></div>
            </div>
          ))}
        </div>

        {/* Main panel */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl shadow-sm">
          <div className="h-6 bg-aura-surface-container rounded w-1/3 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-aura-surface-container rounded"></div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
