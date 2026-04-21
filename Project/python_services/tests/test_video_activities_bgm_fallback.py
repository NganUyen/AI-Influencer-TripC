from pathlib import Path

import pytest
from temporalio.exceptions import ApplicationError

from activities import video_activities


def test_mix_audio_tracks_loops_overlay_only(monkeypatch):
    captured = {}

    def fake_run_ffmpeg(cmd, label, cwd=None):
        captured["cmd"] = cmd
        captured["label"] = label

    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)

    video_activities._mix_audio_tracks(
        base_audio_path="base.mp3",
        overlay_audio_path="overlay.mp3",
        output_audio_path="mixed.mp3",
        overlay_volume=0.2,
    )

    cmd = captured["cmd"]
    assert captured["label"] == "mix_movement_overlay"
    assert cmd.count("-stream_loop") == 1
    assert cmd[cmd.index("-stream_loop") + 1] == "-1"
    assert cmd[cmd.index("-stream_loop") + 2] == "-i"
    assert cmd[cmd.index("-stream_loop") + 3] == "overlay.mp3"
    assert "-i" in cmd
    assert "base.mp3" in cmd
    assert cmd[-1] == "mixed.mp3"


def test_prepare_overlay_segment_uses_offset_when_configured(monkeypatch, tmp_path):
    source = tmp_path / "movement_source.mp3"
    source.write_bytes(b"a" * 5000)
    out = tmp_path / "movement_segment.mp3"
    captured = {}

    def fake_run_ffmpeg(cmd, label, cwd=None):
        captured["cmd"] = cmd
        captured["label"] = label
        out.write_bytes(b"b" * 4000)

    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)

    prepared_path = video_activities._prepare_overlay_segment(
        source_path=str(source),
        output_path=str(out),
        start_offset_seconds=6.4,
        clip_duration_seconds=9.0,
    )

    assert captured["label"] == "prepare_overlay_segment"
    assert "-ss" in captured["cmd"]
    assert "-t" in captured["cmd"]
    assert prepared_path == str(out)


def test_mix_video_audio_with_bgm_loops_overlay_and_preserves_video(monkeypatch):
    captured = {}

    def fake_run_ffmpeg(cmd, label, cwd=None):
        captured["cmd"] = cmd
        captured["label"] = label

    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)

    video_activities._mix_video_audio_with_bgm(
        input_video_path="combined.mp4",
        bgm_audio_path="motivation.mp3",
        output_video_path="final_with_bgm.mp4",
        bgm_volume=0.22,
    )

    cmd = captured["cmd"]
    assert captured["label"] == "mix_bgm_after_combine"
    assert cmd.count("-stream_loop") == 1
    assert cmd[cmd.index("-stream_loop") + 1] == "-1"
    assert cmd[cmd.index("-stream_loop") + 3] == "motivation.mp3"
    assert cmd[cmd.index("-map") + 1] == "0:v"
    assert "-c:v" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert cmd[-1] == "final_with_bgm.mp4"


@pytest.mark.asyncio
async def test_materialize_track_audio_downloads_from_access_url(monkeypatch, tmp_path):
    captured = {}
    dest = tmp_path / "track.mp3"

    async def fake_download_required(url: str, out: str, label: str) -> None:
        captured["url"] = url
        captured["dest"] = out
        captured["label"] = label
        Path(out).write_bytes(b"a" * 5000)

    monkeypatch.setattr(video_activities, "_download_required", fake_download_required)

    ok = await video_activities._materialize_track_audio(
        track={
            "group": "bgm",
            "profile": "product_explainer",
            "access_url": "https://cdn.example/audio-library/bgm.mp3",
        },
        dest_path=str(dest),
        label="bgm_fallback",
    )

    assert ok is True
    assert captured["url"] == "https://cdn.example/audio-library/bgm.mp3"
    assert captured["label"] == "bgm_fallback"
    assert dest.exists()
    assert dest.stat().st_size >= 5000


