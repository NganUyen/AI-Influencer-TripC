from pathlib import Path

import pytest
from temporalio.exceptions import ApplicationError

from activities import video_activities


@pytest.mark.asyncio
async def test_build_split_screen_video_uses_local_bgm_and_preserves_vertical_output(monkeypatch):
    async def fake_download_required(url: str, dest: str, label: str) -> None:
        Path(dest).write_bytes(b"0" * 4000)

    async def fake_download_optional(url: str, dest: str, label: str):
        return None

    def fake_run_ffmpeg(cmd, label, cwd=None):
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"1" * 20000)

    def fake_probe_duration(path: str):
        return 12.0

    def fake_audio_signal(path: str):
        return True

    class _FakeMediaStorage:
        async def upload_bytes(self, **kwargs):
            return {
                "access_url": "https://cdn.example/final.mp4",
                "storage_path": "videos/persona/final.mp4",
            }

    monkeypatch.setattr(video_activities, "_download_required", fake_download_required)
    monkeypatch.setattr(video_activities, "_download_optional", fake_download_optional)
    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr(video_activities, "_probe_media_duration", fake_probe_duration)
    monkeypatch.setattr(video_activities, "_audio_has_audible_signal", fake_audio_signal)
    monkeypatch.setattr(video_activities, "MediaStorageService", _FakeMediaStorage)

    result = await video_activities.build_split_screen_video(
        {
            "image_urls": ["https://cdn.example/scene-1.mp4"],
            "audio_url": None,
            "talking_head_url": None,
            "subtitle_script": "",
            "subtitle_segments": [],
            "scene_durations": [4.0],
            "is_video_flags": [True],
            "persona_id": "persona-1",
            "topic": "manual mobile demo",
            "duration_per_image": 4.0,
            "audio_policy": {
                "bgm_fallback_enabled": True,
                "bgm_library_profile": "product_explainer",
                "max_bgm_duration_seconds": 60,
            },
            "owner_key": "telegram:555",
        }
    )

    assert result["resolution"] == "1080x1920"
    assert result["metadata"]["used_bgm_fallback"] is True
    assert result["metadata"]["used_talking_head"] is False
    assert result["metadata"]["bgm_profile"] == "product_explainer"


@pytest.mark.asyncio
async def test_build_split_screen_video_falls_back_when_subtitle_burn_fails(monkeypatch):
    async def fake_download_required(url: str, dest: str, label: str) -> None:
        Path(dest).write_bytes(b"0" * 4000)

    async def fake_download_optional(url: str, dest: str, label: str):
        return None

    def fake_run_ffmpeg(cmd, label, cwd=None):
        if label == "burn_subtitles":
            raise video_activities.AssemblyError(
                "ffmpeg failed (burn_subtitles) [code=1]: libass font error"
            )
        Path(cmd[-1]).write_bytes(b"1" * 20000)

    def fake_probe_duration(path: str):
        return 12.0

    def fake_audio_signal(path: str):
        return True

    class _FakeMediaStorage:
        async def upload_bytes(self, **kwargs):
            return {
                "access_url": "https://cdn.example/final.mp4",
                "storage_path": "videos/persona/final.mp4",
            }

    monkeypatch.setattr(video_activities, "_download_required", fake_download_required)
    monkeypatch.setattr(video_activities, "_download_optional", fake_download_optional)
    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr(video_activities, "_probe_media_duration", fake_probe_duration)
    monkeypatch.setattr(video_activities, "_audio_has_audible_signal", fake_audio_signal)
    monkeypatch.setattr(video_activities, "MediaStorageService", _FakeMediaStorage)

    result = await video_activities.build_split_screen_video(
        {
            "image_urls": ["https://cdn.example/scene-1.mp4"],
            "audio_url": None,
            "talking_head_url": None,
            "subtitle_script": "Hello world from TripC demo",
            "subtitle_segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello world from TripC demo"}
            ],
            "scene_durations": [4.0],
            "is_video_flags": [True],
            "persona_id": "persona-1",
            "topic": "manual mobile demo",
            "duration_per_image": 4.0,
            "audio_policy": {
                "bgm_fallback_enabled": True,
                "bgm_library_profile": "product_explainer",
                "max_bgm_duration_seconds": 60,
            },
            "owner_key": "telegram:555",
        }
    )

    assert result["video_url"] == "https://cdn.example/final.mp4"
    assert result["metadata"]["subtitle_status"] == "fallback_without_subtitles"
    assert "burn_subtitles" in result["metadata"]["subtitle_error"]


@pytest.mark.asyncio
async def test_build_split_screen_video_raises_typed_application_error_for_assembly_failures(monkeypatch):
    async def fake_download_required(url: str, dest: str, label: str) -> None:
        Path(dest).write_bytes(b"0" * 4000)

    async def fake_download_optional(url: str, dest: str, label: str):
        return None

    def fake_run_ffmpeg(cmd, label, cwd=None):
        raise video_activities.AssemblyError(
            "ffmpeg failed (split_screen_assembly) [code=1]: invalid filter graph"
        )

    def fake_probe_duration(path: str):
        return 12.0

    def fake_audio_signal(path: str):
        return True

    monkeypatch.setattr(video_activities, "_download_required", fake_download_required)
    monkeypatch.setattr(video_activities, "_download_optional", fake_download_optional)
    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr(video_activities, "_probe_media_duration", fake_probe_duration)
    monkeypatch.setattr(video_activities, "_audio_has_audible_signal", fake_audio_signal)

    with pytest.raises(ApplicationError) as exc_info:
        await video_activities.build_split_screen_video(
            {
                "image_urls": ["https://cdn.example/scene-1.mp4"],
                "audio_url": None,
                "talking_head_url": None,
                "subtitle_script": "",
                "subtitle_segments": [],
                "scene_durations": [4.0],
                "is_video_flags": [True],
                "persona_id": "persona-1",
                "topic": "manual mobile demo",
                "duration_per_image": 4.0,
                "audio_policy": {
                    "bgm_fallback_enabled": True,
                    "bgm_library_profile": "product_explainer",
                    "max_bgm_duration_seconds": 60,
                },
                "owner_key": "telegram:555",
            }
        )

    assert exc_info.value.type == "AssemblyError"
    assert exc_info.value.non_retryable is True
    assert "split_screen_assembly" in str(exc_info.value)
