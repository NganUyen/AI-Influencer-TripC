import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

export async function GET(request: NextRequest) {
  try {
    const limit = request.nextUrl.searchParams.get("limit") || "20";
    const baseUrl = getBackendBaseUrl();
    const response = await fetch(
      `${baseUrl}/api/content/list?limit=${encodeURIComponent(limit)}`,
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
        error: "Failed to list content",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
