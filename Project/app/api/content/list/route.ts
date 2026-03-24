import { NextRequest } from "next/server";
import { requireAdminApiAuth } from "@/app/api/_helpers/auth";
import { getBackendBaseUrl, proxyReadOnlyJson } from "@/app/api/_helpers/backend";

export async function GET(request: NextRequest) {
  const authError = requireAdminApiAuth(request);
  if (authError) {
    return authError;
  }

  const limit = request.nextUrl.searchParams.get("limit") || "20";
  const baseUrl = getBackendBaseUrl();
  return proxyReadOnlyJson(
    `${baseUrl}/api/content/list?limit=${encodeURIComponent(limit)}`,
    {
      items: [],
    },
    "Failed to list content",
  );
}
