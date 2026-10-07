"""قلب المساعد: استقبال أي رسالة واردة (من أي قناة) وتنفيذ السيناريو المناسب."""
import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import textnorm as tn
from .classifier import Classification, build_context, classify
from .config import get_settings
from .db import now
from .messaging import resolve_contact, send
from .models import (
    CleaningTask,
    ConversationState,
    DeviceIssue,
    Invoice,
    Item,
    Message,
    Order,
    Staff,
    StockEvent,
    Supplier,
    TaskRun,
)
from . import orders as orders_svc
from .orders import approver, fmt_qty, salon

log = logging.getLogger("salon.engine")
settings = get_settings()

CLARIFY_TTL = timedelta(minutes=30)
RESOLVE_WORDS = ["انصلح", "تصلح", "تصلحت", "انصلحت", "اشتغل", "اشتغلت", "تم الاصلاح", "صلحناه", "صلحناها", "رجع يشتغل", "رجعت تشتغل"]


def media_path(media_url: str | None) -> Path | None:
    if not media_url:
        return None
    p = Path(settings.media_dir) / Path(media_url).name
    return p if p.exists() else None


def handle_inbound(db: Session, phone: str, text: str = "", media_url: str | None = None, channel: str = "simulator") -> Message:
    name, role, contact = resolve_contact(db, phone)
    msg = Message(
        phone=phone,
        contact_name=name,
        contact_role=role,
        direction="in",
        body=text or "",
        media_url=media_url,
        channel=channel,
        transport="received",
        created_at=now(),
    )
    db.add(msg)
    db.flush()

    def reply(body: str, kind: str = "reply", meta: dict | None = None):
        return send(db, phone, body, kind=kind, meta={**(meta or {}), "in_reply_to": msg.id}, channel=channel)

    if role == "unknown":
        msg.kind = "other"
        reply("أهلاً 👋 رقمك غير مسجل في النظام. تواصلي مع إدارة الصالون عشان يضيفونك.")
        return msg

    if role == "supplier":
        _handle_supplier(db, msg, contact, reply)
        return msg

    if role in ("owner", "manager") and _handle_approver(db, msg, contact, reply):
        return msg

    _handle_staff(db, msg, contact, reply)
    return msg


# ------------------------------------------------------------------ staff
def _handle_staff(db: Session, msg: Message, staff: Staff, reply) -> None:
    ctx = build_context(db, staff, now().date())
    state = db.get(ConversationState, msg.phone)
    pending = state.state.get("pending") if state and now() - state.updated_at < CLARIFY_TTL else None

    # نصنّف الرسالة لوحدها أولاً: إذا كانت موضوع جديد كامل ما نخلطها بالسؤال السابق
    text, media, attempts = msg.body, msg.media_url, 0
    c = classify(db, ctx, text, media_path(media))
    new_topic = (c.type != "other" and not c.question) or (msg.media_url and pending and pending.get("media"))
    if pending and not new_topic and not (c.question and c.type not in ("other", pending.get("type"))):
        text = f"{pending.get('text', '')} {msg.body}".strip()
        media = msg.media_url or pending.get("media")
        attempts = pending.get("attempts", 0)
        msg.meta = {**msg.meta, "clarifies": pending.get("message_id")}
        c = classify(db, ctx, text, media_path(media))

    msg.kind = c.type
    msg.meta = {**msg.meta, "classification": c.as_dict()}

    if c.question:
        if attempts >= 1:
            _clear_state(db, msg.phone)
            reply("ما قدرت أحددها بدقة 🙏 سجلت رسالتك وراح تشوفها صاحبة الصالون في اللوحة.", kind="reply")
            send(
                db,
                approver(db).phone,
                f"📝 رسالة من {staff.name} ما قدرت أصنفها:\n«{text}»",
                kind="alert",
                meta={"message_id": msg.id},
            )
            return
        _set_state(
            db,
            msg.phone,
            {"pending": {"text": text, "media": media, "message_id": msg.id, "attempts": attempts + 1, "type": c.type}},
        )
        reply(c.question, kind="question")
        return

    _clear_state(db, msg.phone)
    handler = {
        "shortage": _on_shortage,
        "task_proof": _on_task_proof,
        "issue": _on_issue,
        "invoice": _on_invoice,
    }.get(c.type)
    if handler:
        handler(db, msg, staff, c, media, reply)
    else:
        reply(
            f"أهلاً {staff.name} 🌷 أنا مساعد الصالون. أرسلي لي:\n"
            "• الناقص: «خلصت الصبغة البنية» أو صورة الرف\n"
            "• عطل جهاز: «الاستشوار الثاني ما يسخن»\n"
            "• صورة بعد مهمة التنظيف\n"
            "• صورة فاتورة الاستلام",
            kind="reply",
        )