@pytest.mark.asyncio
async def test_build_split_screen_video_uses_bgm_fallback_and_preserves_vertical_output(monkeypatch):
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
    monkeypatch.setattr(video_activities, "_validate_video_stream", lambda path, label: True)
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
async def test_build_split_screen_video_applies_post_combine_bgm_when_voiceover_present(
    monkeypatch, tmp_path
):
    ffmpeg_labels = []
    bgm_overlay_source = tmp_path / "motivational.mp3"
    bgm_overlay_source.write_bytes(b"m" * 5000)

    async def fake_download_required(url: str, dest: str, label: str) -> None:
        Path(dest).write_bytes(b"0" * 4000)

    async def fake_download_optional(url: str, dest: str, label: str):
        return None

    def fake_run_ffmpeg(cmd, label, cwd=None):
        ffmpeg_labels.append(label)
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"1" * 20000)

    def fake_probe_duration(path: str):
        return 12.0

    def fake_audio_signal(path: str):
        return True

    class _FakeMediaStorage:
        async def upload_bytes(self, **kwargs):
            return {
                "access_url": "https://cdn.example/final-with-bgm.mp4",
                "storage_path": "videos/persona/final-with-bgm.mp4",
            }

    def fake_select_track(*args, **kwargs):
        return {
            "group": "bgm",
            "profile": "motivational_lift",
            "path": str(bgm_overlay_source),
            "duration_seconds": 55,
        }

    monkeypatch.setattr(video_activities, "_download_required", fake_download_required)
    monkeypatch.setattr(video_activities, "_download_optional", fake_download_optional)
    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr(video_activities, "_probe_media_duration", fake_probe_duration)
    monkeypatch.setattr(video_activities, "_audio_has_audible_signal", fake_audio_signal)
    monkeypatch.setattr(video_activities, "_validate_video_stream", lambda path, label: True)
    monkeypatch.setattr(video_activities, "MediaStorageService", _FakeMediaStorage)
    monkeypatch.setattr(
        video_activities.BackgroundMusicService,
        "select_track",
        fake_select_track,
    )

    result = await video_activities.build_split_screen_video(
        {
            "image_urls": ["https://cdn.example/scene-1.mp4"],
            "audio_url": "https://cdn.example/voiceover.mp3",
            "talking_head_url": None,
            "subtitle_script": "",
            "subtitle_segments": [],
            "scene_durations": [4.0],
            "is_video_flags": [True],
            "persona_id": "persona-1",
            "topic": "motivational plan",
            "duration_per_image": 4.0,
            "audio_policy": {
                "bgm_fallback_enabled": True,
                "bgm_library_profile": "motivational_lift",
                "bgm_duck_under_voiceover": True,
                "max_bgm_duration_seconds": 60,
            },
            "owner_key": "telegram:555",
        }
    )

    assert "mix_bgm_after_combine" in ffmpeg_labels
    assert result["metadata"]["used_bgm_fallback"] is False
    assert result["metadata"]["used_bgm_overlay_after_combine"] is True
    assert result["metadata"]["bgm_profile"] == "motivational_lift"


