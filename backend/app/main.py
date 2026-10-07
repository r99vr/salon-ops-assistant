"""نقطة تشغيل الخلفية: FastAPI + المجدول + قناة تيليجرام + webhook الواتساب."""
import hashlib
import hmac
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select

from . import scheduler, telegram_bot
from .api import router
from .config import get_settings
from .db import Base, engine, session_scope
from .engine import handle_inbound
from .models import Salon
from .seed import reset_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("salon")
settings = get_settings()
SAMPLES = Path(__file__).parent / "samples"


def prepare_media() -> None:
    media = Path(settings.media_dir)
    media.mkdir(parents=True, exist_ok=True)
    # صور الإثبات التاريخية في بيانات العرض تنسخ من مجلد الصور التجريبية
    for p in SAMPLES.glob("proof-*"):
        if not (media / p.name).exists():
            shutil.copy(p, media / p.name)


def schema_outdated() -> bool:
    """هل جداول قاعدة البيانات أقدم من الكود؟ (عمود ناقص أو جدول ناقص)

    مشروع عرض ببيانات وهمية: لو تغير الشكل نعيد بناء البيانات بدل ملفات migration.
    مع عميل حقيقي نستخدم Alembic بدل هذا.
    """
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    if not existing:
        return False
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            return True
        cols = {c["name"] for c in insp.get_columns(table.name)}
        if {c.name for c in table.columns} - cols:
            return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    prepare_media()
    if schema_outdated():
        log.warning("شكل قاعدة البيانات قديم — إعادة بناء بيانات العرض")
        reset_database()
    Base.metadata.create_all(engine)
    with session_scope() as db:
        empty = db.scalar(select(Salon).limit(1)) is None
    if empty:
        log.info("قاعدة البيانات فاضية — تعبئة صالون تجريبي")
        reset_database()
    scheduler.start()
    telegram_bot.start_polling()
    yield
    telegram_bot.stop_polling()
    scheduler.stop()


app = FastAPI(title="مساعد تشغيل الصالون", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
app.mount("/media/samples", StaticFiles(directory=SAMPLES), name="samples")
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.get("/health")
def health():
    return {
        "ok": True,
        "ai": settings.ai_enabled,
        "telegram": settings.telegram_enabled,
        "whatsapp": settings.whatsapp_enabled,
        "tables": len(inspect(engine).get_table_names()),
    }


# --------------------------------------------------------------- Telegram webhook (للسيرفر)
@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    background: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(403)
    background.add_task(telegram_bot.process_update, await request.json())
    return {"ok": True}


# --------------------------------------------------------------- WhatsApp Cloud API webhook
@app.get("/webhook/whatsapp")
def wa_verify(
    mode: str = Query(alias="hub.mode", default=""),
    token: str = Query(alias="hub.verify_token", default=""),
    challenge: str = Query(alias="hub.challenge", default=""),
):
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return PlainTextResponse(challenge)
    raise HTTPException(403)


@app.post("/webhook/whatsapp")
async def wa_receive(request: Request, background: BackgroundTasks, x_hub_signature_256: str | None = Header(default=None)):
    raw = await request.body()
    if settings.whatsapp_app_secret:
        expected = "sha256=" + hmac.new(settings.whatsapp_app_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not x_hub_signature_256 or not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(403)
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []):
                background.add_task(_wa_process, m)
    return {"ok": True}


def _wa_process(m: dict) -> None:
    import httpx
    import uuid

    phone = m.get("from", "")
    text, media_url = "", None
    if m.get("type") == "text":
        text = m["text"]["body"]
    elif m.get("type") == "image":
        text = m["image"].get("caption", "")
        try:
            h = {"Authorization": f"Bearer {settings.whatsapp_token}"}
            meta = httpx.get(f"https://graph.facebook.com/{settings.whatsapp_api_version}/{m['image']['id']}", headers=h, timeout=20).json()
            data = httpx.get(meta["url"], headers=h, timeout=30).content
            name = f"wa-{uuid.uuid4().hex[:12]}.jpg"
            (Path(settings.media_dir) / name).write_bytes(data)
            media_url = f"/media/{name}"
        except Exception:
            log.exception("تحميل صورة الواتساب فشل")
    else:
        return
    with session_scope() as db:
        handle_inbound(db, phone, text, media_url, channel="whatsapp")
