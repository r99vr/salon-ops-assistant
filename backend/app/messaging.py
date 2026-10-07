"""طبقة القنوات للرسائل الصادرة.

كل رسالة تنحفظ في الأرشيف وتبان في المحاكي دائماً، وبعدها توصل عبر القناة:
- simulator: داخل اللوحة فقط
- telegram: بوت تيليجرام (مجاني، للعرض المباشر)
- whatsapp: Meta WhatsApp Cloud API (جاهز، يتفعّل مع عميل حقيقي)

الرد على رسالة واردة يرجع لنفس القناة اللي جت منها. الرسائل اللي يبدأها النظام
(ملخص الثامنة، تقرير الصباح، رسالة المندوب) تروح للقناة الحية المختارة في الإعدادات.
"""
import logging
import re
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import now
from .models import Message, Salon, Staff, Supplier

log = logging.getLogger("salon.messaging")
settings = get_settings()


def resolve_contact(db: Session, phone: str) -> tuple[str, str, Staff | Supplier | None]:
    """يرجع (الاسم، الدور، الكائن) لأي رقم: عاملة، صاحبة الصالون، مديرة، أو مندوب."""
    st = db.scalar(select(Staff).where(Staff.phone == phone))
    if st:
        role = st.role if st.role in ("owner", "manager") else "staff"
        return st.name, role, st
    sp = db.scalar(select(Supplier).where(Supplier.rep_phone == phone))
    if sp:
        return sp.rep_name, "supplier", sp
    return phone, "unknown", None


def live_channel(db: Session) -> str:
    salon = db.scalar(select(Salon).limit(1))
    return salon.channel if salon else settings.default_channel


def send(
    db: Session,
    phone: str,
    body: str,
    kind: str = "reply",
    meta: dict | None = None,
    channel: str | None = None,
) -> Message:
    name, role, contact = resolve_contact(db, phone)
    ch = channel or live_channel(db)
    msg = Message(
        phone=phone,
        contact_name=name,
        contact_role=role,
        direction="out",
        body=body,
        kind=kind,
        meta=meta or {},
        channel=ch,
        transport="simulator",
        created_at=now(),
    )
    db.add(msg)
    db.flush()

    if ch == "telegram":
        chat_id = getattr(contact, "telegram_chat_id", None)
        if not settings.telegram_enabled:
            msg.transport = "failed"
            msg.meta = {**msg.meta, "error": "TELEGRAM_BOT_TOKEN غير مضبوط"}
        elif not chat_id:
            msg.transport = "not_linked"
        else:
            ok, info = telegram_send(chat_id, body)
            msg.transport = "sent" if ok else "failed"
            msg.meta = {**msg.meta, "tg": info}
    elif ch == "whatsapp":
        if not settings.whatsapp_enabled:
            msg.transport = "failed"
            msg.meta = {**msg.meta, "error": "بيانات الواتساب غير مضبوطة"}
        else:
            ok, info = _whatsapp_send(db, phone, body)
            msg.transport = "sent" if ok else "failed"
            msg.meta = {**msg.meta, "wa": info}
    return msg


# ---------------------------------------------------------------- Telegram
def telegram_api(method: str, payload: dict | None = None, timeout: float = 20) -> dict:
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    r = httpx.post(url, json=payload or {}, timeout=timeout)
    return r.json()


def telegram_send(chat_id: str, body: str) -> tuple[bool, dict]:
    try:
        data = telegram_api("sendMessage", {"chat_id": chat_id, "text": body[:4096]})
        if not data.get("ok"):
            log.warning("Telegram error: %s", data)
            return False, {"error": data.get("description")}
        return True, {"id": data["result"]["message_id"]}
    except httpx.HTTPError as e:
        log.warning("Telegram HTTP error: %s", e)
        return False, {"error": str(e)}


# ---------------------------------------------------------------- WhatsApp
def _window_open(db: Session, phone: str) -> bool:
    last_in = db.scalar(
        select(Message.created_at)
        .where(Message.phone == phone, Message.direction == "in", Message.channel == "whatsapp")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    return bool(last_in and now() - last_in < timedelta(hours=23, minutes=50))


def _graph_post(payload: dict) -> tuple[bool, dict]:
    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
    try:
        r = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {settings.whatsapp_token}"}, timeout=20)
        data = r.json()
        if r.status_code >= 400:
            log.warning("WhatsApp error %s: %s", r.status_code, data)
            return False, {"error": data.get("error", data)}
        return True, {"id": (data.get("messages") or [{}])[0].get("id")}
    except httpx.HTTPError as e:
        log.warning("WhatsApp HTTP error: %s", e)
        return False, {"error": str(e)}


def _whatsapp_send(db: Session, phone: str, body: str) -> tuple[bool, dict]:
    to = re.sub(r"\D", "", phone)
    if _window_open(db, phone):
        return _graph_post(
            {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"preview_url": False, "body": body}}
        )
    # خارج نافذة الـ24 ساعة: لازم قالب Utility معتمد. متغيرات القوالب ما تقبل أسطر جديدة.
    flat = re.sub(r"\s*\n+\s*", " • ", body).strip()[:1000]
    return _graph_post(
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": settings.whatsapp_fallback_template,
                "language": {"code": settings.whatsapp_template_lang},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": flat}]}],
            },
        }
    )
