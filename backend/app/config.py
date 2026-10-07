"""إعدادات التطبيق — كلها من متغيرات البيئة عشان نفس الكود يشتغل محلياً وعلى السيرفر."""
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://salon:salon@localhost:5432/salon"
    timezone: str = "Asia/Riyadh"

    # الذكاء الاصطناعي (OpenRouter). بدون مفتاح يشتغل النظام بقواعد نصية بسيطة.
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.5-flash-lite"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # القناة الحية الافتراضية: simulator / telegram / whatsapp (تتغير من شاشة الإعدادات)
    default_channel: str = "simulator"

    # تيليجرام: polling = يسحب الرسائل بنفسه (يشتغل من اللابتوب بدون رابط عام)، webhook = للسيرفر
    telegram_bot_token: str = ""
    telegram_mode: str = "polling"
    telegram_webhook_secret: str = ""

    # الواتساب (Meta Cloud API) — جاهز ومو مفعّل إلا إذا تعبت هذي القيم واخترت القناة
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "salon-ops-verify"
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v23.0"
    # قالب Utility يُستخدم لما تكون نافذة الـ24 ساعة مقفلة (متغير واحد في النص)
    whatsapp_fallback_template: str = "salon_update"
    whatsapp_template_lang: str = "ar"

    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"
    media_dir: str = "media"
    enable_scheduler: bool = True
    # مفتاح بسيط يحمي واجهة اللوحة لما تكون منشورة (فاضي = بدون حماية محلياً)
    dashboard_api_key: str = ""

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openrouter_api_key)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_token and self.whatsapp_phone_number_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
