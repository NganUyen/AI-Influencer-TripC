import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from activities.capture.capture_models import CaptureTarget, SceneCaptureSpec
from activities.capture.exceptions import (
    CaptureStorageError,
    StorageBucketError,
    StorageUploadError,
    StorageVerifyError,
)
from activities.capture.storage import (
    _upload_to_supabase_storage,
    _verify_video_file,
    persist_capture_result_activity,
    save_capture_result_activity,
)


@pytest.fixture
def scenes():
    """Return three valid scenes for cumulative timing checks."""
    target = CaptureTarget(type="mobile")
    return [
        SceneCaptureSpec(scene_index=0, script_text="A", capture_target=target, duration_seconds=3.0),
        SceneCaptureSpec(scene_index=1, script_text="B", capture_target=target, duration_seconds=2.5),
        SceneCaptureSpec(scene_index=2, script_text="C", capture_target=target, duration_seconds=4.0),
    ]


class TestVerifyVideoFile:
    @pytest.mark.asyncio
    async def test_empty_file_raises_verify_error(self, tmp_path):
        """0-byte file should raise StorageVerifyError."""
        video = tmp_path / "empty.mp4"
        video.write_bytes(b"")
        with pytest.raises(StorageVerifyError, match="empty"):
            await _verify_video_file(str(video))

    @pytest.mark.asyncio
    async def test_nonexistent_file_raises_verify_error(self):
        """Missing file should raise StorageVerifyError."""
        with pytest.raises(StorageVerifyError, match="not found"):
            await _verify_video_file("D:/not-found/video.mp4")

    @pytest.mark.asyncio
    async def test_wrong_resolution_raises_verify_error(self, tmp_path):
        """Non-1080x960 video should fail resolution verification."""
        video = tmp_path / "wrong-size.mp4"
        video.write_bytes(b"x")
        payload = {"streams": [{"width": 1920, "height": 1080}], "format": {"duration": "7.0"}}
        completed = SimpleNamespace(stdout=json.dumps(payload))
        with patch("activities.capture.storage.subprocess.run", return_value=completed):
            with pytest.raises(StorageVerifyError, match="Invalid resolution"):
                await _verify_video_file(str(video))

    @pytest.mark.asyncio
    async def test_zero_duration_raises_verify_error(self, tmp_path):
        """Zero duration video should raise StorageVerifyError."""
        video = tmp_path / "zero-duration.mp4"
        video.write_bytes(b"x")
        payload = {"streams": [{"width": 1080, "height": 960}], "format": {"duration": "0"}}
        completed = SimpleNamespace(stdout=json.dumps(payload))
        with patch("activities.capture.storage.subprocess.run", return_value=completed):
            with pytest.raises(StorageVerifyError, match="duration"):
                await _verify_video_file(str(video))

    @pytest.mark.asyncio
    async def test_valid_file_returns_metadata(self, tmp_path):
        """Valid 1080x960 file should return parsed metadata."""
        video = tmp_path / "ok.mp4"
        video.write_bytes(b"x")
        payload = {"streams": [{"width": 1080, "height": 960}], "format": {"duration": "7.0"}}
        completed = SimpleNamespace(stdout=json.dumps(payload))
        with patch("activities.capture.storage.subprocess.run", return_value=completed):
            meta = await _verify_video_file(str(video))
        assert meta == {"width": 1080, "height": 960, "duration": 7.0}


