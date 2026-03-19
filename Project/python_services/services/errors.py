"""
Pipeline Error Types (TripC v2 Standard)
=========================================
Định nghĩa các lỗi rõ ràng để Temporal retry policy xử lý chính xác.
Non-retryable errors: Auth errors, invalid config, content rejection.
Retryable errors: Network timeouts, transient 5xx, polling timeouts.
"""


# ─── Base ─────────────────────────────────────────────────────────────────────

class PipelineError(Exception):
    """Base class for all pipeline errors."""
    retryable: bool = False


# ─── fal.ai ───────────────────────────────────────────────────────────────────

class FalAIServiceError(PipelineError):
    """Generic fal.ai error (retryable by default)."""
    retryable = True


class FalAIAuthError(FalAIServiceError):
    """Invalid API key or authentication failure. Non-retryable."""
    retryable = False


class FalAIRetryableError(FalAIServiceError):
    """Transient network or 5xx error. Retryable."""
    retryable = True


class FalAIContentRejectionError(FalAIServiceError):
    """Prompt rejected by content policy. Non-retryable."""
    retryable = False


# ─── Google TTS ───────────────────────────────────────────────────────────────

class TTSServiceError(PipelineError):
    """Generic TTS error."""
    retryable = True


class TTSAuthError(TTSServiceError):
    """Invalid TTS API key. Non-retryable."""
    retryable = False


class TTSVoiceConfigError(TTSServiceError):
    """Invalid voice configuration. Non-retryable."""
    retryable = False


# ─── HeyGen ───────────────────────────────────────────────────────────────────

class HeyGenServiceError(PipelineError):
    """Generic HeyGen error."""
    retryable = True


class HeyGenAuthError(HeyGenServiceError):
    """Invalid HeyGen API key. Non-retryable."""
    retryable = False


class HeyGenTimeoutError(HeyGenServiceError):
    """HeyGen polling timed out. Retryable (bounded)."""
    retryable = True


class HeyGenAvatarSetupError(HeyGenServiceError):
    """Failed to create or validate avatar. Non-retryable without operator input."""
    retryable = False


# ─── ffmpeg Assembly ──────────────────────────────────────────────────────────

class AssemblyError(PipelineError):
    """ffmpeg assembly failed."""
    retryable = False


class AssemblyMissingAssetError(AssemblyError):
    """One or more required media files are missing. Non-retryable until upstream provides them."""
    retryable = False


# ─── Persona ──────────────────────────────────────────────────────────────────

class PersonaConfigurationError(PipelineError):
    """Invalid or incomplete persona configuration. Non-retryable."""
    retryable = False


class PersonaNotReadyError(PipelineError):
    """Persona avatar_id or voice config is missing — not ready for video generation."""
    retryable = False


# ─── Storage ──────────────────────────────────────────────────────────────────

class StorageUploadError(PipelineError):
    """Failed to upload artifact to R2. Retryable for transient errors."""
    retryable = True


# ─── Script Generation ────────────────────────────────────────────────────────

class ScriptGenerationError(PipelineError):
    """AI failed to generate valid script JSON. May be retryable."""
    retryable = True


class ScriptContractError(PipelineError):
    """Generated script does not satisfy the required JSON contract. Non-retryable."""
    retryable = False
