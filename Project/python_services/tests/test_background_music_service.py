from services.background_music_service import BackgroundMusicService


def test_background_music_service_selects_storage_track_by_profile():
    track = BackgroundMusicService.select_track(
        profile="product_explainer",
        max_duration_seconds=60,
    )

    assert track["profile"] == "product_explainer"
    assert track["duration_seconds"] <= 60
    assert track["storage_path"] == "bgm/bgm_corporate_atlasaudio.mp3"
    assert track["storage_path"].endswith("bgm_corporate_atlasaudio.mp3")
    assert track["access_url"].startswith("http://")
    assert track["path"] == track["access_url"]


def test_background_music_service_selects_new_bgm_track_by_profile():
    track = BackgroundMusicService.select_track(
        group="bgm",
        profile="electro_drive",
        max_duration_seconds=60,
    )

    assert track["group"] == "bgm"
    assert track["profile"] == "electro_drive"
    assert track["storage_path"] == "bgm/bgm_electro_drive.mp3"
    assert track["storage_path"].endswith("bgm_electro_drive.mp3")
    assert track["preview_path"].startswith("http://")


def test_background_music_service_selects_movement_track_by_profile():
    track = BackgroundMusicService.select_track(
        group="movement",
        profile="natural",
        max_duration_seconds=60,
    )

    assert track["group"] == "movement"
    assert track["profile"] == "natural"
    assert track["storage_path"] == "movement/movement_natural.mp3"
    assert track["storage_path"].endswith("movement_natural.mp3")
    assert track["access_url"].startswith("http://")