def _on_shortage(db: Session, msg: Message, staff: Staff, c: Classification, media, reply) -> None:
    out = []
    for entry in c.items:
        item = db.get(Item, entry["item_id"])
        before = Decimal(item.quantity)
        rem = entry.get("remaining")
        if rem is None:
            # بلّغت إنه ناقص بدون رقم: نعتبره تحت الحد الأدنى بوحدة
            new = min(before, max(Decimal(item.min_qty) - 1, Decimal(0)))
            note = "بلاغ نقص بدون كمية"
        else:
            new = Decimal(str(rem))
            note = "بلاغ نقص"
        item.quantity = new
        item.updated_at = now()
        db.add(
            StockEvent(
                item_id=item.id, delta=new - before, qty_after=new, source="message",
                message_id=msg.id, staff_id=staff.id, note=note,
            )
        )
        line = f"• {item.name}: باقي {fmt_qty(new)} {item.unit}"
        if item.is_low:
            status, order = orders_svc.add_to_order(db, item)
            if status == "added":
                when = "الطلبية المعلقة" if order.status == "awaiting_approval" else "طلبية الليلة"
                line += f" ← انضاف لـ{when} 🛒"
            elif status == "already":
                line += " ← موجود في طلبية مفتوحة"
            else:
                line += " ← ما له مورد مسجل، بلغت الإدارة"
        out.append(line)
    db.flush()
    reply("تم ✅ سجلت:\n" + "\n".join(out), meta={"items": [e["item_id"] for e in c.items]})


def _on_task_proof(db: Session, msg: Message, staff: Staff, c: Classification, media, reply) -> None:
    run = db.get(TaskRun, c.task_run_id)
    run.status = "done"
    run.done_at = now()
    run.proof_url = media
    run.message_id = msg.id
    db.flush()
    late = run.done_at > run.due_at + timedelta(minutes=15)
    remaining = list(
        db.scalars(
            select(TaskRun)
            .join(CleaningTask)
            .where(
                TaskRun.run_date == run.run_date,
                TaskRun.status == "pending",
                TaskRun.id != run.id,
                CleaningTask.staff_id == staff.id,
            )
            .order_by(TaskRun.due_at)
        )
    )
    body = f"تم ✅ قفلت مهمة «{run.task.title}» الساعة {run.done_at:%H:%M}" + (" (متأخرة شوي)" if late else " 👏")
    if remaining:
        body += "\nالباقي لك اليوم:\n" + "\n".join(f"  • {r.task.title} — {r.due_at:%H:%M}" for r in remaining)
    else:
        body += "\nخلصتي كل مهام اليوم، يعطيك العافية 🌟"
    reply(body, meta={"task_run_id": run.id})


def _on_issue(db: Session, msg: Message, staff: Staff, c: Classification, media, reply) -> None:
    dev = db.get(Item, c.device_id)
    open_issue = db.scalar(select(DeviceIssue).where(DeviceIssue.item_id == dev.id, DeviceIssue.status == "open"))
    if open_issue:
        reply(f"العطل في «{dev.name}» مسجل من قبل ✅ وصاحبة الصالون عندها خبر.")
        return
    dev.status = "broken"
    dev.updated_at = now()
    issue = DeviceIssue(
        item_id=dev.id, reported_by=staff.id, description=c.issue or msg.body,
        image_url=msg.media_url, message_id=msg.id,
    )
    db.add(issue)
    db.flush()
    reply(f"وصل البلاغ ✅ «{dev.name}» صار حالته معطل، وبلغت الإدارة. استخدمي جهاز ثاني لين ينصلح 🙏")
    send(
        db,
        approver(db).phone,
        f"🔧 بلاغ عطل\nالجهاز: {dev.name} ({dev.section.name})\nالمشكلة: {issue.description}\nمن: {staff.name}\n\n"
        f"لما ينصلح ردي: «انصلح {dev.name}»",
        kind="alert",
        meta={"issue_id": issue.id},
    )