@pytest.mark.asyncio
async def test_build_split_screen_video_applies_movement_overlay_when_enabled(
    monkeypatch, tmp_path
):
    ffmpeg_labels = []
    movement_source = tmp_path / "movement-natural.mp3"
    movement_source.write_bytes(b"m" * 6000)

    async def fake_download_required(url: str, dest: str, label: str) -> None:
        Path(dest).write_bytes(b"0" * 4000)

    async def fake_download_optional(url: str, dest: str, label: str):
        return None

    def fake_run_ffmpeg(cmd, label, cwd=None):
        ffmpeg_labels.append(label)
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"1" * 20000)

    def fake_probe_duration(path: str):
        return 12.0

    def fake_audio_signal(path: str):
        return True

    class _FakeMediaStorage:
        async def upload_bytes(self, **kwargs):
            return {
                "access_url": "https://cdn.example/final-with-movement.mp4",
                "storage_path": "videos/persona/final-with-movement.mp4",
            }

    def fake_select_track(*, group="bgm", profile="product_explainer", max_duration_seconds=60):
        if group == "movement":
            return {
                "group": "movement",
                "profile": "natural",
                "path": str(movement_source),
                "duration_seconds": 26,
                "start_offset_seconds": 0.4,
                "clip_duration_seconds": 10.0,
            }
        return {
            "group": "bgm",
            "profile": profile,
            "path": str(movement_source),
            "duration_seconds": 26,
        }

    monkeypatch.setattr(video_activities, "_download_required", fake_download_required)
    monkeypatch.setattr(video_activities, "_download_optional", fake_download_optional)
    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr(video_activities, "_probe_media_duration", fake_probe_duration)
    monkeypatch.setattr(video_activities, "_audio_has_audible_signal", fake_audio_signal)
    monkeypatch.setattr(video_activities, "_validate_video_stream", lambda path, label: True)
    monkeypatch.setattr(video_activities, "MediaStorageService", _FakeMediaStorage)
    monkeypatch.setattr(
        video_activities.BackgroundMusicService,
        "select_track",
        fake_select_track,
    )

    result = await video_activities.build_split_screen_video(
        {
            "image_urls": ["https://cdn.example/scene-1.mp4"],
            "audio_url": "https://cdn.example/voiceover.mp3",
            "talking_head_url": None,
            "subtitle_script": "",
            "subtitle_segments": [],
            "scene_durations": [4.0],
            "is_video_flags": [True],
            "persona_id": "persona-1",
            "topic": "movement plan",
            "duration_per_image": 4.0,
            "audio_policy": {
                "bgm_fallback_enabled": False,
                "movement_overlay_enabled": True,
                "movement_library_profile": "natural",
                "movement_overlay_volume": 0.2,
                "max_bgm_duration_seconds": 60,
            },
            "owner_key": "telegram:555",
        }
    )

    assert "mix_movement_overlay" in ffmpeg_labels
    assert result["metadata"]["used_movement_overlay"] is True
    assert result["metadata"]["movement_profile"] == "natural"


