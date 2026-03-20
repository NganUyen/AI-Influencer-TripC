import { NextRequest } from "next/server";
import { requireAdminApiAuth } from "@/app/api/_helpers/auth";
import { getBackendBaseUrl, proxyReadOnlyJson } from "@/app/api/_helpers/backend";

type Params = {
  params: Promise<{
    workflowId: string;
  }>;
};

export async function GET(_request: NextRequest, { params }: Params) {
  const authError = requireAdminApiAuth(_request);
  if (authError) {
    return authError;
  }

  const { workflowId } = await params;
  const baseUrl = getBackendBaseUrl();
  return proxyReadOnlyJson(
    `${baseUrl}/api/workflows/status/${workflowId}`,
    {
      workflow_id: workflowId,
      status: {
        status: "unknown",
        current_step: "backend_unavailable",
      },
    },
    "Failed to fetch workflow status",
  );
}