def _match_supplier(db: Session, name: str) -> Supplier | None:
    if not name:
        return None
    best = max(
        ((tn.score(name, s.name, s.aliases), s) for s in db.scalars(select(Supplier))),
        key=lambda x: x[0],
        default=(0, None),
    )
    return best[1] if best[0] >= 0.5 else None


def _on_invoice(db: Session, msg: Message, staff: Staff, c: Classification, media, reply) -> None:
    s = salon(db)
    data = c.invoice or {}
    supplier = _match_supplier(db, data.get("supplier", "")) or _match_supplier(db, msg.body)
    open_orders = list(
        db.scalars(select(Order).where(Order.status.in_(("sent", "confirmed"))).order_by(Order.sent_at.desc()))
    )
    if supplier:
        order = next((o for o in open_orders if o.supplier_id == supplier.id), None)
    else:
        # بدون اسم مورد: نختار الطلبية اللي فيها أكثر أصناف من قسم العاملة اللي صورت الفاتورة
        own = {sec.id for sec in staff.sections}
        order = max(
            open_orders,
            key=lambda o: (sum(l.item.section_id in own for l in o.lines), o.sent_at or o.created_at),
            default=None,
        )
        supplier = order.supplier if order else None

    lines = [l for l in data.get("lines", []) if l.get("qty")]
    extraction = "ai"
    if not lines and order:
        # ما قدرنا نقرأ الأسطر: نطابق الفاتورة مع الطلبية المفتوحة
        lines = [
            {"item_id": l.item_id, "name": l.item.name, "qty": float(l.qty), "unit_price": float(l.item.unit_price or 0)}
            for l in order.lines
        ]
        extraction = "matched"
    total = Decimal(str(data.get("total") or 0))
    if not total and lines:
        total = sum((Decimal(str(l["qty"])) * Decimal(str(l.get("unit_price") or 0)) for l in lines), Decimal(0))
    try:
        inv_date = date.fromisoformat(data.get("date") or "")
    except ValueError:
        inv_date = now().date()
    if inv_date > now().date() or inv_date < now().date() - timedelta(days=60):
        inv_date = now().date()

    inv = Invoice(
        salon_id=s.id,
        supplier_id=supplier.id if supplier else None,
        supplier_name=data.get("supplier") or (supplier.name if supplier else ""),
        invoice_no=data.get("invoice_no") or "",
        total=total,
        invoice_date=inv_date,
        image_url=msg.media_url,
        lines=lines,
        order_id=order.id if order else None,
        message_id=msg.id,
        uploaded_by=staff.id,
        extraction=extraction if lines else "pending",
    )
    db.add(inv)
    db.flush()

    added = []
    for l in lines:
        item = db.get(Item, l["item_id"]) if l.get("item_id") else None
        if not item or item.kind != "consumable":
            continue
        q = Decimal(str(l["qty"]))
        item.quantity = Decimal(item.quantity) + q
        item.updated_at = now()
        db.add(
            StockEvent(
                item_id=item.id, delta=q, qty_after=item.quantity, source="invoice",
                message_id=msg.id, staff_id=staff.id, note=f"فاتورة #{inv.id}",
            )
        )
        added.append(f"  • {item.name} +{fmt_qty(q)} (صار {fmt_qty(item.quantity)})")
    if order:
        order.status = "received"
        order.received_at = now()
    db.flush()

    if not lines:
        reply("استلمت صورة الفاتورة ✅ بس ما قدرت أقرأ تفاصيلها، حولتها للإدارة تراجعها.")
        send(db, approver(db).phone, f"🧾 فاتورة من {staff.name} تحتاج مراجعة يدوية في اللوحة.", kind="alert",
             meta={"invoice_id": inv.id})
        return
    who = supplier.name if supplier else (inv.supplier_name or "مورد غير معروف")
    reply(
        f"تم ✅ سجلت فاتورة {who} بمبلغ {fmt_qty(total)} {s.currency}\nوأضفت للمخزون:\n" + "\n".join(added or ["  (ما فيه أصناف مطابقة)"]),
        meta={"invoice_id": inv.id},
    )
    send(
        db,
        approver(db).phone,
        f"📥 وصلت طلبية {who}" + (f" (#{order.id})" if order else "") + f"\nالفاتورة: {fmt_qty(total)} {s.currency} — سجلتها كمصروف وحدثت المخزون.",
        kind="alert",
        meta={"invoice_id": inv.id},
    )


