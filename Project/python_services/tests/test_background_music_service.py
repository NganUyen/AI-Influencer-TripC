import json
from pathlib import Path

from services.background_music_service import BackgroundMusicService


def test_background_music_service_selects_local_track_by_profile():
    track = BackgroundMusicService.select_track(
        profile="product_explainer",
        max_duration_seconds=60,
    )

    assert track["profile"] == "product_explainer"
    assert track["duration_seconds"] <= 60
    assert track["path"].endswith("bgm_corporate_atlasaudio.mp3")


def test_background_music_service_selects_new_bgm_track_by_profile():
    track = BackgroundMusicService.select_track(
        group="bgm",
        profile="electro_drive",
        max_duration_seconds=60,
    )

    assert track["group"] == "bgm"
    assert track["profile"] == "electro_drive"
    assert track["path"].endswith("bgm_electro_drive.mp3")


def test_background_music_service_selects_movement_track_by_profile():
    track = BackgroundMusicService.select_track(
        group="movement",
        profile="natural",
        max_duration_seconds=60,
    )

    assert track["group"] == "movement"
    assert track["profile"] == "natural"
    assert track["path"].endswith("movement_natural.mp3")


def test_background_music_service_lists_tracks_from_manifest_without_audio_files(
    tmp_path,
    monkeypatch,
):
    library_root = tmp_path / "audio_library"
    bgm_dir = library_root / "bgm"
    bgm_dir.mkdir(parents=True)
    (bgm_dir / "library.json").write_text(
        json.dumps(
            [
                {
                    "id": "bgm_demo_track",
                    "group": "bgm",
                    "profile": "demo",
                    "duration_seconds": 30,
                    "filename": "demo-track.mp3",
                    "relative_path": "bgm/demo-track.mp3",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(BackgroundMusicService, "_library_root", library_root)
    monkeypatch.setattr(
        BackgroundMusicService,
        "_legacy_manifest_path",
        library_root / "library.json",
    )

    tracks = BackgroundMusicService.list_tracks(group="bgm")

    assert len(tracks) == 1
    assert tracks[0]["group"] == "bgm"
    assert tracks[0]["path"] == str(Path(library_root / "bgm" / "demo-track.mp3"))
