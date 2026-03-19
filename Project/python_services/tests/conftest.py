import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("TEMPORAL_ADDRESS", "localhost:7233")
os.environ.setdefault("TEMPORAL_NAMESPACE", "default")
os.environ.setdefault("TEMPORAL_TASK_QUEUE", "ai-influencer-workflows")
os.environ["DEBUG"] = "true"
os.environ.setdefault("POSTIZ_API_URL", "http://postiz.test")
os.environ.setdefault("GROWCHIEF_API_URL", "http://growchief.test")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SUPABASE_URL", "http://supabase.test")
os.environ.setdefault("SUPABASE_KEY", "supabase-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "supabase-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "anthropic-key")
os.environ.setdefault("FAL_AI_API_KEY", "fal-key")
os.environ.setdefault("PLAYHT_API_KEY", "playht-key")
os.environ.setdefault("PLAYHT_USER_ID", "playht-user")
os.environ.setdefault("R2_ACCOUNT_ID", "r2-account")
os.environ.setdefault("R2_ACCESS_KEY_ID", "r2-access")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "r2-secret")
os.environ.setdefault("R2_BUCKET_NAME", "r2-bucket")
os.environ.setdefault("R2_PUBLIC_URL", "http://r2.public")
os.environ.setdefault("IPROYAL_USERNAME", "ipro-user")
os.environ.setdefault("IPROYAL_PASSWORD", "ipro-pass")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "telegram-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "telegram-chat")


class _TelegramStub:
    def __init__(self, *args, **kwargs):
        pass


telegram_mod = types.ModuleType("telegram")
telegram_mod.Bot = _TelegramStub
telegram_mod.InlineKeyboardButton = _TelegramStub
telegram_mod.InlineKeyboardMarkup = _TelegramStub
telegram_mod.Update = _TelegramStub
sys.modules.setdefault("telegram", telegram_mod)

telegram_ext_mod = types.ModuleType("telegram.ext")
telegram_ext_mod.Application = _TelegramStub
telegram_ext_mod.CommandHandler = _TelegramStub
telegram_ext_mod.CallbackQueryHandler = _TelegramStub
telegram_ext_mod.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
sys.modules.setdefault("telegram.ext", telegram_ext_mod)

openai_mod = types.ModuleType("openai")
openai_mod.AsyncOpenAI = _TelegramStub
sys.modules.setdefault("openai", openai_mod)

anthropic_mod = types.ModuleType("anthropic")
anthropic_mod.AsyncAnthropic = _TelegramStub
sys.modules.setdefault("anthropic", anthropic_mod)