# --------------------------------------------------------------- approver
def _handle_approver(db: Session, msg: Message, who: Staff, reply) -> bool:
    """أوامر صاحبة الصالون/المديرة. يرجع False إذا الرسالة مو أمر (فتنعامل كرسالة عادية)."""
    text = msg.body or ""
    if not text or msg.media_url:
        return False
    awaiting = orders_svc.awaiting_orders(db)

    # إصلاح جهاز
    if tn.contains_any(text, RESOLVE_WORDS):
        broken = list(db.scalars(select(Item).where(Item.kind == "device", Item.status == "broken")))
        scored = sorted(((tn.score(text, d.name, d.aliases), d) for d in broken), key=lambda x: -x[0])
        if scored and (scored[0][0] >= 0.6 or len(broken) == 1):
            dev = scored[0][1]
            resolve_device(db, dev)
            msg.kind = "owner_command"
            reply(f"تمام ✅ «{dev.name}» رجع شغال في النظام.")
            return True

    if not awaiting:
        return False

    if tn.contains_any(text, tn.REJECT_WORDS) and not tn.contains_any(text, tn.REMOVE_WORDS[:4]):
        n = orders_svc.cancel_awaiting(db)
        msg.kind = "owner_command"
        reply(f"تمام، ألغيت {n} طلبية ❌ والأصناف بتظهر في ملخص بكرة إذا لسا ناقصة.")
        return True

    edit = orders_svc.apply_owner_edit(db, text)
    if edit:
        msg.kind = "owner_command"
        db.flush()
        remaining = [o for o in orders_svc.awaiting_orders(db) if o.lines]
        if remaining:
            reply(f"✏️ {edit}.\n\n" + orders_svc.summary_text(db, remaining), kind="summary")
        else:
            reply(f"✏️ {edit}. ما بقى شي في الطلبية.")
        return True

    if tn.contains_any(text, tn.APPROVE_WORDS):
        sent = orders_svc.approve(db, by=who)
        msg.kind = "owner_command"
        names = "، ".join(f"{o.supplier.rep_name} ({o.supplier.name})" for o in sent)
        reply(f"تم ✅ أرسلت الطلبية للمندوب: {names}\nأتابع ردهم وأبلغك.")
        return True
    return False


def resolve_device(db: Session, dev: Item) -> None:
    dev.status = "ok"
    dev.updated_at = now()
    for i in db.scalars(select(DeviceIssue).where(DeviceIssue.item_id == dev.id, DeviceIssue.status == "open")):
        i.status = "resolved"
        i.resolved_at = now()


# --------------------------------------------------------------- supplier
def _handle_supplier(db: Session, msg: Message, supplier: Supplier, reply) -> None:
    msg.kind = "supplier_reply"
    order = db.scalar(
        select(Order)
        .where(Order.supplier_id == supplier.id, Order.status.in_(("sent", "confirmed")))
        .order_by(Order.sent_at.desc())
    )
    if not order:
        reply("أهلاً 🌷 ما عندنا طلبية مفتوحة حالياً. إذا فيه شي ثاني تواصل مع الإدارة.")
        return
    first = order.status == "sent"
    order.status = "confirmed"
    order.supplier_reply = msg.body
    order.supplier_replied_at = now()
    reply(f"شكراً {supplier.rep_name} 🙏 تم تسجيل ردك على الطلب #{order.id}.")
    if first:
        send(
            db,
            approver(db).phone,
            f"🚚 المندوب {supplier.rep_name} ({supplier.name}) رد على الطلبية #{order.id}:\n«{msg.body}»",
            kind="alert",
            meta={"order_id": order.id},
        )


# ------------------------------------------------------------------ state
def _set_state(db: Session, phone: str, state: dict) -> None:
    st = db.get(ConversationState, phone)
    if not st:
        st = ConversationState(phone=phone)
        db.add(st)
    st.state = state
    st.updated_at = now()


def _clear_state(db: Session, phone: str) -> None:
    st = db.get(ConversationState, phone)
    if st:
        st.state = {}
        st.updated_at = now()
