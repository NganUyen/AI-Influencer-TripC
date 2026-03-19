import { NextRequest } from "next/server";
import { requireAdminApiAuth } from "@/app/api/_helpers/auth";
import { getBackendBaseUrl, proxyReadOnlyJson } from "@/app/api/_helpers/backend";

type Params = {
  params: {
    workflowId: string;
  };
};

export async function GET(_request: NextRequest, { params }: Params) {
  const authError = requireAdminApiAuth(_request);
  if (authError) {
    return authError;
  }

  const baseUrl = getBackendBaseUrl();
  return proxyReadOnlyJson(
    `${baseUrl}/api/workflows/status/${params.workflowId}`,
    {
      workflow_id: params.workflowId,
      status: {
        status: "unknown",
        current_step: "backend_unavailable",
      },
    },
    "Failed to fetch workflow status",
  );
}
