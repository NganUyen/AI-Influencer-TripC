import { NextResponse } from "next/server";

import { getServerPublicEnv } from "@/lib/public-env-server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  const payload = JSON.stringify(getServerPublicEnv()).replace(/</g, "\\u003c");

  return new NextResponse(
    `window.__AI_INFLUENCER_PUBLIC_ENV__=${payload};`,
    {
      headers: {
        "Content-Type": "application/javascript; charset=utf-8",
        "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
      },
    },
  );
}
