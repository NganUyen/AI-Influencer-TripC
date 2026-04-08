import { NextRequest } from "next/server";
import { requireAdminApiAuth } from "@/app/api/_helpers/auth";
import { getBackendBaseUrl, proxyReadOnlyJson } from "@/app/api/_helpers/backend";

export async function GET(request: NextRequest) {
  const authError = requireAdminApiAuth(request);
  if (authError) {
    return authError;
  }

  const baseUrl = getBackendBaseUrl();
  const searchParams = request.nextUrl.searchParams.toString();
  const targetUrl = `${baseUrl}/api/quota/summary${searchParams ? `?${searchParams}` : ""}`;
  
  return proxyReadOnlyJson(
    targetUrl,
    {
      total_cost_usd: 0,
      providers: [],
      time_period: "30_days",
    },
    "Failed to fetch quota summary",
  );
}
