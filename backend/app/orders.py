"""الطلبيات: تجميع النواقص، ملخص الثامنة، الموافقة، الإرسال للمندوب، والمتابعة."""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import textnorm as tn
from .db import now
from .messaging import send
from .models import Item, Order, OrderItem, Salon, Staff

OPEN_STATES = ("draft", "awaiting_approval", "sent", "confirmed")


def salon(db: Session) -> Salon:
    return db.scalar(select(Salon).limit(1))


def approver(db: Session) -> Staff:
    s = salon(db)
    role = "manager" if s.approver == "manager" else "owner"
    st = db.scalar(select(Staff).where(Staff.role == role, Staff.active.is_(True)))
    return st or db.scalar(select(Staff).where(Staff.role == "owner"))


def fmt_qty(q: Decimal | float) -> str:
    q = float(q)
    return str(int(q)) if q == int(q) else f"{q:g}"


def reorder_qty(item: Item) -> Decimal:
    need = Decimal(item.target_qty or 0) - Decimal(item.quantity or 0)
    return max(need, Decimal(1))


def item_open_order(db: Session, item: Item) -> OrderItem | None:
    return db.scalar(
        select(OrderItem).join(Order).where(OrderItem.item_id == item.id, Order.status.in_(OPEN_STATES)).limit(1)
    )


def add_to_order(db: Session, item: Item) -> tuple[str, Order | None]:
    """يضيف الصنف لطلبية مورده. يرجع (الحالة، الطلبية): added / already / no_supplier."""
    if not item.supplier_id:
        return "no_supplier", None
    existing = item_open_order(db, item)
    if existing:
        return "already", existing.order
    # لو فيه طلبية بانتظار الموافقة لنفس المورد نضيف عليها، وإلا مسودة اليوم
    order = db.scalar(
        select(Order).where(Order.supplier_id == item.supplier_id, Order.status.in_(("draft", "awaiting_approval")))
    )
    if not order:
        order = Order(salon_id=salon(db).id, supplier_id=item.supplier_id, order_date=now().date(), status="draft")
        db.add(order)
        db.flush()
    db.add(OrderItem(order_id=order.id, item_id=item.id, qty=reorder_qty(item)))
    db.flush()
    db.refresh(order)
    return "added", order


def order_lines_text(order: Order) -> str:
    return "\n".join(f"  • {l.item.name} × {fmt_qty(l.qty)} {l.item.unit}" for l in order.lines)


def awaiting_orders(db: Session) -> list[Order]:
    return list(db.scalars(select(Order).where(Order.status == "awaiting_approval").order_by(Order.id)))


def nightly_summary(db: Session) -> dict:
    """ملخص الثامنة: يحوّل المسودات لـ«بانتظار الموافقة» ويرسل ملخص واحد للمعتمِدة."""
    drafts = list(db.scalars(select(Order).where(Order.status == "draft").order_by(Order.id)))
    for o in drafts:
        if o.lines:
            o.status = "awaiting_approval"
        else:
            db.delete(o)
    db.flush()
    orders = [o for o in awaiting_orders(db) if o.lines]
    appr = approver(db)
    if not orders:
        send(db, appr.phone, "مساء الخير 🌙\nما فيه نواقص تحتاج طلب اليوم. كل الأصناف فوق الحد الأدنى ✅", kind="summary")
        return {"orders": 0}
    send(db, appr.phone, summary_text(db, orders), kind="summary", meta={"order_ids": [o.id for o in orders]})
    return {"orders": len(orders)}


def summary_text(db: Session, orders: list[Order]) -> str:
    cur = salon(db).currency
    parts = ["مساء الخير 🌙 طلبية اليوم جاهزة للموافقة:\n"]
    total = Decimal(0)
    for o in orders:
        parts.append(f"📦 {o.supplier.name} (المندوب: {o.supplier.rep_name})")
        parts.append(order_lines_text(o))
        total += o.estimated_total
    parts.append(f"\nالتكلفة التقديرية: {fmt_qty(total)} {cur}")
    parts.append("\nللإرسال ردي بـ «موافقة»")
    parts.append("للتعديل مثلاً: «شيل زيت المساج» أو «الصبغة البنية 8»")
    return "\n".join(parts)