class TestUploadToSupabaseStorage:
    @pytest.mark.asyncio
    async def test_raises_bucket_error_when_bucket_missing(self, tmp_path):
        """Missing bucket object should raise StorageBucketError."""
        file_path = tmp_path / "video.mp4"
        file_path.write_bytes(b"x")
        supabase = MagicMock()
        supabase.storage.from_.return_value = None
        with pytest.raises(StorageBucketError):
            await _upload_to_supabase_storage(
                supabase_client=supabase,
                bucket_name="videos",
                local_file_path=str(file_path),
                campaign_id="camp-123",
            )

    @pytest.mark.asyncio
    async def test_storage_path_includes_campaign_id(self, tmp_path):
        """Storage path should include captures/{campaign_id}/ prefix."""
        file_path = tmp_path / "video.mp4"
        file_path.write_bytes(b"x")
        bucket = MagicMock()
        bucket.get_public_url.return_value = "https://cdn.example/video.mp4"
        supabase = MagicMock()
        supabase.storage.from_.return_value = bucket
        out = await _upload_to_supabase_storage(
            supabase_client=supabase,
            bucket_name="videos",
            local_file_path=str(file_path),
            campaign_id="camp-123",
            head_check=lambda _: True,
        )
        assert "captures/camp-123/" in out["storage_path"]

    @pytest.mark.asyncio
    async def test_raises_upload_error_after_3_failed_head_checks(self, tmp_path):
        """Three failed HEAD checks should raise StorageUploadError."""
        file_path = tmp_path / "video.mp4"
        file_path.write_bytes(b"x")
        bucket = MagicMock()
        bucket.get_public_url.return_value = "https://cdn.example/video.mp4"
        supabase = MagicMock()
        supabase.storage.from_.return_value = bucket
        with pytest.raises(StorageUploadError):
            await _upload_to_supabase_storage(
                supabase_client=supabase,
                bucket_name="videos",
                local_file_path=str(file_path),
                campaign_id="camp-123",
                head_check=lambda _: False,
            )