@pytest.mark.asyncio
async def test_build_split_screen_video_can_apply_movement_and_post_combine_bgm_together(
    monkeypatch, tmp_path
):
    ffmpeg_labels = []

    async def fake_download_required(url: str, dest: str, label: str) -> None:
        Path(dest).write_bytes(b"0" * 4000)

    async def fake_download_optional(url: str, dest: str, label: str):
        return None

    def fake_run_ffmpeg(cmd, label, cwd=None):
        ffmpeg_labels.append(label)
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"1" * 20000)

    def fake_probe_duration(path: str):
        return 12.0

    def fake_audio_signal(path: str):
        return True

    class _FakeMediaStorage:
        async def upload_bytes(self, **kwargs):
            return {
                "access_url": "https://cdn.example/final-with-bgm-and-movement.mp4",
                "storage_path": "videos/persona/final-with-bgm-and-movement.mp4",
            }

    def fake_select_track(*, group="bgm", profile="product_explainer", max_duration_seconds=60):
        if group == "movement":
            return {
                "group": "movement",
                "profile": "natural",
                "access_url": "https://cdn.example/library/movement-natural.mp3",
                "duration_seconds": 26,
                "start_offset_seconds": 0.4,
                "clip_duration_seconds": 10.0,
            }
        return {
            "group": "bgm",
            "profile": "motivational_lift",
            "access_url": "https://cdn.example/library/bgm-motivational.mp3",
            "duration_seconds": 55,
        }

    monkeypatch.setattr(video_activities, "_download_required", fake_download_required)
    monkeypatch.setattr(video_activities, "_download_optional", fake_download_optional)
    monkeypatch.setattr(video_activities, "_run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr(video_activities, "_probe_media_duration", fake_probe_duration)
    monkeypatch.setattr(video_activities, "_audio_has_audible_signal", fake_audio_signal)
    monkeypatch.setattr(video_activities, "_validate_video_stream", lambda path, label: True)
    monkeypatch.setattr(video_activities, "MediaStorageService", _FakeMediaStorage)
    monkeypatch.setattr(
        video_activities.BackgroundMusicService,
        "select_track",
        fake_select_track,
    )

    result = await video_activities.build_split_screen_video(
        {
            "image_urls": ["https://cdn.example/scene-1.mp4"],
            "audio_url": "https://cdn.example/voiceover.mp3",
            "talking_head_url": None,
            "subtitle_script": "",
            "subtitle_segments": [],
            "scene_durations": [4.0],
            "is_video_flags": [True],
            "persona_id": "persona-1",
            "topic": "combo movement and bgm",
            "duration_per_image": 4.0,
            "audio_policy": {
                "bgm_fallback_enabled": True,
                "bgm_library_profile": "motivational_lift",
                "bgm_duck_under_voiceover": True,
                "movement_overlay_enabled": True,
                "movement_library_profile": "natural",
                "movement_overlay_volume": 0.2,
                "max_bgm_duration_seconds": 60,
            },
            "owner_key": "telegram:555",
        }
    )

    assert "mix_movement_overlay" in ffmpeg_labels
    assert "mix_bgm_after_combine" in ffmpeg_labels
    assert result["metadata"]["used_movement_overlay"] is True
    assert result["metadata"]["used_bgm_overlay_after_combine"] is True


@pytest.mark.asyncio
async def test_build_split_screen_video_fails_fast_when_top_half_video_stream_is_invalid(
    monkeypatch,
):
    async def fake_download_required(url: str, dest: str, label: str) -> None:
        Path(dest).write_bytes(b"0" * 5000)

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
    monkeypatch.setattr(
        video_activities,
        "_validate_video_stream",
        lambda path, label: False if "img_00" in path else True,
        raising=False,
    )

    with pytest.raises(ApplicationError, match="invalid video stream"):
        await video_activities.build_split_screen_video(
            {
                "image_urls": ["https://cdn.example/scene-1.mp4"],
                "audio_url": "https://cdn.example/voiceover.mp3",
                "talking_head_url": None,
                "subtitle_script": "",
                "subtitle_segments": [],
                "scene_durations": [4.0],
                "is_video_flags": [True],
                "persona_id": "persona-1",
                "topic": "invalid top half",
                "duration_per_image": 4.0,
                "owner_key": "telegram:555",
            }
        )


@pytest.mark.asyncio
async def test_build_split_screen_video_falls_back_when_talking_head_stream_is_invalid(
    monkeypatch,
):
    ffmpeg_labels = []

    async def fake_download_required(url: str, dest: str, label: str) -> None:
        Path(dest).write_bytes(b"0" * 5000)

    async def fake_download_optional(url: str, dest: str, label: str):
        Path(dest).write_bytes(b"2" * 5000)
        return dest

    def fake_run_ffmpeg(cmd, label, cwd=None):
        ffmpeg_labels.append(label)
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
    monkeypatch.setattr(
        video_activities,
        "_validate_video_stream",
        lambda path, label: False if "talking_head" in path else True,
        raising=False,
    )

    result = await video_activities.build_split_screen_video(
        {
            "image_urls": ["https://cdn.example/scene-1.mp4"],
            "audio_url": "https://cdn.example/voiceover.mp3",
            "talking_head_url": "https://cdn.example/talking-head.mp4",
            "subtitle_script": "",
            "subtitle_segments": [],
            "scene_durations": [4.0],
            "is_video_flags": [True],
            "persona_id": "persona-1",
            "topic": "invalid talking head",
            "duration_per_image": 4.0,
            "owner_key": "telegram:555",
        }
    )

    assert "normalize_talking_head" not in ffmpeg_labels
    assert "build_fallback_bottom_half" in ffmpeg_labels
    assert result["metadata"]["used_talking_head"] is False
