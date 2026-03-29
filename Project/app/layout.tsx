import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "react-hot-toast";

import { RUNTIME_PUBLIC_ENV_ROUTE } from "@/lib/public-env-server";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Influencer Factory",
  description:
    "AI-driven marketing orchestration platform with autonomous content generation and distribution",
  keywords: [
    "AI",
    "marketing",
    "automation",
    "influencer",
    "content generation",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <script src={RUNTIME_PUBLIC_ENV_ROUTE} />
      </head>
      <body className={inter.className}>
        {children}
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
