"""Website review service for Telegram video planning."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from services.browser_automation import BrowserAutomationService
from services.contracts import (
    WebPageReviewContract,
    WebPageReviewFindingContract,
)
from services.openclaw_service import OpenClawService

logger = logging.getLogger(__name__)


class WebsiteReviewService:
    JINA_READER_BASE = "https://r.jina.ai/"
    FETCH_TIMEOUT = 20.0
    MAX_SOURCE_CHARS = 12000

    @classmethod
    def normalize_url(cls, raw_url: str) -> str:
        normalized = str(raw_url or "").strip()
        if not normalized:
            return ""
        parsed = urlparse(normalized)
        if parsed.scheme:
            return normalized
        return f"https://{normalized}"

    @classmethod
    def _host_label(cls, url: str) -> str:
        host = urlparse(url).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or url

    @classmethod
    async def _fetch_with_jina(cls, normalized_url: str) -> str:
        jina_url = f"{cls.JINA_READER_BASE}{normalized_url}"
        async with httpx.AsyncClient(timeout=cls.FETCH_TIMEOUT) as client:
            response = await client.get(jina_url)
            response.raise_for_status()
            return response.text.strip()

    @classmethod
    async def _fetch_with_browser(cls, normalized_url: str) -> str:
        browser = BrowserAutomationService()
        try:
            return (await browser.get_page_content(normalized_url)).strip()
        finally:
            try:
                await browser.close()
            except Exception:
                logger.debug("Browser close failed after URL review", exc_info=True)

    @classmethod
    async def _fetch_source(cls, normalized_url: str) -> tuple[str, str]:
        try:
            content = await cls._fetch_with_jina(normalized_url)
            if content:
                return content[: cls.MAX_SOURCE_CHARS], "jina_reader"
        except Exception as exc:
            logger.warning("Jina fetch failed for %s: %s", normalized_url, exc)

        try:
            content = await cls._fetch_with_browser(normalized_url)
            if content:
                return content[: cls.MAX_SOURCE_CHARS], "browser_capture"
        except Exception as exc:
            logger.warning("Browser fetch failed for %s: %s", normalized_url, exc)

        return "", "manual_summary"

    @classmethod
    def _build_prompt(cls, *, objective: str, normalized_url: str, source_text: str) -> str:
        return (
            "Review this website for a Telegram-based video planning agent.\n\n"
            f"Objective: {objective or 'General product review'}\n"
            f"Target URL: {normalized_url}\n\n"
            "Analyze the source and return ONLY valid JSON with exactly these keys:\n"
            "{\n"
            '  "page_title": "...",\n'
            '  "suggested_objective": "A concise content objective for an AI influencer video review based on this page.",\n'
            '  "product_summary": "...",\n'
            '  "access_level": "public_page_only|has_logged_in_access|login_required_but_not_available|unknown",\n'
            '  "login_required": true,\n'
            '  "visible_features": [{"label": "...", "summary": "...", "evidence": ["..."], "source_url": "..."}],\n'
            '  "visible_flows": [{"label": "...", "summary": "...", "evidence": ["..."], "source_url": "..."}],\n'
            '  "recording_candidates": ["..."],\n'
            '  "risks": ["..."],\n'
            '  "assumptions": ["..."]\n'
            "}\n\n"
            "Rules:\n"
            "- Keep each list concise.\n"
            "- Prefer what is directly supported by the page content.\n"
            "- Mark login_required=true only if the source strongly suggests account-only flows.\n"
            "- Do not include markdown fences.\n\n"
            f"Source text:\n{source_text[: cls.MAX_SOURCE_CHARS]}"
        )

    @classmethod
    def _fallback_review(
        cls,
        *,
        normalized_url: str,
        source_text: str,
        fetch_method: str,
    ) -> WebPageReviewContract:
        host = cls._host_label(normalized_url)
        lowered = source_text.lower()
        login_required = any(
            token in lowered
            for token in ["log in", "login", "sign in", "dashboard", "account"]
        )
        access_level = "has_logged_in_access" if login_required else "unknown"
        snippets = []
        for part in re.split(r"\n+", source_text):
            cleaned = re.sub(r"\s+", " ", part).strip()
            if len(cleaned) >= 24:
                snippets.append(cleaned)
            if len(snippets) >= 2:
                break
        features = []
        if snippets:
            features.append(
                WebPageReviewFindingContract(
                    label="Observed page content",
                    summary=snippets[0][:240],
                    evidence=snippets[:2],
                    source_url=normalized_url,
                )
            )
        return WebPageReviewContract(
            target_url=normalized_url,
            normalized_url=normalized_url,
            page_title=host,
            product_summary=(
                snippets[0][:280]
                if snippets
                else f"Captured {host} for downstream planning, but detailed AI review was unavailable."
            ),
            page_fetch_method=fetch_method,
            access_level=access_level,
            login_required=login_required,
            visible_features=features,
            visible_flows=[],
            recording_candidates=[
                "Show the product homepage or landing message",
            ],
            risks=(
                ["Detailed AI review was unavailable, so this summary is heuristic."]
                if not snippets
                else []
            ),
            assumptions=[
                "The provided URL represents the intended product surface for the video plan.",
            ],
        )

    @classmethod
    def _coerce_findings(cls, items: Any, normalized_url: str) -> list[WebPageReviewFindingContract]:
        findings: list[WebPageReviewFindingContract] = []
        if not isinstance(items, list):
            return findings
        for item in items[:6]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if not label or not summary:
                continue
            evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
            findings.append(
                WebPageReviewFindingContract(
                    label=label[:120],
                    summary=summary[:400],
                    evidence=[str(entry).strip()[:240] for entry in evidence if str(entry).strip()][:3],
                    source_url=str(item.get("source_url") or normalized_url).strip() or normalized_url,
                )
            )
        return findings

    @classmethod
    def _coerce_review(
        cls,
        *,
        normalized_url: str,
        raw_payload: Dict[str, Any],
        fetch_method: str,
    ) -> WebPageReviewContract:
        access_level = str(raw_payload.get("access_level") or "unknown").strip()
        login_required = bool(raw_payload.get("login_required"))
        if login_required and access_level == "unknown":
            access_level = "has_logged_in_access"
        return WebPageReviewContract(
            target_url=normalized_url,
            normalized_url=normalized_url,
            page_title=str(raw_payload.get("page_title") or cls._host_label(normalized_url)).strip() or cls._host_label(normalized_url),
            suggested_objective=str(raw_payload.get("suggested_objective") or "").strip() or None,
            product_summary=str(raw_payload.get("product_summary") or "").strip(),
            page_fetch_method=fetch_method,
            access_level=access_level,
            login_required=login_required,
            visible_features=cls._coerce_findings(raw_payload.get("visible_features"), normalized_url),
            visible_flows=cls._coerce_findings(raw_payload.get("visible_flows"), normalized_url),
            recording_candidates=[
                str(item).strip()[:240]
                for item in (raw_payload.get("recording_candidates") or [])
                if str(item).strip()
            ][:6],
            risks=[str(item).strip()[:240] for item in (raw_payload.get("risks") or []) if str(item).strip()][:6],
            assumptions=[str(item).strip()[:240] for item in (raw_payload.get("assumptions") or []) if str(item).strip()][:6],
        )

    @classmethod
    async def review_url(
        cls,
        url: str,
        *,
        objective: str = "",
        user_id: str = "system",
    ) -> WebPageReviewContract:
        normalized_url = cls.normalize_url(url)
        if not normalized_url:
            raise ValueError("URL is required for website review")

        source_text, fetch_method = await cls._fetch_source(normalized_url)
        if not source_text:
            return cls._fallback_review(
                normalized_url=normalized_url,
                source_text="",
                fetch_method=fetch_method,
            )

        service = OpenClawService()
        try:
            raw = await service.execute_task(
                task_type="website_review_planner",
                prompt=cls._build_prompt(
                    objective=objective,
                    normalized_url=normalized_url,
                    source_text=source_text,
                ),
                user_id=user_id,
                context={
                    "objective": objective,
                    "target_url": normalized_url,
                    "source_excerpt": source_text[:4000],
                    "fetch_method": fetch_method,
                },
            )
            if not isinstance(raw, dict):
                raise ValueError("Website review response was not a JSON object")
            return cls._coerce_review(
                normalized_url=normalized_url,
                raw_payload=raw,
                fetch_method=fetch_method,
            )
        except Exception as exc:
            logger.warning("Website review AI analysis failed for %s: %s", normalized_url, exc, exc_info=True)
            return cls._fallback_review(
                normalized_url=normalized_url,
                source_text=source_text,
                fetch_method=fetch_method,
            )
        finally:
            await service.close()
