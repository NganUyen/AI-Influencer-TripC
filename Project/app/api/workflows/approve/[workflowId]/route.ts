import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

type Params = {
  params: {
    workflowId: string;
  };
};

export async function POST(request: NextRequest, { params }: Params) {
  try {
    const payload = await request.json();
    const approved = Boolean(payload?.approved);
    const feedback = payload?.feedback ? String(payload.feedback) : "";

    const baseUrl = getBackendBaseUrl();
    const url = new URL(
      `${baseUrl}/api/workflows/approve/${params.workflowId}`,
    );
    url.searchParams.set("approved", String(approved));
    if (feedback) {
      url.searchParams.set("feedback", feedback);
    }

    const response = await fetch(url.toString(), {
      method: "POST",
      cache: "no-store",
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to approve workflow",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
