import { NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/app/api/_helpers/backend";

export async function GET() {
  try {
    const baseUrl = getBackendBaseUrl();
    const response = await fetch(`${baseUrl}/api/content/stats`, {
      method: "GET",
      cache: "no-store",
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to fetch content stats",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
