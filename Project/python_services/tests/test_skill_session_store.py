from unittest.mock import patch

import pytest

from services import skill_session_store
from services.skill_session_store import TelegramSkillSessionStore
from skills.base import SkillSession


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


@pytest.mark.asyncio
async def test_get_session_discards_stale_memory_when_redis_has_no_session():
    class _FakeRedisClient:
        async def get(self, key):
            return None

    chat_id = 123456
    key = TelegramSkillSessionStore._session_key(chat_id)
    TelegramSkillSessionStore._redis_client = _FakeRedisClient()
    TelegramSkillSessionStore._redis_enabled = True
    TelegramSkillSessionStore._redis_init_attempted = True
    TelegramSkillSessionStore._memory_sessions = {
        key: SkillSession(
            skill_name="persona-creator",
            step_key="preview",
        ).model_dump(mode="json")
    }

    session = await TelegramSkillSessionStore.get_session(chat_id)

    assert session is None
    assert key not in TelegramSkillSessionStore._memory_sessions
