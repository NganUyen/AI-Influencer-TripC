from services.background_music_service import BackgroundMusicService


def test_background_music_service_selects_local_track_by_profile():
    track = BackgroundMusicService.select_track(
        profile="product_explainer",
        max_duration_seconds=60,
    )

    assert track["profile"] == "product_explainer"
    assert track["duration_seconds"] <= 60
    assert track["path"].endswith("product_explainer_soft.mp3")
