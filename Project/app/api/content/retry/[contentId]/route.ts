import { NextRequest, NextResponse } from "next/server";
import {
  getInternalApiHeaders,
  requireAdminApiAuth,
} from "@/app/api/_helpers/auth";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

type Params = {
  params: {
    contentId: string;
  };
};

export async function POST(_request: NextRequest, { params }: Params) {
  const authError = requireAdminApiAuth(_request);
  if (authError) {
    return authError;
  }

  try {
    const baseUrl = getBackendBaseUrl();
    const response = await fetch(
      `${baseUrl}/api/content/retry/${params.contentId}`,
      {
        method: "POST",
        headers: getInternalApiHeaders(),
        cache: "no-store",
      },
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to retry content publish",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
