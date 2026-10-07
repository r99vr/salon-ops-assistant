"""قناة تيليجرام: استقبال الرسائل (polling أو webhook) وربط كل شخص برابط دعوته.

التيليجرام ما يعطي رقم الجوال، فكل عاملة/مندوب يفتح رابط دعوة خاص فيه مرة وحدة:
t.me/<bot>?start=<invite_code>  ← نربط رقم المحادثة بالشخص، وبعدها كل رسائله تنعرف.
"""
import logging
import threading
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select

from .config import get_settings
from .db import session_scope
from .engine import handle_inbound
from .messaging import telegram_api, telegram_send
from .models import Staff, Supplier

log = logging.getLogger("salon.telegram")
settings = get_settings()

_bot_username: str | None = None
_thread: threading.Thread | None = None
_stop = threading.Event()


def bot_username() -> str | None:
    global _bot_username
    if _bot_username or not settings.telegram_enabled:
        return _bot_username
    try:
        data = telegram_api("getMe", timeout=10)
        if data.get("ok"):
            _bot_username = data["result"]["username"]
    except httpx.HTTPError as e:
        log.warning("getMe فشل: %s", e)
    return _bot_username


def invite_link(code: str) -> str | None:
    u = bot_username()
    return f"https://t.me/{u}?start={code}" if u else None


def _download_photo(file_id: str) -> str | None:
    try:
        info = telegram_api("getFile", {"file_id": file_id})
        path = info["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{path}"
        r = httpx.get(url, timeout=30)
        r.raise_for_status()
        ext = Path(path).suffix or ".jpg"
        name = f"tg-{uuid.uuid4().hex[:12]}{ext}"
        Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
        (Path(settings.media_dir) / name).write_bytes(r.content)
        return f"/media/{name}"
    except (httpx.HTTPError, KeyError) as e:
        log.warning("تحميل الصورة فشل: %s", e)
        return None


def process_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat_id = str(msg["chat"]["id"])
    text = (msg.get("text") or msg.get("caption") or "").strip()

    with session_scope() as db:
        if text.startswith("/start"):
            code = text.split(maxsplit=1)[1].strip() if " " in text else ""
            person = None
            if code:
                person = db.scalar(select(Staff).where(Staff.invite_code == code)) or db.scalar(
                    select(Supplier).where(Supplier.invite_code == code)
                )
            if not person:
                telegram_send(chat_id, "أهلاً 👋 افتحي رابط الدعوة الخاص فيك من إدارة الصالون عشان أتعرف عليك.")
                return
            # فك أي ربط سابق لنفس المحادثة (مفيد في العرض لما جوال واحد يجرب أكثر من دور)
            for model in (Staff, Supplier):
                for other in db.scalars(select(model).where(model.telegram_chat_id == chat_id)):
                    other.telegram_chat_id = None
            db.flush()
            person.telegram_chat_id = chat_id
            name = person.name if isinstance(person, Staff) else person.rep_name
            role = person.title if isinstance(person, Staff) else f"مندوب {person.name}"
            telegram_send(chat_id, f"أهلاً {name} 🌷 تم ربطك بمساعد الصالون ({role}).\nأرسلي رسائلك وصورك هنا مثل ما تسوين بالواتساب.")
            return

        person = db.scalar(select(Staff).where(Staff.telegram_chat_id == chat_id)) or db.scalar(
            select(Supplier).where(Supplier.telegram_chat_id == chat_id)
        )
        if not person:
            telegram_send(chat_id, "ما تعرفت عليك 🙏 افتحي رابط الدعوة الخاص فيك من إدارة الصالون أولاً.")
            return
        phone = person.phone if isinstance(person, Staff) else person.rep_phone

        media_url = None
        if msg.get("photo"):
            media_url = _download_photo(msg["photo"][-1]["file_id"])
        elif msg.get("document", {}).get("mime_type", "").startswith("image/"):
            media_url = _download_photo(msg["document"]["file_id"])
        if not text and not media_url:
            telegram_send(chat_id, "أقدر أستقبل نصوص وصور بس حالياً 🙏")
            return
        try:
            telegram_api("sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=5)
        except httpx.HTTPError:
            pass
        handle_inbound(db, phone, text, media_url, channel="telegram")


def _poll_loop() -> None:
    offset = None
    try:
        telegram_api("deleteWebhook", {"drop_pending_updates": False}, timeout=10)
    except httpx.HTTPError:
        pass
    log.info("تيليجرام: بدأ الاستقبال (polling) — @%s", bot_username())
    while not _stop.is_set():
        try:
            payload = {"timeout": 25, "allowed_updates": ["message", "edited_message"]}
            if offset:
                payload["offset"] = offset
            data = telegram_api("getUpdates", payload, timeout=35)
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    process_update(upd)
                except Exception:
                    log.exception("فشل معالجة رسالة تيليجرام")
        except httpx.HTTPError as e:
            log.warning("تيليجرام polling: %s", e)
            _stop.wait(5)


def start_polling() -> None:
    global _thread
    if not settings.telegram_enabled or settings.telegram_mode != "polling" or _thread:
        return
    _stop.clear()
    _thread = threading.Thread(target=_poll_loop, name="telegram-poll", daemon=True)
    _thread.start()


def stop_polling() -> None:
    _stop.set()
