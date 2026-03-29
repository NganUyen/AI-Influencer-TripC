from __future__ import annotations

import argparse
import asyncio
from typing import Iterable, List, Sequence

from services.database_service import DatabaseService
from services.supabase_auth_bridge_service import (
    SupabaseAuthBridgeCollisionError,
    SupabaseAuthBridgeError,
    SupabaseAuthBridgeService,
)
from services.telegram_identity_service import TelegramIdentity, TelegramIdentityService


ACTIVE_LINK_QUERY = """
SELECT
    tul.chat_id,
    tul.telegram_username,
    u.id,
    u.email,
    u.name,
    u.avatar_url
FROM public.telegram_user_links tul
JOIN public.users u
  ON u.id = tul.user_id
WHERE tul.revoked_at IS NULL
ORDER BY tul.linked_at NULLS LAST, tul.chat_id
"""


ORPHAN_TELEGRAM_USER_QUERY = """
SELECT
    NULL::bigint AS chat_id,
    NULL::text AS telegram_username,
    u.id,
    u.email,
    u.name,
    u.avatar_url
FROM public.users u
WHERE u.email ~ '^tg_[0-9]+@ai-influencer\\.invalid$'
  AND NOT EXISTS (
      SELECT 1
      FROM public.telegram_user_links tul
      WHERE tul.user_id = u.id
        AND tul.revoked_at IS NULL
  )
ORDER BY u.created_at NULLS LAST, u.id
"""


def _chat_id_from_email(email: str | None) -> int | None:
    normalized = str(email or "").strip().lower()
    prefix = "tg_"
    suffix = "@ai-influencer.invalid"
    if not normalized.startswith(prefix) or not normalized.endswith(suffix):
        return None
    chat_id = normalized[len(prefix) : -len(suffix)]
    if not chat_id.isdigit():
        return None
    return int(chat_id)


def _identity_from_row(row) -> TelegramIdentity | None:
    raw_chat_id = row.get("chat_id")
    chat_id = int(raw_chat_id) if raw_chat_id is not None else _chat_id_from_email(row.get("email"))
    if chat_id is None:
        return None

    telegram_username = row.get("telegram_username")
    display_name = row.get("name") or TelegramIdentityService.default_display_name(
        chat_id,
        telegram_username=telegram_username,
    )
    return TelegramIdentity(
        chat_id=chat_id,
        user_id=str(row["id"]),
        email=str(row.get("email") or TelegramIdentityService.email_for_chat(chat_id)),
        display_name=display_name,
        avatar_url=row.get("avatar_url"),
        telegram_username=telegram_username,
    )


async def fetch_backfill_candidates() -> List[TelegramIdentity]:
    pool = await DatabaseService.get_pool()
    async with pool.acquire() as conn:
        rows: Sequence = [
            *(await conn.fetch(ACTIVE_LINK_QUERY)),
            *(await conn.fetch(ORPHAN_TELEGRAM_USER_QUERY)),
        ]

    identities: List[TelegramIdentity] = []
    seen_user_ids: set[str] = set()
    for row in rows:
        identity = _identity_from_row(row)
        if identity is None or identity.user_id in seen_user_ids:
            continue
        seen_user_ids.add(identity.user_id)
        identities.append(identity)
    return identities


async def run_backfill(*, apply_changes: bool) -> dict[str, int]:
    identities = await fetch_backfill_candidates()
    summary = {
        "candidates": len(identities),
        "created": 0,
        "updated": 0,
        "collisions": 0,
        "failed": 0,
    }

    for identity in identities:
        descriptor = (
            f"user_id={identity.user_id} chat_id={identity.chat_id} email={identity.email}"
        )
        if not apply_changes:
            print(f"DRY RUN {descriptor}")
            continue

        try:
            result = await SupabaseAuthBridgeService.ensure_telegram_auth_user(identity)
        except SupabaseAuthBridgeCollisionError as exc:
            summary["collisions"] += 1
            print(f"COLLISION {descriptor}: {exc}")
            continue
        except SupabaseAuthBridgeError as exc:
            summary["failed"] += 1
            print(f"FAILED {descriptor}: {exc}")
            continue

        summary[result.status] += 1
        print(f"{result.status.upper()} {descriptor}")

    return summary


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision missing Supabase Auth users for Telegram-linked customers."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Create or update Supabase Auth users.",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="List the users that would be provisioned without changing Auth.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


async def _async_main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    apply_changes = bool(args.apply)
    summary = await run_backfill(apply_changes=apply_changes)
    mode = "apply" if apply_changes else "dry-run"
    print(
        "SUMMARY "
        f"mode={mode} "
        f"candidates={summary['candidates']} "
        f"created={summary['created']} "
        f"updated={summary['updated']} "
        f"collisions={summary['collisions']} "
        f"failed={summary['failed']}"
    )
    return 0 if summary["failed"] == 0 else 1


def main(argv: Iterable[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
