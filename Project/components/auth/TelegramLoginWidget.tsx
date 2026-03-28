"use client";

import { useEffect, useRef } from "react";

interface Props {
  botName: string;
  dataOnauth: (user: any) => void;
  buttonSize?: "large" | "medium" | "small";
  cornerRadius?: number;
  requestAccess?: "write";
  usePic?: boolean;
}

declare global {
  interface Window {
    onTelegramAuth: (user: any) => void;
  }
}

export const TelegramLoginWidget = ({
  botName,
  dataOnauth,
  buttonSize = "large",
  cornerRadius = 20,
  requestAccess = "write",
  usePic = true,
}: Props) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.onTelegramAuth = (user: any) => {
      dataOnauth(user);
    };

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botName);
    script.setAttribute("data-size", buttonSize);
    script.setAttribute("data-radius", cornerRadius.toString());
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", requestAccess);
    if (!usePic) {
      script.setAttribute("data-userpic", "false");
    }

    if (containerRef.current) {
      containerRef.current.appendChild(script);
    }

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
      delete (window as any).onTelegramAuth;
    };
  }, [botName, dataOnauth, buttonSize, cornerRadius, requestAccess, usePic]);

  return <div ref={containerRef} />;
};