def approve(db: Session, by: Staff | None = None, order_ids: list[int] | None = None) -> list[Order]:
    orders = awaiting_orders(db)
    if order_ids:
        orders = [o for o in orders if o.id in order_ids]
    sent = []
    for o in orders:
        if not o.lines:
            continue
        o.status = "sent"
        o.approved_by = by.id if by else None
        o.approved_at = o.sent_at = now()
        send_to_supplier(db, o)
        sent.append(o)
    return sent


def send_to_supplier(db: Session, o: Order, reminder: bool = False) -> None:
    s = salon(db)
    head = "تذكير 🔔 ما وصلنا تأكيدكم على الطلبية:" if reminder else f"السلام عليكم {o.supplier.rep_name}،\nطلبية جديدة من {s.name}:"
    body = (
        f"{head}\n\n{order_lines_text(o)}\n\n"
        f"رقم الطلب: #{o.id}\n"
        "نرجو تأكيد الطلب وموعد التوصيل بالرد على هذي الرسالة. شكراً 🌷"
    )
    send(db, o.supplier.rep_phone, body, kind="reminder" if reminder else "order", meta={"order_id": o.id})


def cancel_awaiting(db: Session) -> int:
    orders = awaiting_orders(db)
    for o in orders:
        o.status = "cancelled"
    return len(orders)


def apply_owner_edit(db: Session, text: str) -> str | None:
    """تعديلات صاحبة الصالون على الطلبية المعلقة. يرجع وصف التعديل أو None إذا ما فهمت."""
    orders = awaiting_orders(db)
    lines = [l for o in orders for l in o.lines]
    if not lines:
        return None
    scored = sorted(((tn.score(text, l.item.name, l.item.aliases), l) for l in lines), key=lambda x: -x[0])
    if not scored or scored[0][0] < 0.6:
        return None
    line = scored[0][1]
    name = line.item.name
    if tn.contains_any(text, tn.REMOVE_WORDS):
        order = line.order
        db.delete(line)
        db.flush()
        db.refresh(order)
        if not order.lines:
            order.status = "cancelled"
        return f"شلت {name} من الطلبية"
    q = tn.extract_quantity(text)
    if q is not None and q > 0:
        line.qty = Decimal(str(q))
        return f"عدلت {name} إلى {fmt_qty(q)} {line.item.unit}"
    return None


def supplier_followups(db: Session, force: bool = False) -> dict:
    """تذكير المندوب إذا ما رد خلال المهلة، وبعد مهلة ثانية تنبيه لصاحبة الصالون."""
    s = salon(db)
    wait = timedelta(minutes=s.supplier_reminder_minutes)
    reminded = escalated = 0
    for o in db.scalars(select(Order).where(Order.status == "sent")):
        base = o.sent_at or o.created_at
        if not o.reminded_at and (force or now() - base >= wait):
            send_to_supplier(db, o, reminder=True)
            o.reminded_at = now()
            reminded += 1
        elif o.reminded_at and not o.escalated_at and (force or now() - o.reminded_at >= wait):
            send(
                db,
                approver(db).phone,
                f"⚠️ المندوب {o.supplier.rep_name} ({o.supplier.name}) ما رد على الطلبية #{o.id} حتى بعد التذكير.\n"
                f"تقترحين نتواصل معه بمكالمة؟ رقمه: {o.supplier.rep_phone}",
                kind="alert",
                meta={"order_id": o.id},
            )
            o.escalated_at = now()
            escalated += 1
    return {"reminded": reminded, "escalated": escalated}
