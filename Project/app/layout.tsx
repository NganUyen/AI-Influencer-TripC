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
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Lexend:wght@300;400;500;600&display=swap" rel="stylesheet" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />
      </head>
      <body className={inter.className}>
        {children}
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
