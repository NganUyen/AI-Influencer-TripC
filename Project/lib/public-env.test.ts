import {
  buildTelegramBotLaunchUrl,
  deriveTelegramBotUsername,
  getClientTelegramBotLaunchUrl,
  normalizeTelegramBotUrl,
} from "@/lib/public-env";
import { getServerPublicEnv } from "@/lib/public-env-server";

describe("Telegram public env helpers", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    window.__AI_INFLUENCER_PUBLIC_ENV__ = {};
    process.env = { ...originalEnv };
    delete process.env.NEXT_PUBLIC_TELEGRAM_BOT_URL;
    delete process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("derives the bot username from tg deep links", () => {
    expect(
      deriveTelegramBotUsername("tg://resolve?domain=TripCInternBot&start=secure-token"),
    ).toBe("TripCInternBot");
  });

  it("normalizes tg deep links into browser-safe launch URLs", () => {
    expect(
      normalizeTelegramBotUrl("tg://resolve?domain=TripCInternBot&start=existing"),
    ).toBe("https://t.me/TripCInternBot?start=existing");

    expect(
      buildTelegramBotLaunchUrl({
        botUrl: "tg://resolve?domain=TripCInternBot",
        startToken: "secure-token",
      }),
    ).toBe("https://t.me/TripCInternBot?start=secure-token");
  });

  it("builds browser-safe launch URLs from runtime env and server env", () => {
    window.__AI_INFLUENCER_PUBLIC_ENV__ = {
      NEXT_PUBLIC_TELEGRAM_BOT_URL: "tg://resolve?domain=TripCInternBot",
    };
    process.env.NEXT_PUBLIC_TELEGRAM_BOT_URL = "tg://resolve?domain=TripCInternBot";

    expect(getClientTelegramBotLaunchUrl("secure-token")).toBe(
      "https://t.me/TripCInternBot?start=secure-token",
    );

    const publicEnv = getServerPublicEnv();
    expect(publicEnv.NEXT_PUBLIC_TELEGRAM_BOT_URL).toBe("https://t.me/TripCInternBot");
    expect(publicEnv.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME).toBe("TripCInternBot");
  });
});
