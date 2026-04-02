"""
Capture module exceptions.
"""


class CaptureStorageError(Exception):
    """Base exception for capture storage operations."""
    pass


class StorageVerifyError(CaptureStorageError):
    """Video file verification failed."""
    pass


class StorageBucketError(CaptureStorageError):
    """Supabase bucket not found or inaccessible."""
    pass


class StorageUploadError(CaptureStorageError):
    """Failed to upload file to storage after retries."""
    pass


class CampaignNotFoundError(CaptureStorageError):
    """Campaign not found in database."""
    pass


class StorageInconsistencyError(CaptureStorageError):
    """Storage state inconsistency detected."""
    pass


class CaptureCompositorError(CaptureStorageError):
    """Image compositor failed while preparing top-half frame."""
    pass


class CapturePipelineError(CaptureStorageError):
    """Capture pipeline orchestration failed."""
    pass
