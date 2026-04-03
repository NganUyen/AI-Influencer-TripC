"""
Official Feature Catalog Service (Phase 2b - V3.1)

Crawls URLs and extracts features using GPT-4o mini.
"""

import logging
import json
from typing import List
import httpx

from services.contracts import (
    OfficialFeatureContract,
    OfficialFeatureCatalogContract,
)
from services.ai_service import AIService

logger = logging.getLogger(__name__)


class OfficialFeatureCatalogService:
    """
    Extracts feature catalog from official URLs.

    Input:  verified_feature_urls[]
    Output: OfficialFeatureCatalogContract
    """

    JINA_READER_BASE = "https://r.jina.ai/"
    TIMEOUT_PER_URL = 15
    MAX_FEATURES_TOTAL = 10

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def extract_catalog(
        self, verified_feature_urls: List[str]
    ) -> OfficialFeatureCatalogContract:
        """
        Extract feature catalog from URLs.

        Returns:
            OfficialFeatureCatalogContract with merged features from all URLs.
            Returns empty catalog if all URLs fail (does not hard fail).
        """
        if not verified_feature_urls:
            logger.warning("No URLs provided, returning empty catalog")
            return OfficialFeatureCatalogContract()

        all_features = []
        all_terminology = {}
        visited_urls = []
        primary_source_url = verified_feature_urls[0] if verified_feature_urls else ""

        for url in verified_feature_urls:
            try:
                # Fetch markdown via Jina
                markdown = await self._fetch_markdown(url)
                if not markdown:
                    continue

                # Extract features via GPT-4o mini
                features, terminology = await self._extract_features_from_markdown(
                    markdown, url
                )

                all_features.extend(features)
                # Merge terminology - don't overwrite existing keys
                for key, value in terminology.items():
                    if key not in all_terminology:
                        all_terminology[key] = value

                visited_urls.append(url)

            except Exception as e:
                logger.warning(f"Failed to extract features from {url}: {e}")
                continue

        # Dedup features by name (case-insensitive)
        deduped_features = self._deduplicate_features(all_features)

        # Cap at MAX_FEATURES_TOTAL
        final_features = deduped_features[: self.MAX_FEATURES_TOTAL]

        # Reject features without source_url
        valid_features = [f for f in final_features if f.source_url]

        logger.info(
            f"Extracted {len(valid_features)} features from {len(visited_urls)} URLs"
        )

        return OfficialFeatureCatalogContract(
            features=valid_features,
            official_terminology=all_terminology,
            visited_urls=visited_urls,
            primary_source_url=primary_source_url,
        )

    async def _fetch_markdown(self, url: str) -> str:
        """Fetch markdown content via Jina Reader."""
        try:
            jina_url = f"{self.JINA_READER_BASE}{url}"
            async with httpx.AsyncClient(timeout=self.TIMEOUT_PER_URL) as client:
                logger.info(f"Fetching {jina_url} via Jina Reader")
                response = await client.get(jina_url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.warning(f"Failed to fetch {url} via Jina: {e}")
            return ""

    async def _extract_features_from_markdown(
        self, markdown: str, source_url: str
    ) -> tuple[List[OfficialFeatureContract], dict]:
        """
        Extract features from markdown using GPT-4o mini.

        Returns:
            (features, official_terminology)
        """
        system_prompt = "Extract product features. Return ONLY valid JSON, no markdown."

        user_prompt = f"""{markdown[:8000]}

Return JSON:
{{
  "features": [{{"name": "...", "description": "..."}}, ...],
  "official_terminology": {{"ocr_or_common_term": "official_name"}}
}}"""

        try:
            response = await self.ai_service.chat_completion(
                model="gpt-4o-mini",
                system_message=system_prompt,
                user_message=user_prompt,
                temperature=0.0,
            )

            # Parse JSON response
            response_text = response.get("content", "").strip()

            # Remove markdown code fences if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = (
                    "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
                )

            data = json.loads(response_text)

            # Build OfficialFeatureContract instances
            features = []
            for feat_data in data.get("features", []):
                if not feat_data.get("name"):
                    continue
                features.append(
                    OfficialFeatureContract(
                        name=feat_data["name"],
                        description=feat_data.get("description", ""),
                        source_url=source_url,  # Set from URL parameter
                    )
                )

            terminology = data.get("official_terminology", {})

            logger.info(f"Extracted {len(features)} features from {source_url}")
            return features, terminology

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response from GPT-4o mini: {e}")
            return [], {}
        except Exception as e:
            logger.warning(f"Failed to extract features via GPT-4o mini: {e}")
            return [], {}

    @staticmethod
    def _deduplicate_features(
        features: List[OfficialFeatureContract],
    ) -> List[OfficialFeatureContract]:
        """Deduplicate features by name (case-insensitive)."""
        seen_names = set()
        deduped = []

        for feature in features:
            name_lower = feature.name.lower()
            if name_lower not in seen_names:
                seen_names.add(name_lower)
                deduped.append(feature)

        return deduped
