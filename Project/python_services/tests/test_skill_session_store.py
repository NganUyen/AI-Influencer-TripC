from unittest.mock import patch

from services import skill_session_store
from services.skill_session_store import TelegramSkillSessionStore


def test_skill_session_store_initializes_redis_when_configured():
    fake_client = object()
    TelegramSkillSessionStore._redis_client = None
    TelegramSkillSessionStore._redis_enabled = False
    TelegramSkillSessionStore._redis_init_attempted = False

    with patch.object(skill_session_store, "Redis") as redis_cls:
        redis_cls.from_url.return_value = fake_client
        with patch.object(skill_session_store.settings, "REDIS_URL", "redis://redis:6379"):
            TelegramSkillSessionStore._init_redis()

    assert TelegramSkillSessionStore._redis_enabled is True
    assert TelegramSkillSessionStore._redis_client is fake_client
    redis_cls.from_url.assert_called_once_with("redis://redis:6379", decode_responses=True)
