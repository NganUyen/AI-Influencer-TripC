"""
AI Service
Wrapper for OpenAI/Anthropic API calls
"""

import logging
from typing import Dict, Any, List
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config.settings import settings

logger = logging.getLogger(__name__)


class AIService:
    """
    Unified service for AI model interactions
    Supports OpenAI (GPT-4) and Anthropic (Claude)
    """

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.default_model = settings.DEFAULT_AI_MODEL

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

        try:
            if model.startswith("gpt"):
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                return response.choices[0].message.content

            elif model.startswith("claude"):
                response = await self.anthropic_client.messages.create(
                    model=model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                return response.content[0].text

        except Exception as e:
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
