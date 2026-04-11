import Link from "next/link";
import { Home, LayoutDashboard, FileText, Users, Settings } from "lucide-react";

export default function Sidebar() {
  return (
    <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 h-screen sticky top-0">
      <div className="p-6 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          AI Influencer
        </h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">Factory</p>
      </div>

      <nav className="px-4 py-6 space-y-1">
        <NavItem href="/" icon={<Home size={20} />} label="Home" />
        <NavItem
          href="/dashboard"
          icon={<LayoutDashboard size={20} />}
          label="Dashboard"
        />
        <NavItem
          href="/content"
          icon={<FileText size={20} />}
          label="Content"
        />
        <NavItem href="/personas" icon={<Users size={20} />} label="Personas" />
        <NavItem
          href="/settings"
          icon={<Settings size={20} />}
          label="Settings"
        />
      </nav>
    </aside>
  );
}

function NavItem({
  href,
  icon,
  label,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center space-x-3 px-4 py-3 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}