class TestSaveCaptureResultActivity:
    @pytest.mark.asyncio
    async def test_marks_running_status_at_start(self, scenes):
        """First DB update should set capture_status=running."""
        db = MagicMock()
        response = SimpleNamespace(data=[{"id": "camp-1"}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = response
        with patch("activities.capture.storage._verify_video_file", new=AsyncMock(return_value={})):
            with patch("activities.capture.storage._upload_to_supabase_storage", new=AsyncMock(return_value={"storage_path": "p", "storage_url": "u"})):
                await save_capture_result_activity(
                    campaign_id="camp-1",
                    scenes=scenes,
                    output_video_path="out.mp4",
                    db_client=db,
                    supabase_client=MagicMock(),
                )
        first_payload = db.table.return_value.update.call_args_list[0].args[0]
        assert first_payload["capture_status"] == "running"

    @pytest.mark.asyncio
    async def test_marks_failed_when_verify_fails(self, scenes):
        """Verify failure should force failed status and raise CaptureStorageError."""
        db = MagicMock()
        response = SimpleNamespace(data=[{"id": "camp-1"}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = response
        with patch(
            "activities.capture.storage._verify_video_file",
            new=AsyncMock(side_effect=StorageVerifyError("bad video")),
        ):
            with pytest.raises(CaptureStorageError):
                await save_capture_result_activity(
                    campaign_id="camp-1",
                    scenes=scenes,
                    output_video_path="out.mp4",
                    db_client=db,
                    supabase_client=MagicMock(),
                )
        payloads = [c.args[0] for c in db.table.return_value.update.call_args_list]
        assert payloads[0]["capture_status"] == "running"
        assert payloads[-1]["capture_status"] == "failed"

    @pytest.mark.asyncio
    async def test_never_stores_path_before_verify(self, scenes):
        """top_half_video_path should not be written before verification."""
        db = MagicMock()
        response = SimpleNamespace(data=[{"id": "camp-1"}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = response
        verify = AsyncMock(return_value={})
        upload = AsyncMock(return_value={"storage_path": "p", "storage_url": "u"})
        with patch("activities.capture.storage._verify_video_file", new=verify):
            with patch("activities.capture.storage._upload_to_supabase_storage", new=upload):
                await save_capture_result_activity(
                    campaign_id="camp-1",
                    scenes=scenes,
                    output_video_path="out.mp4",
                    db_client=db,
                    supabase_client=MagicMock(),
                )
        payloads = [c.args[0] for c in db.table.return_value.update.call_args_list]
        assert all("top_half_video_path" not in p for p in payloads[:2])
        assert any(p.get("top_half_video_path") == "out.mp4" for p in payloads)

    @pytest.mark.asyncio
    async def test_subtitle_timing_cumulative(self, scenes):
        """Subtitle timings stored in DB should be cumulative."""
        db = MagicMock()
        response = SimpleNamespace(data=[{"id": "camp-1"}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = response
        with patch("activities.capture.storage._verify_video_file", new=AsyncMock(return_value={})):
            with patch("activities.capture.storage._upload_to_supabase_storage", new=AsyncMock(return_value={"storage_path": "p", "storage_url": "u"})):
                await save_capture_result_activity(
                    campaign_id="camp-1",
                    scenes=scenes,
                    output_video_path="out.mp4",
                    db_client=db,
                    supabase_client=MagicMock(),
                )
        final_payload = db.table.return_value.update.call_args_list[-1].args[0]
        subs = final_payload["subtitle_data"]
        assert subs[0]["start_sec"] == 0.0 and subs[0]["end_sec"] == 3.0
        assert subs[1]["start_sec"] == 3.0 and subs[1]["end_sec"] == 5.5
        assert subs[2]["start_sec"] == 5.5 and subs[2]["end_sec"] == 9.5

    @pytest.mark.asyncio
    async def test_upload_skipped_when_flag_false(self, scenes):
        """upload_to_storage=False should skip upload and keep URL None."""
        db = MagicMock()
        response = SimpleNamespace(data=[{"id": "camp-1"}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = response
        upload = AsyncMock(return_value={"storage_path": "p", "storage_url": "u"})
        with patch("activities.capture.storage._verify_video_file", new=AsyncMock(return_value={})):
            with patch("activities.capture.storage._upload_to_supabase_storage", new=upload):
                await save_capture_result_activity(
                    campaign_id="camp-1",
                    scenes=scenes,
                    output_video_path="out.mp4",
                    db_client=db,
                    supabase_client=MagicMock(),
                    upload_to_storage=False,
                )
        assert upload.await_count == 0
        final_payload = db.table.return_value.update.call_args_list[-1].args[0]
        assert final_payload["top_half_storage_url"] is None

    @pytest.mark.asyncio
    async def test_db_never_left_in_running_state_on_error(self, scenes):
        """Any exception should end with capture_status=failed."""
        db = MagicMock()
        response = SimpleNamespace(data=[{"id": "camp-1"}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = response
        with patch(
            "activities.capture.storage._upload_to_supabase_storage",
            new=AsyncMock(side_effect=StorageUploadError("upload failed")),
        ):
            with patch("activities.capture.storage._verify_video_file", new=AsyncMock(return_value={})):
                with pytest.raises(CaptureStorageError):
                    await save_capture_result_activity(
                        campaign_id="camp-1",
                        scenes=scenes,
                        output_video_path="out.mp4",
                        db_client=db,
                        supabase_client=MagicMock(),
                    )
        payloads = [c.args[0] for c in db.table.return_value.update.call_args_list]
        assert payloads[0]["capture_status"] == "running"
        assert payloads[-1]["capture_status"] == "failed"


class _FakeConn:
    def __init__(self):
        self.calls = []

    async def execute(self, sql, *args):
        self.calls.append((sql, args))
        return "UPDATE 1"


class _FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _FakeAcquire(self.conn)


class TestPersistCaptureResultActivity:
    @pytest.mark.asyncio
    async def test_persist_activity_updates_db_with_asyncpg_pool(self):
        """Persist wrapper should support asyncpg pool integration path."""
        fake_conn = _FakeConn()
        fake_pool = _FakePool(fake_conn)
        with patch("services.database_service.DatabaseService.get_pool", new=AsyncMock(return_value=fake_pool)):
            result = await persist_capture_result_activity(
                {
                    "campaign_id": "11111111-1111-1111-1111-111111111111",
                    "output_video_path": "https://cdn.example/final.mp4",
                    "scenes": [
                        {"scene_index": 0, "narration_text": "A", "timestamp_start": 0.0, "timestamp_end": 3.0},
                        {"scene_index": 1, "narration_text": "B", "timestamp_start": 3.0, "timestamp_end": 5.5},
                    ],
                    "upload_to_storage": False,
                }
            )

        assert result["status"] == "success"
        assert fake_conn.calls, "Expected SQL updates to be executed"
