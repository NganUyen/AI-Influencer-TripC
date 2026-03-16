import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

export async function POST(request: NextRequest) {
  try {
    const payload = await request.json();
    const userId = payload?.user_id;
    const brandConfig = payload?.brand_config || {};

    if (!userId) {
      return NextResponse.json(
        { error: "user_id is required" },
        { status: 400 },
      );
    }

    const baseUrl = getBackendBaseUrl();
    const url = new URL(`${baseUrl}/api/workflows/start-weekly`);
    url.searchParams.set("user_id", String(userId));

    const response = await fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(brandConfig),
      cache: "no-store",
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to start workflow",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
