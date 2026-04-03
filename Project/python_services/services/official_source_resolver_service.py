"""
Official Source Resolver Service (Phase 2a - V3.1)

Resolves homepage URL to feature/docs page URLs using Jina Reader.
"""

import logging
from typing import List
import httpx

logger = logging.getLogger(__name__)


class OfficialSourceResolverService:
    """
    Resolves reference URL to feature/docs URLs.

    Input:  reference_url (homepage)
    Output: verified_feature_urls (max 3)
    """

    JINA_READER_BASE = "https://r.jina.ai/"
    TIMEOUT_SEC = 10
    MAX_FEATURE_URLS = 3

    # Patterns for feature/docs pages
    FEATURE_PATTERNS = [
        "/features",
        "/how-it-works",
        "/docs",
        "/documentation",
        "/creators",
        "/rewards",
        "/earn",
        "/explore",
        "/pricing",
        "/product",
    ]

    @classmethod
    async def resolve_feature_urls(cls, reference_url: str) -> List[str]:
        """
        Crawl homepage to find feature/docs URLs.

        Returns:
            List of up to 3 verified feature URLs.
            Falls back to [reference_url] if crawl fails or no links found.
        """
        if not reference_url or not reference_url.startswith("http"):
            logger.warning(
                f"Invalid reference_url: {reference_url}, returning empty list"
            )
            return []

        try:
            jina_url = f"{cls.JINA_READER_BASE}{reference_url}"

            async with httpx.AsyncClient(timeout=cls.TIMEOUT_SEC) as client:
                logger.info(f"Fetching {jina_url} via Jina Reader")
                response = await client.get(jina_url)
                response.raise_for_status()
                markdown_content = response.text

            # Parse markdown for internal links
            feature_urls = cls._extract_feature_urls(markdown_content, reference_url)

            if not feature_urls:
                logger.warning(
                    f"No feature URLs found in {reference_url}, using homepage as fallback"
                )
                return [reference_url]

            # Return top 3 most relevant
            return feature_urls[: cls.MAX_FEATURE_URLS]

        except httpx.TimeoutException:
            logger.warning(
                f"Jina Reader timeout for {reference_url}, using homepage as fallback"
            )
            return [reference_url]
        except Exception as e:
            logger.warning(
                f"Failed to resolve feature URLs from {reference_url}: {e}, using homepage as fallback"
            )
            return [reference_url]

    @classmethod
    def _extract_feature_urls(cls, markdown: str, base_url: str) -> List[str]:
        """
        Extract feature/docs URLs from markdown content.

        Returns:
            List of absolute URLs matching feature patterns.
        """
        from urllib.parse import urljoin
        import re

        urls = []
        base_domain = cls._extract_domain(base_url)

        # Find all markdown links: [text](url)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        matches = re.findall(link_pattern, markdown)

        for text, url in matches:
            # Skip external links, anchors, mailto, tel
            if url.startswith(("#", "mailto:", "tel:")):
                continue

            # Convert relative to absolute
            absolute_url = urljoin(base_url, url)

            # Only keep links from same domain
            if cls._extract_domain(absolute_url) != base_domain:
                continue

            # Check if URL matches feature patterns
            url_lower = absolute_url.lower()
            if any(pattern in url_lower for pattern in cls.FEATURE_PATTERNS):
                if absolute_url not in urls:  # Deduplicate
                    urls.append(absolute_url)

        logger.info(f"Extracted {len(urls)} feature URLs from {base_url}")
        return urls

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc.lower()
