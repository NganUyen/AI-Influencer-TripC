import { Suspense } from "react";
import { notFound } from "next/navigation";

import CustomerDashboard from "@/components/customer-dashboard";
import { getDashboardTabIdFromSegments } from "@/lib/dashboard-tabs";

type DashboardPageProps = {
  params: Promise<{
    tab?: string[];
  }>;
};

export default async function DashboardPage({ params }: DashboardPageProps) {
  const { tab } = await params;
  const activeTab = getDashboardTabIdFromSegments(tab);

  if (!activeTab) {
    notFound();
  }

  return (
    <Suspense fallback={null}>
      <CustomerDashboard activeTab={activeTab} />
    </Suspense>
  );
}
