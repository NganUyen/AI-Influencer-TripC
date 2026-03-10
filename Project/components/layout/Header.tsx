import { Bell, User } from "lucide-react";

export default function Header() {
  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-8 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Welcome back!
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Here's what's happening with your campaigns today.
          </p>
        </div>

        <div className="flex items-center space-x-4">
          <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors relative">
            <Bell size={20} className="text-gray-600 dark:text-gray-400" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
          </button>

          <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            <User size={20} className="text-gray-600 dark:text-gray-400" />
          </button>
        </div>
      </div>
    </header>
  );
}
