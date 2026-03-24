import { NextRequest } from "next/server";
import { requireAdminApiAuth } from "@/app/api/_helpers/auth";
import { getBackendBaseUrl, proxyReadOnlyJson } from "@/app/api/_helpers/backend";

export async function GET(request: NextRequest) {
  const authError = requireAdminApiAuth(request);
  if (authError) {
    return authError;
  }

  const baseUrl = getBackendBaseUrl();
  return proxyReadOnlyJson(
    `${baseUrl}/api/content/stats`,
    {
      total_content: 0,
      active_campaigns: 0,
      published: 0,
    },
    "Failed to fetch content stats",
  );
}
