import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8 bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      <div className="max-w-4xl mx-auto text-center space-y-8 animate-fade-in">
        <h1 className="text-6xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
          AI Influencer Factory
        </h1>

        <p className="text-xl text-gray-700 dark:text-gray-300 max-w-2xl mx-auto">
          Your AI-driven marketing orchestration platform with autonomous
          content generation and multi-platform distribution.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mt-8">
          <Link
            href="/dashboard"
            className="px-8 py-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold shadow-lg hover:shadow-xl"
          >
            Go to Dashboard
          </Link>

          <Link
            href="/auth"
            className="px-8 py-4 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors font-semibold shadow-lg hover:shadow-xl border border-gray-200 dark:border-gray-700"
          >
            Sign In
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16">
          <FeatureCard
            icon="🤖"
            title="AI-Powered"
            description="Autonomous content generation using GPT-4o and Claude 3.5"
          />
          <FeatureCard
            icon="📅"
            title="Smart Scheduling"
            description="Temporal.io orchestration for reliable workflow execution"
          />
          <FeatureCard
            icon="🌐"
            title="Multi-Platform"
            description="Distribute content across Twitter, LinkedIn, TikTok, and more"
          />
        </div>
      </div>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md hover:shadow-lg transition-shadow">
      <div className="text-4xl mb-3">{icon}</div>
      <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-white">
        {title}
      </h3>
      <p className="text-gray-600 dark:text-gray-400">{description}</p>
    </div>
  );
}
