import { Suspense } from "react";
import CustomerDashboard from "@/components/customer-dashboard";

export default function DashboardPage() {
  return (
    <Suspense fallback={null}>
      <CustomerDashboard />
    </Suspense>
  );
}
