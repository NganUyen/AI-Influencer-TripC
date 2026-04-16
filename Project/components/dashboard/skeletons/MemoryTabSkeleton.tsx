/**
 * Simple skeleton for Memory (Project & Memory) tab
 */
export function MemoryTabSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="h-8 bg-aura-surface-container rounded-lg w-1/4"></div>

      {/* Two column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Form sections */}
          {[1, 2].map((section) => (
            <div key={section} className="bg-white p-6 rounded-2xl shadow-sm">
              <div className="h-6 bg-aura-surface-container rounded w-1/3 mb-4"></div>
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="space-y-2">
                    <div className="h-4 bg-aura-surface-container rounded w-1/4"></div>
                    <div className="h-10 bg-aura-surface-container rounded"></div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {[1, 2].map((i) => (
            <div key={i} className="bg-white p-4 rounded-2xl shadow-sm">
              <div className="h-5 bg-aura-surface-container rounded w-2/3 mb-3"></div>
              <div className="space-y-2">
                {[1, 2].map((j) => (
                  <div key={j} className="h-8 bg-aura-surface-container rounded"></div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
