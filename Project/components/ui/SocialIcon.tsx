"use client";

import * as si from "simple-icons";
import { cn } from "@/lib/utils";

interface SocialIconProps {
  platform: string;
  size?: number;
  className?: string;
  /**
   * Whether to use official brand colors.
   * Defaults to true as requested for "proper SaaS look".
   */
  colored?: boolean;
}

/**
 * Mapping of platform slugs to simple-icons export names.
 */
const PLATFORM_MAP: Record<string, string> = {
  linkedin: "siLinkedin",
  twitter: "siX",
  x: "siX",
  youtube: "siYoutube",
  instagram: "siInstagram",
  tiktok: "siTiktok",
  facebook: "siFacebook",
  telegram: "siTelegram",
  openai: "siOpenai",
  chatgpt: "siOpenai",
  anthropic: "siAnthropic",
  github: "siGithub",
  discord: "siDiscord",
  threads: "siThreads",
};

export function SocialIcon({ platform, size = 16, className, colored = true }: SocialIconProps) {
  const key = platform.toLowerCase();
  const siKey = PLATFORM_MAP[key];
  const icon = siKey ? (si as any)[siKey] : null;

  if (!icon) {
    // Fallback: initial letter if no icon found
    return (
      <span
        className={cn("inline-flex items-center justify-center rounded font-bold text-xs bg-muted text-muted-foreground", className)}
        style={{ width: size, height: size, fontSize: size * 0.6 }}
      >
        {platform.charAt(0).toUpperCase()}
      </span>
    );
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={colored ? `#${icon.hex}` : "currentColor"}
      className={cn("transition-opacity", !colored && "opacity-70", className)}
      aria-label={platform}
      role="img"
    >
      <title>{icon.title}</title>
      <path d={icon.path} />
    </svg>
  );
}

