"""
AI Service
Wrapper for OpenAI/Anthropic API calls
"""

import logging
import asyncio
from typing import Dict, Any, List
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config.settings import settings
from services.quota_monitor_service import QuotaMonitorService

logger = logging.getLogger(__name__)

_shared_openai_client: AsyncOpenAI | None = None
_shared_anthropic_client: AsyncAnthropic | None = None


def _get_shared_openai() -> AsyncOpenAI:
    global _shared_openai_client
    if _shared_openai_client is None:
        _shared_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _shared_openai_client


def _get_shared_anthropic() -> AsyncAnthropic:
    global _shared_anthropic_client
    if _shared_anthropic_client is None:
        _shared_anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _shared_anthropic_client


def _usage_value(usage: Any, *keys: str) -> Any:
    if usage is None:
        return None
    for key in keys:
        if isinstance(usage, dict) and usage.get(key) is not None:
            return usage.get(key)
        value = getattr(usage, key, None)
        if value is not None:
            return value
    return None


def _estimate_text_tokens(*parts: str) -> int:
    total_chars = sum(len(str(part or "")) for part in parts)
    if total_chars <= 0:
        return 0
    return max(1, (total_chars + 3) // 4)


def _header_value(headers: Any, key: str) -> Any:
    if headers is None:
        return None
    if hasattr(headers, "get"):
        return headers.get(key)
    return None


def _header_int(headers: Any, key: str) -> int | None:
    value = _header_value(headers, key)
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _header_text(headers: Any, key: str) -> str | None:
    value = _header_value(headers, key)
    if value in (None, ""):
        return None
    return str(value).strip()


def _openai_quota_from_headers(headers: Any) -> Dict[str, Any]:
    quota: Dict[str, Any] = {
        "unit": "tokens",
        "exact": True,
        "source": "provider_response_headers",
    }
    limit = _header_int(headers, "x-ratelimit-limit-tokens")
    remaining = _header_int(headers, "x-ratelimit-remaining-tokens")
    reset_after = _header_text(headers, "x-ratelimit-reset-tokens")
    requests_limit = _header_int(headers, "x-ratelimit-limit-requests")
    requests_remaining = _header_int(headers, "x-ratelimit-remaining-requests")
    requests_reset_after = _header_text(headers, "x-ratelimit-reset-requests")

    if limit is not None:
        quota["limit"] = limit
    if remaining is not None:
        quota["remaining"] = remaining
    if reset_after:
        quota["reset_after"] = reset_after
    if requests_limit is not None:
        quota["requests_limit"] = requests_limit
    if requests_remaining is not None:
        quota["requests_remaining"] = requests_remaining
    if requests_reset_after:
        quota["requests_reset_after"] = requests_reset_after

    if (
        "limit" not in quota
        and "remaining" not in quota
        and "requests_limit" not in quota
    ):
        return {}
    return quota


def _anthropic_quota_from_headers(headers: Any) -> Dict[str, Any]:
    quota: Dict[str, Any] = {
        "unit": "tokens",
        "exact": True,
        "source": "provider_response_headers",
    }
    limit = _header_int(headers, "anthropic-ratelimit-tokens-limit")
    remaining = _header_int(headers, "anthropic-ratelimit-tokens-remaining")
    reset_at = _header_text(headers, "anthropic-ratelimit-tokens-reset")
    requests_limit = _header_int(headers, "anthropic-ratelimit-requests-limit")
    requests_remaining = _header_int(headers, "anthropic-ratelimit-requests-remaining")
    requests_reset_at = _header_text(headers, "anthropic-ratelimit-requests-reset")

    if limit is not None:
        quota["limit"] = limit
    if remaining is not None:
        quota["remaining"] = remaining
    if reset_at:
        quota["reset_at"] = reset_at
    if requests_limit is not None:
        quota["requests_limit"] = requests_limit
    if requests_remaining is not None:
        quota["requests_remaining"] = requests_remaining
    if requests_reset_at:
        quota["requests_reset_at"] = requests_reset_at

    if (
        "limit" not in quota
        and "remaining" not in quota
        and "requests_limit" not in quota
    ):
        return {}
    return quota


class AIService:
    """
    Unified service for AI model interactions
    Supports OpenAI (GPT-4) and Anthropic (Claude)
    """

    def __init__(self):
        self.openai_client = _get_shared_openai()
        self.anthropic_client = _get_shared_anthropic()

        self.default_model = settings.DEFAULT_AI_MODEL or "claude-3-5-sonnet-20241022"

    async def close(self) -> None:
        """Shared clients are managed globally, no-op here."""
        pass

    async def __aenter__(self) -> "AIService":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @staticmethod
    def _provider_for_model(model: str) -> str:
        if model.startswith("gpt"):
            return "openai"
        if model.startswith("claude"):
            return "anthropic"
        return "unknown"

    async def _record_quota_usage(
        self,
        provider: str,
        model: str,
        usage: Dict[str, Any] | None = None,
        quota: Dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        metadata: Dict[str, Any] = {
            "service": "ai_service",
            "operation": "generate_text",
            "model": model,
            "status": "error" if error else "success",
        }
        if error:
            metadata["error_type"] = type(error).__name__
            metadata["error_message"] = str(error)

        normalized_usage: Dict[str, Any] = {"requests": 1}
        if usage:
            normalized_usage.update(
                {key: value for key, value in usage.items() if value is not None}
            )

        await QuotaMonitorService.record_runtime_usage(
            provider=provider,
            usage=normalized_usage,
            quota=quota,
            metadata=metadata,
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Generate text using AI model

        Args:
            prompt: User prompt
            system_prompt: System prompt
            model: Model to use (gpt-4, claude-3.5-sonnet, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        model = model or self.default_model
        logger.info(f"Generating text with {model}")
        provider = self._provider_for_model(model)
        estimated_input_tokens = _estimate_text_tokens(system_prompt, prompt)
        await QuotaMonitorService.assert_within_budget(
            provider=provider,
            estimated_usage={
                "requests": 1,
                "tokens": estimated_input_tokens + max_tokens,
                "input_tokens": estimated_input_tokens,
                "output_tokens": max_tokens,
            },
            operation=f"generate_text:{model}",
        )

        try:
            if model.startswith("gpt"):
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                raw_response = (
                    await self.openai_client.chat.completions.with_raw_response.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                )
                response = raw_response.parse()
                usage = getattr(response, "usage", None)
                await self._record_quota_usage(
                    provider=provider,
                    model=model,
                    usage={
                        "tokens": _usage_value(usage, "total_tokens"),
                        "input_tokens": _usage_value(usage, "prompt_tokens"),
                        "output_tokens": _usage_value(usage, "completion_tokens"),
                    },
                    quota=_openai_quota_from_headers(
                        getattr(raw_response, "headers", None)
                    ),
                )

                return response.choices[0].message.content

            elif model.startswith("claude"):
                raw_response = (
                    await self.anthropic_client.messages.with_raw_response.create(
                        model=model,
                        system=system_prompt,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                )
                response = raw_response.parse()
                usage = getattr(response, "usage", None)
                input_tokens = _usage_value(usage, "input_tokens")
                output_tokens = _usage_value(usage, "output_tokens")
                total_tokens = None
                if input_tokens is not None or output_tokens is not None:
                    total_tokens = (input_tokens or 0) + (output_tokens or 0)
                await self._record_quota_usage(
                    provider=provider,
                    model=model,
                    usage={
                        "tokens": total_tokens,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    quota=_anthropic_quota_from_headers(
                        getattr(raw_response, "headers", None)
                    ),
                )

                return response.content[0].text

            else:
                raise ValueError(f"Unsupported model: {model}. Use gpt-* or claude-*")

        except Exception as e:
            await self._record_quota_usage(provider=provider, model=model, error=e)
            logger.error(f"Text generation failed: {str(e)}")
            raise

    async def generate_visual_prompt(
        self, content_description: str, style: str, platform: str
    ) -> str:
        """
        Generate optimized prompt for image/video generation
        """
        system_prompt = """You are an expert at creating prompts for AI image and video generation.
        Create detailed, vivid prompts that will produce high-quality visuals optimized for social media."""

        user_prompt = f"""
        Create an image generation prompt for:
        
        Content: {content_description}
        Visual Style: {style}
        Platform: {platform}
        
        The prompt should be detailed, specific, and optimized for modern AI image models.
        Include details about composition, lighting, colors, and mood.
        Keep it under 200 words.
        """

        return await self.generate_text(
            prompt=user_prompt, system_prompt=system_prompt, temperature=0.8
        )

    async def generate_audio_script(self, content: str, voice_persona: str) -> str:
        """
        Generate script optimized for text-to-speech
        """
        system_prompt = f"""You are a scriptwriter creating content for {voice_persona} voice synthesis.
        Optimize the text for natural speech patterns, including appropriate pauses and intonation guidance."""

        user_prompt = f"""
        Convert this content into a natural-sounding speech script:
        
        {content}
        
        Ensure it sounds conversational and engaging when spoken aloud.
        """

        return await self.generate_text(
            prompt=user_prompt, system_prompt=system_prompt, temperature=0.7
        )

    async def generate_platform_copy(
        self, theme: str, platforms: List[str], brand_voice: str
    ) -> Dict[str, str]:
        """
        Generate platform-specific copy variations
        """
        copies = {}

        for platform in platforms:
            system_prompt = f"""You are a {brand_voice} social media copywriter.
            Create engaging content optimized for {platform}'s audience and format."""

            user_prompt = f"""
            Create a post about: {theme}
            
            Platform: {platform}
            Format requirements:
            - Twitter: 280 characters max, hashtag-friendly
            - LinkedIn: Professional, longer-form (500-1000 chars)
            - Instagram: Visual-first, emoji-friendly, hashtags at end
            - TikTok: Short, punchy, trend-aware
            - Facebook: Conversational, question-ending
            """

            copy = await self.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=500,
            )

            copies[f"{platform}_copy"] = copy

        return copies

    async def analyze_image_structured(
        self,
        image_base64: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        """
        Analyze image using GPT-4o mini vision model (Phase 3a - V3.1).

        Args:
            image_base64: Base64-encoded image data
            system_prompt: System instructions
            user_prompt: User query/task

        Returns:
            Parsed dict from JSON response

        Raises:
            ValueError: If response cannot be parsed as JSON
        """
        model = "gpt-4o-mini"
        logger.info(f"Analyzing image with {model} vision")
        estimated_input_tokens = _estimate_text_tokens(system_prompt, user_prompt) + 1024
        await QuotaMonitorService.assert_within_budget(
            provider="openai",
            estimated_usage={
                "requests": 1,
                "tokens": estimated_input_tokens + 1000,
                "input_tokens": estimated_input_tokens,
                "output_tokens": 1000,
            },
            operation=f"analyze_image_structured:{model}",
        )

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                },
            ]

            raw_response = (
                await self.openai_client.chat.completions.with_raw_response.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1000,
                )
            )
            response = raw_response.parse()
            usage = getattr(response, "usage", None)

            await self._record_quota_usage(
                provider="openai",
                model=model,
                usage={
                    "tokens": _usage_value(usage, "total_tokens"),
                    "input_tokens": _usage_value(usage, "prompt_tokens"),
                    "output_tokens": _usage_value(usage, "completion_tokens"),
                },
                quota=_openai_quota_from_headers(
                    getattr(raw_response, "headers", None)
                ),
            )

            content = response.choices[0].message.content

            # Remove markdown code fences if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content

            # Parse JSON
            import json

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from vision response: {content}")
                raise ValueError(f"Vision model returned invalid JSON: {e}")

        except Exception as e:
            await self._record_quota_usage(
                provider="openai",
                model=model,
                error=e,
            )
            raise

    async def chat_completion(
        self,
        model: str,
        system_message: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict:
        """
        Chat completion using AI model (Phase 4a - V3.1).

        Args:
            model: Model to use (gpt-4o-mini, etc.)
            system_message: System prompt
            user_message: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            dict with "content" key containing the response text
        """
        model = model or self.default_model
        logger.info(f"Chat completion with {model}")
        provider = self._provider_for_model(model)
        estimated_input_tokens = _estimate_text_tokens(system_message, user_message)
        await QuotaMonitorService.assert_within_budget(
            provider=provider,
            estimated_usage={
                "requests": 1,
                "tokens": estimated_input_tokens + max_tokens,
                "input_tokens": estimated_input_tokens,
                "output_tokens": max_tokens,
            },
            operation=f"chat_completion:{model}",
        )

        try:
            if model.startswith("gpt"):
                messages = []
                if system_message:
                    messages.append({"role": "system", "content": system_message})
                messages.append({"role": "user", "content": user_message})

                raw_response = (
                    await self.openai_client.chat.completions.with_raw_response.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                )
                response = raw_response.parse()
                usage = getattr(response, "usage", None)
                await self._record_quota_usage(
                    provider=provider,
                    model=model,
                    usage={
                        "tokens": _usage_value(usage, "total_tokens"),
                        "input_tokens": _usage_value(usage, "prompt_tokens"),
                        "output_tokens": _usage_value(usage, "completion_tokens"),
                    },
                    quota=_openai_quota_from_headers(
                        getattr(raw_response, "headers", None)
                    ),
                )

                return {"content": response.choices[0].message.content}

            elif model.startswith("claude"):
                raw_response = (
                    await self.anthropic_client.messages.with_raw_response.create(
                        model=model,
                        system=system_message,
                        messages=[{"role": "user", "content": user_message}],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                )
                response = raw_response.parse()
                usage = getattr(response, "usage", None)
                input_tokens = _usage_value(usage, "input_tokens")
                output_tokens = _usage_value(usage, "output_tokens")
                total_tokens = None
                if input_tokens is not None or output_tokens is not None:
                    total_tokens = (input_tokens or 0) + (output_tokens or 0)
                await self._record_quota_usage(
                    provider=provider,
                    model=model,
                    usage={
                        "tokens": total_tokens,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    quota=_anthropic_quota_from_headers(
                        getattr(raw_response, "headers", None)
                    ),
                )

                return {"content": response.content[0].text}

            else:
                raise ValueError(f"Unsupported model: {model}. Use gpt-* or claude-*")

        except Exception as e:
            await self._record_quota_usage(provider=provider, model=model, error=e)
            logger.error(f"Chat completion failed: {str(e)}")
            raise
