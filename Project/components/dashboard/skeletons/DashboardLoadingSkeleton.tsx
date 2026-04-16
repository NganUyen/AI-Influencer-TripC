/**
 * Generic loading skeleton wrapper for dashboard pages
 * Displays at full screen height with layout structure
 */
export function DashboardLoadingSkeleton() {
  return (
    <div className="min-h-screen bg-aura-surface px-4 py-8 animate-pulse">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header skeleton */}
        <div className="space-y-3 mb-8">
          <div className="h-10 bg-white rounded-xl w-1/3"></div>
          <div className="h-4 bg-aura-surface-container rounded w-2/3"></div>
        </div>

        {/* Main grid layout */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main content */}
          <div className="lg:col-span-3 space-y-6">
            {/* Large hero section */}
            <div className="bg-white p-6 rounded-2xl shadow-sm h-64"></div>

            {/* Two column stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {[1, 2].map((i) => (
                <div key={i} className="bg-white p-6 rounded-2xl shadow-sm h-40"></div>
              ))}
            </div>

            {/* Content section */}
            <div className="bg-white p-6 rounded-2xl shadow-sm">
              <div className="h-6 bg-aura-surface-container rounded w-1/4 mb-4"></div>
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 bg-aura-surface-container rounded"></div>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white p-4 rounded-2xl shadow-sm h-32"></div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
