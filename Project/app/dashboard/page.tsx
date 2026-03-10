export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="container mx-auto p-8">
        <h1 className="text-4xl font-bold mb-8 text-gray-900 dark:text-white">
          Dashboard
        </h1>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard title="Total Content" value="0" icon="📝" />
          <StatCard title="Active Campaigns" value="0" icon="🚀" />
          <StatCard title="Engagement Rate" value="0%" icon="📊" />
          <StatCard title="AI Personas" value="0" icon="👤" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
              Recent Content
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              No content generated yet. Start your first campaign!
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
              Upcoming Posts
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              No scheduled posts. Create a content calendar!
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: string;
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
            {title}
          </p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
        </div>
        <div className="text-4xl">{icon}</div>
      </div>
    </div>
  );
}
