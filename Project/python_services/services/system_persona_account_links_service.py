from __future__ import annotations

import logging
from typing import Any, Dict, List

from services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class SystemPersonaAccountLinksService:
    @classmethod
    async def list_active_links_by_persona(
        cls,
        *,
        persona_ids: List[str],
        provider: str = "tiktok",
    ) -> Dict[str, Dict[str, Any]]:
        normalized_persona_ids = [str(item).strip() for item in persona_ids if str(item).strip()]
        if not normalized_persona_ids:
            return {}
        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (persona_id)
                        persona_id,
                        provider,
                        profile_url,
                        account_handle,
                        updated_at
                    FROM public.system_persona_account_links
                    WHERE provider = $1
                      AND is_active = true
                      AND persona_id = ANY($2::text[])
                    ORDER BY persona_id, updated_at DESC
                    """,
                    provider,
                    normalized_persona_ids,
                )
        except Exception as exc:
            logger.warning(
                "system_persona_account_links query skipped: %s", exc
            )
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            persona_id = str(row.get("persona_id") or "").strip()
            if not persona_id:
                continue
            result[persona_id] = {
                "provider": row.get("provider"),
                "profile_url": row.get("profile_url"),
                "account_handle": row.get("account_handle"),
                "source": "system_persona_account_links",
            }
        return result

    @classmethod
    async def apply_tiktok_links_to_personas(
        cls, personas: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not personas:
            return personas
        persona_ids = [
            str(item.get("persona_id") or "").strip()
            for item in personas
            if item.get("persona_id")
        ]
        link_map = await cls.list_active_links_by_persona(persona_ids=persona_ids)
        if not link_map:
            return personas

        for persona in personas:
            persona_id = str(persona.get("persona_id") or "").strip()
            if not persona_id:
                continue
            link_payload = link_map.get(persona_id)
            if not link_payload:
                continue
            channel_configs = persona.get("channel_configs")
            if not isinstance(channel_configs, dict):
                channel_configs = {}
            tiktok = channel_configs.get("tiktok")
            if not isinstance(tiktok, dict):
                tiktok = {}
            if not tiktok.get("profile_url"):
                tiktok["profile_url"] = link_payload.get("profile_url")
            if not tiktok.get("username") and link_payload.get("account_handle"):
                tiktok["username"] = link_payload.get("account_handle")
            channel_configs["tiktok"] = tiktok
            persona["channel_configs"] = channel_configs
        return personas
