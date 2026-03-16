import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

type Params = {
  params: {
    workflowId: string;
  };
};

export async function GET(_request: NextRequest, { params }: Params) {
  try {
    const baseUrl = getBackendBaseUrl();
    const response = await fetch(
      `${baseUrl}/api/workflows/status/${params.workflowId}`,
      {
        method: "GET",
        cache: "no-store",
      },
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to fetch workflow status",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
