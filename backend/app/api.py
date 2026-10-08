"""واجهة اللوحة (JSON) + محاكي الواتساب + أزرار العرض."""
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import orders as orders_svc
from . import scheduler
from . import attendance as attendance_svc
from .cleaning import ensure_runs, today_runs
from .config import get_settings
from .db import get_db, now
from .engine import handle_inbound, resolve_device
from .models import (
    Attendance,
    CleaningTask,
    DeviceIssue,
    Invoice,
    Item,
    JobLog,
    Message,
    Order,
    OrderItem,
    Salon,
    Section,
    Staff,
    StockEvent,
    Supplier,
    TaskRun,
)
from .seed import reset_database
from .telegram_bot import bot_username, invite_link

settings = get_settings()


def require_key(x_api_key: str | None = Header(default=None)):
    if settings.dashboard_api_key and x_api_key != settings.dashboard_api_key:
        raise HTTPException(401, "مفتاح اللوحة غير صحيح")


router = APIRouter(prefix="/api", dependencies=[Depends(require_key)])


# ----------------------------------------------------------- serializers
def f(v) -> float | None:
    return float(v) if v is not None else None


def ts(v: datetime | None) -> str | None:
    return v.astimezone(settings.tz).isoformat() if v else None


def item_out(i: Item) -> dict:
    return {
        "id": i.id, "name": i.name, "aliases": i.aliases, "kind": i.kind, "unit": i.unit,
        "quantity": f(i.quantity), "min_qty": f(i.min_qty), "target_qty": f(i.target_qty),
        "unit_price": f(i.unit_price), "supplier_id": i.supplier_id,
        "supplier": i.supplier.name if i.supplier else None, "status": i.status, "is_low": i.is_low,
        "section_id": i.section_id, "section": i.section.name, "updated_at": ts(i.updated_at),
    }


def staff_out(s: Staff) -> dict:
    return {
        "id": s.id, "name": s.name, "phone": s.phone, "role": s.role, "title": s.title, "color": s.color,
        "active": s.active, "sections": [x.name for x in s.sections],
        "telegram_linked": bool(s.telegram_chat_id), "invite_code": s.invite_code,
        "invite_link": invite_link(s.invite_code),
    }


def supplier_out(s: Supplier) -> dict:
    return {
        "id": s.id, "name": s.name, "category": s.category, "rep_name": s.rep_name, "rep_phone": s.rep_phone,
        "telegram_linked": bool(s.telegram_chat_id), "invite_code": s.invite_code,
        "invite_link": invite_link(s.invite_code),
    }


def run_out(r: TaskRun) -> dict:
    status = r.status
    # بعد التذكير (وقت المراجعة) المهمة المفتوحة تعتبر متأخرة
    if status == "pending" and r.reminded_at:
        status = "overdue"
    return {
        "id": r.id, "task_id": r.task_id, "title": r.task.title, "date": r.run_date.isoformat(),
        "status": status, "done_at": ts(r.done_at), "proof_url": r.proof_url,
        "reminded_at": ts(r.reminded_at), "escalated_at": ts(r.escalated_at),
        "staff": r.task.staff.name if r.task.staff else None,
    }


def order_out(o: Order) -> dict:
    return {
        "id": o.id, "status": o.status, "date": o.order_date.isoformat(),
        "supplier": {"id": o.supplier.id, "name": o.supplier.name, "rep_name": o.supplier.rep_name},
        "lines": [
            {"id": l.id, "item_id": l.item_id, "name": l.item.name, "unit": l.item.unit, "qty": f(l.qty),
             "unit_price": f(l.item.unit_price)}
            for l in o.lines
        ],
        "estimated_total": f(o.estimated_total), "approved_at": ts(o.approved_at), "sent_at": ts(o.sent_at),
        "supplier_reply": o.supplier_reply, "supplier_replied_at": ts(o.supplier_replied_at),
        "reminded_at": ts(o.reminded_at), "received_at": ts(o.received_at), "created_at": ts(o.created_at),
    }


def invoice_out(i: Invoice) -> dict:
    return {
        "id": i.id, "supplier": i.supplier.name if i.supplier else i.supplier_name, "invoice_no": i.invoice_no,
        "total": f(i.total), "date": i.invoice_date.isoformat(), "image_url": i.image_url, "lines": i.lines,
        "order_id": i.order_id, "extraction": i.extraction,
        "uploaded_by": i.uploader.name if i.uploader else None, "created_at": ts(i.created_at),
    }


def message_out(m: Message) -> dict:
    return {
        "id": m.id, "phone": m.phone, "name": m.contact_name, "role": m.contact_role, "direction": m.direction,
        "body": m.body, "media_url": m.media_url, "kind": m.kind, "channel": m.channel,
        "transport": m.transport, "created_at": ts(m.created_at),
        "classification": (m.meta or {}).get("classification"),
    }


def salon_out(s: Salon) -> dict:
    return {
        "id": s.id, "name": s.name, "approver": s.approver, "channel": s.channel, "currency": s.currency,
        "summary_time": s.summary_time.strftime("%H:%M"), "morning_time": s.morning_time.strftime("%H:%M"),
        "tasks_time": s.tasks_time.strftime("%H:%M"), "supplier_reminder_minutes": s.supplier_reminder_minutes,
        "cleaning_grace_minutes": s.cleaning_grace_minutes,
        "tasks_check_time": s.tasks_check_time.strftime("%H:%M"),
        "timezone": settings.timezone,
    }


def attendance_rows(db: Session, day: date) -> list[dict]:
    rows = {a.staff_id: a for a in db.scalars(select(Attendance).where(Attendance.work_date == day))}
    out = []
    for st in attendance_svc.workers(db):
        a = rows.get(st.id)
        mins = None
        if a and a.check_in and a.check_out:
            mins = max(0, int((a.check_out - a.check_in).total_seconds() // 60))
        status = "none"
        if a:
            status = "absent" if a.status == "absent" else ("left" if a.check_out else "present")
        out.append({
            "staff_id": st.id, "name": st.name, "title": st.title, "color": st.color, "status": status,
            "check_in": ts(a.check_in) if a else None, "check_out": ts(a.check_out) if a else None,
            "minutes": mins, "recorded_by": a.recorder.name if a and a.recorder else None,
        })
    return out


# ------------------------------------------------------------- overview
@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    t = now()
    today = t.date()
    ensure_runs(db, today)
    db.commit()
    s = orders_svc.salon(db)
    consumables = list(db.scalars(select(Item).where(Item.kind == "consumable")))
    low = sorted([i for i in consumables if i.is_low], key=lambda i: float(i.quantity / (i.min_qty or 1)))
    devices = list(db.scalars(select(Item).where(Item.kind == "device")))
    broken = [d for d in devices if d.status == "broken"]
    runs = today_runs(db, today)
    open_orders = list(db.scalars(select(Order).where(Order.status.in_(orders_svc.OPEN_STATES)).order_by(Order.id)))

    start = today - timedelta(days=13)
    inv = list(db.scalars(select(Invoice).where(Invoice.invoice_date >= start)))
    by_day = defaultdict(float)
    for i in inv:
        by_day[i.invoice_date] += float(i.total)
    spend_series = [{"date": (start + timedelta(days=d)).isoformat(), "total": by_day.get(start + timedelta(days=d), 0.0)}
                    for d in range(14)]
    month_start = today.replace(day=1)
    month_spend = db.scalar(select(func.coalesce(func.sum(Invoice.total), 0)).where(Invoice.invoice_date >= month_start))

    # نسبة إنجاز المهام لآخر 7 أيام
    week = []
    for d in range(6, -1, -1):
        day = today - timedelta(days=d)
        rs = list(db.scalars(select(TaskRun).where(TaskRun.run_date == day)))
        week.append({"date": day.isoformat(), "done": sum(r.status == "done" for r in rs), "total": len(rs)})

    alerts = list(db.scalars(
        select(Message).where(Message.kind.in_(("alert", "summary", "report"))).order_by(Message.created_at.desc()).limit(6)
    ))
    return {
        "salon": salon_out(s),
        "now": ts(t),
        "stats": {
            "low_count": len(low), "items_count": len(consumables), "devices_count": len(devices),
            "broken_count": len(broken), "tasks_done": sum(r.status == "done" for r in runs), "tasks_total": len(runs),
            "open_orders": len(open_orders), "month_spend": f(month_spend),
        },
        "low_items": [item_out(i) for i in low],
        "broken_devices": [
            {**item_out(d), "issue": _open_issue(db, d)} for d in broken
        ],
        "today_tasks": [run_out(r) for r in runs],
        "attendance": attendance_rows(db, today),
        "open_orders": [order_out(o) for o in open_orders],
        "spend_series": spend_series,
        "task_week": week,
        "alerts": [message_out(m) for m in alerts],
    }


def _open_issue(db: Session, d: Item) -> dict | None:
    i = db.scalar(select(DeviceIssue).where(DeviceIssue.item_id == d.id, DeviceIssue.status == "open"))
    if not i:
        return None
    return {"id": i.id, "description": i.description, "reported_by": i.reporter.name if i.reporter else None,
            "created_at": ts(i.created_at), "image_url": i.image_url}


# ------------------------------------------------------------ inventory
@router.get("/inventory")
def inventory(db: Session = Depends(get_db)):
    sections = list(db.scalars(select(Section).order_by(Section.sort)))
    return {
        "sections": [
            {
                "id": s.id, "name": s.name, "icon": s.icon,
                "staff": {"id": s.staff.id, "name": s.staff.name, "color": s.staff.color} if s.staff else None,
                "items": [{**item_out(i), "issue": _open_issue(db, i) if i.kind == "device" else None} for i in s.items],
            }
            for s in sections
        ],
        "suppliers": [supplier_out(s) for s in db.scalars(select(Supplier).order_by(Supplier.id))],
    }


class ItemPatch(BaseModel):
    quantity: float | None = None
    min_qty: float | None = None
    target_qty: float | None = None
    unit_price: float | None = None
    supplier_id: int | None = None
    name: str | None = None
    aliases: str | None = None
    unit: str | None = None


@router.patch("/items/{item_id}")
def patch_item(item_id: int, body: ItemPatch, db: Session = Depends(get_db)):
    it = db.get(Item, item_id) or _404()
    data = body.model_dump(exclude_unset=True)
    if "quantity" in data and data["quantity"] is not None:
        new = Decimal(str(data.pop("quantity")))
        if new != it.quantity:
            db.add(StockEvent(item_id=it.id, delta=new - it.quantity, qty_after=new, source="manual", note="تعديل من اللوحة"))
            it.quantity = new
    for k, v in data.items():
        setattr(it, k, Decimal(str(v)) if k in ("min_qty", "target_qty", "unit_price") and v is not None else v)
    it.updated_at = now()
    db.commit()
    return item_out(it)


class ItemCreate(BaseModel):
    section_id: int
    name: str
    kind: str = "consumable"
    unit: str = "حبة"
    quantity: float = 0
    min_qty: float = 0
    target_qty: float = 0
    unit_price: float = 0
    supplier_id: int | None = None
    aliases: str = ""


@router.post("/items")
def create_item(body: ItemCreate, db: Session = Depends(get_db)):
    it = Item(**{k: (Decimal(str(v)) if isinstance(v, float) else v) for k, v in body.model_dump().items()})
    if it.kind == "device":
        it.unit = "جهاز"
    db.add(it)
    db.commit()
    return item_out(it)


@router.get("/items/{item_id}/history")
def item_history(item_id: int, db: Session = Depends(get_db)):
    events = list(db.scalars(select(StockEvent).where(StockEvent.item_id == item_id).order_by(StockEvent.created_at.desc()).limit(20)))
    return [
        {"id": e.id, "delta": f(e.delta), "qty_after": f(e.qty_after), "source": e.source, "note": e.note,
         "staff": e.staff.name if e.staff else None, "created_at": ts(e.created_at)}
        for e in events
    ]


@router.post("/devices/{item_id}/resolve")
def resolve(item_id: int, db: Session = Depends(get_db)):
    it = db.get(Item, item_id) or _404()
    resolve_device(db, it)
    db.commit()
    return item_out(it)


@router.get("/devices/issues")
def device_issues(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(DeviceIssue).order_by(DeviceIssue.created_at.desc()).limit(30)))
    return [
        {"id": i.id, "device": i.item.name, "section": i.item.section.name, "description": i.description,
         "status": i.status, "reported_by": i.reporter.name if i.reporter else None,
         "created_at": ts(i.created_at), "resolved_at": ts(i.resolved_at), "image_url": i.image_url}
        for i in rows
    ]


# ----------------------------------------------------------- attendance
@router.get("/attendance")
def attendance_page(days: int = 7, db: Session = Depends(get_db)):
    today = now().date()
    days = max(1, min(days, 31))
    history = []
    for d in range(days - 1, -1, -1):
        day = today - timedelta(days=d)
        history.append({"date": day.isoformat(), "rows": attendance_rows(db, day)})
    manager = db.scalar(select(Staff).where(Staff.role == "manager"))
    return {"today": attendance_rows(db, today), "history": history,
            "recorder": manager.name if manager else None}


# ---------------------------------------------------------------- tasks
@router.get("/tasks")
def tasks(day: date | None = None, db: Session = Depends(get_db)):
    day = day or now().date()
    if day == now().date():
        ensure_runs(db, day)
        db.commit()
    runs = today_runs(db, day)
    templates = list(
        db.scalars(select(CleaningTask).where(CleaningTask.active.is_(True)).order_by(CleaningTask.sort, CleaningTask.id))
    )
    history = []
    for d in range(13, -1, -1):
        dd = now().date() - timedelta(days=d)
        rs = list(db.scalars(select(TaskRun).where(TaskRun.run_date == dd)))
        history.append({"date": dd.isoformat(), "done": sum(r.status == "done" for r in rs),
                        "missed": sum(r.status == "missed" for r in rs), "total": len(rs)})
    return {
        "date": day.isoformat(),
        "runs": [run_out(r) for r in runs],
        "templates": [
            {"id": t.id, "title": t.title, "days": t.days,
             "staff_id": t.staff_id, "staff": t.staff.name if t.staff else None, "aliases": t.aliases}
            for t in templates
        ],
        "history": history,
    }


class TaskIn(BaseModel):
    title: str
    days: str = "0123456"
    staff_id: int | None = None
    aliases: str = ""


@router.post("/tasks")
def create_task(body: TaskIn, db: Session = Depends(get_db)):
    s = orders_svc.salon(db)
    last = db.scalar(select(func.coalesce(func.max(CleaningTask.sort), 0)))
    t = CleaningTask(salon_id=s.id, title=body.title, sort=last + 1, days=body.days,
                     staff_id=body.staff_id, aliases=body.aliases)
    db.add(t)
    db.flush()
    # تنضاف لقائمة اليوم مباشرة إذا اليوم من أيامها
    ensure_runs(db, now().date())
    db.commit()
    return {"id": t.id}


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, body: TaskIn, db: Session = Depends(get_db)):
    t = db.get(CleaningTask, task_id) or _404()
    t.title, t.days, t.staff_id, t.aliases = body.title, body.days, body.staff_id, body.aliases
    db.commit()
    return {"ok": True}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(CleaningTask, task_id) or _404()
    t.active = False
    for r in db.scalars(select(TaskRun).where(TaskRun.task_id == t.id, TaskRun.run_date >= now().date(), TaskRun.status == "pending")):
        db.delete(r)
    db.commit()
    return {"ok": True}


@router.post("/task-runs/{run_id}/done")
def mark_done(run_id: int, db: Session = Depends(get_db)):
    r = db.get(TaskRun, run_id) or _404()
    r.status, r.done_at = "done", now()
    db.commit()
    return run_out(r)


# --------------------------------------------------------------- orders
@router.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Order).where(Order.status != "draft").order_by(Order.created_at.desc()).limit(40)))
    drafts = list(db.scalars(select(Order).where(Order.status == "draft").order_by(Order.id)))
    invoices = list(db.scalars(select(Invoice).order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).limit(40)))
    s = orders_svc.salon(db)
    return {
        "drafts": [order_out(o) for o in drafts],
        "orders": [order_out(o) for o in rows],
        "invoices": [invoice_out(i) for i in invoices],
        "summary_time": s.summary_time.strftime("%H:%M"),
    }


class ApproveIn(BaseModel):
    order_ids: list[int] | None = None


@router.post("/orders/approve")
def approve_orders(body: ApproveIn, db: Session = Depends(get_db)):
    appr = orders_svc.approver(db)
    sent = orders_svc.approve(db, by=appr, order_ids=body.order_ids)
    if sent:
        from .messaging import send

        names = "، ".join(o.supplier.rep_name for o in sent)
        send(db, appr.phone, f"تم ✅ اعتمدتِ الطلبية من اللوحة وأرسلتها للمندوب: {names}", kind="reply")
    db.commit()
    return {"sent": [o.id for o in sent]}


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    o = db.get(Order, order_id) or _404()
    o.status = "cancelled"
    db.commit()
    return order_out(o)


class LinePatch(BaseModel):
    qty: float


@router.patch("/order-lines/{line_id}")
def patch_line(line_id: int, body: LinePatch, db: Session = Depends(get_db)):
    l = db.get(OrderItem, line_id) or _404()
    if l.order.status not in ("draft", "awaiting_approval"):
        raise HTTPException(400, "الطلبية أُرسلت ولا يمكن تعديلها")
    if body.qty <= 0:
        order = l.order
        db.delete(l)
        db.flush()
        db.refresh(order)
        if not order.lines:
            order.status = "cancelled"
    else:
        l.qty = Decimal(str(body.qty))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------- settings
@router.get("/settings")
def get_settings_api(db: Session = Depends(get_db)):
    s = orders_svc.salon(db)
    return {
        "salon": salon_out(s),
        "staff": [staff_out(x) for x in db.scalars(select(Staff).order_by(Staff.id))],
        "sections": [
            {"id": x.id, "name": x.name, "icon": x.icon, "staff_id": x.staff_id, "items": len(x.items)}
            for x in db.scalars(select(Section).order_by(Section.sort))
        ],
        "suppliers": [supplier_out(x) for x in db.scalars(select(Supplier).order_by(Supplier.id))],
        "channels": {
            "ai": settings.ai_enabled, "ai_model": settings.openrouter_model if settings.ai_enabled else None,
            "telegram": settings.telegram_enabled, "telegram_bot": bot_username(),
            "whatsapp": settings.whatsapp_enabled,
        },
    }


class SalonPatch(BaseModel):  # noqa: D101
    name: str | None = None
    approver: str | None = None
    channel: str | None = None
    summary_time: str | None = None
    morning_time: str | None = None
    tasks_time: str | None = None
    tasks_check_time: str | None = None
    supplier_reminder_minutes: int | None = None
    cleaning_grace_minutes: int | None = None


@router.patch("/settings")
def patch_settings(body: SalonPatch, db: Session = Depends(get_db)):
    s = orders_svc.salon(db)
    data = body.model_dump(exclude_unset=True)
    if data.get("channel") and data["channel"] not in ("simulator", "telegram", "whatsapp"):
        raise HTTPException(400, "قناة غير معروفة")
    if data.get("channel") == "telegram" and not settings.telegram_enabled:
        raise HTTPException(400, "أضف TELEGRAM_BOT_TOKEN في ملف .env أولاً")
    if data.get("channel") == "whatsapp" and not settings.whatsapp_enabled:
        raise HTTPException(400, "أضف بيانات WhatsApp Cloud API في ملف .env أولاً")
    for k, v in data.items():
        if k.endswith("_time") and v:
            v = time.fromisoformat(v)
        setattr(s, k, v)
    db.commit()
    return salon_out(s)


class StaffIn(BaseModel):
    name: str
    phone: str
    role: str = "worker"
    title: str = ""
    color: str = "rose"
    section_ids: list[int] = []


@router.post("/staff")
def create_staff(body: StaffIn, db: Session = Depends(get_db)):
    s = orders_svc.salon(db)
    st = Staff(salon_id=s.id, name=body.name, phone=body.phone, role=body.role, title=body.title, color=body.color)
    db.add(st)
    db.flush()
    for sec in db.scalars(select(Section).where(Section.id.in_(body.section_ids))):
        sec.staff_id = st.id
    db.commit()
    return staff_out(st)


@router.patch("/staff/{staff_id}")
def update_staff(staff_id: int, body: StaffIn, db: Session = Depends(get_db)):
    st = db.get(Staff, staff_id) or _404()
    st.name, st.phone, st.role, st.title, st.color = body.name, body.phone, body.role, body.title, body.color
    for sec in db.scalars(select(Section).where(or_(Section.id.in_(body.section_ids), Section.staff_id == st.id))):
        sec.staff_id = st.id if sec.id in body.section_ids else (None if sec.staff_id == st.id else sec.staff_id)
    db.commit()
    return staff_out(st)


@router.post("/staff/{staff_id}/unlink")
def unlink_staff(staff_id: int, db: Session = Depends(get_db)):
    st = db.get(Staff, staff_id) or _404()
    st.telegram_chat_id = None
    db.commit()
    return staff_out(st)


class SupplierIn(BaseModel):
    name: str
    category: str = ""
    rep_name: str
    rep_phone: str


@router.post("/suppliers")
def create_supplier(body: SupplierIn, db: Session = Depends(get_db)):
    s = orders_svc.salon(db)
    sp = Supplier(salon_id=s.id, **body.model_dump())
    db.add(sp)
    db.commit()
    return supplier_out(sp)


@router.patch("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, body: SupplierIn, db: Session = Depends(get_db)):
    sp = db.get(Supplier, supplier_id) or _404()
    for k, v in body.model_dump().items():
        setattr(sp, k, v)
    db.commit()
    return supplier_out(sp)


# ------------------------------------------------------------ simulator
@router.get("/sim/contacts")
def sim_contacts(db: Session = Depends(get_db)):
    last = {}
    for m in db.scalars(select(Message).order_by(Message.created_at.desc()).limit(400)):
        last.setdefault(m.phone, m)
    out = []
    for st in db.scalars(select(Staff).where(Staff.active.is_(True)).order_by(Staff.id)):
        role = st.role if st.role in ("owner", "manager") else "staff"
        out.append({"phone": st.phone, "name": st.name, "subtitle": st.title, "role": role, "color": st.color,
                    "last": message_out(last[st.phone]) if st.phone in last else None})
    for sp in db.scalars(select(Supplier).order_by(Supplier.id)):
        out.append({"phone": sp.rep_phone, "name": sp.rep_name, "subtitle": f"مندوب {sp.name}", "role": "supplier",
                    "color": "teal", "last": message_out(last[sp.rep_phone]) if sp.rep_phone in last else None})
    return out


@router.get("/sim/thread/{phone}")
def sim_thread(phone: str, after: int = 0, db: Session = Depends(get_db)):
    q = select(Message).where(Message.phone == phone, Message.id > after).order_by(Message.created_at, Message.id)
    return [message_out(m) for m in db.scalars(q)]


@router.post("/sim/send")
async def sim_send(
    phone: str = Form(...),
    text: str = Form(""),
    sample: str = Form(""),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    media_url = None
    media_dir = Path(settings.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    if image is not None and image.filename:
        ext = Path(image.filename).suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            raise HTTPException(400, "الصور فقط (jpg / png / webp)")
        name = f"sim-{uuid.uuid4().hex[:12]}{ext}"
        (media_dir / name).write_bytes(await image.read())
        media_url = f"/media/{name}"
    elif sample:
        src = Path(__file__).parent / "samples" / Path(sample).name
        if not src.exists():
            raise HTTPException(404, "الصورة التجريبية غير موجودة")
        name = f"sim-{uuid.uuid4().hex[:12]}{src.suffix}"
        (media_dir / name).write_bytes(src.read_bytes())
        media_url = f"/media/{name}"
    if not text.strip() and not media_url:
        raise HTTPException(400, "الرسالة فاضية")
    msg = handle_inbound(db, phone, text.strip(), media_url, channel="simulator")
    db.commit()
    return message_out(msg)


@router.get("/sim/samples")
def sim_samples():
    folder = Path(__file__).parent / "samples"
    meta = {
        "shelf-dye.jpg": ("رف الصبغات", "staff"),
        "shelf-towels.jpg": ("رف المناشف", "staff"),
        "invoice-lamsa.jpg": ("فاتورة لمسة", "staff"),
        "invoice-naqaa.jpg": ("فاتورة نقاء", "staff"),
        "proof-sterilize.jpg": ("بعد التعقيم", "staff"),
        "proof-brushes.jpg": ("فرش نظيفة", "staff"),
        "proof-floor.jpg": ("أرضية نظيفة", "staff"),
        "dryer.jpg": ("استشوار", "staff"),
    }
    out = []
    for p in sorted(folder.glob("*")) if folder.exists() else []:
        label = meta.get(p.name, (p.stem, "staff"))[0]
        out.append({"file": p.name, "url": f"/media/samples/{p.name}", "label": label})
    return out


# ----------------------------------------------------------------- demo
@router.post("/demo/run/{job}")
def demo_run(job: str):
    try:
        return {"job": job, "result": scheduler.run_job(job, manual=True, force=True)}
    except KeyError:
        raise HTTPException(404, "مهمة غير معروفة")


@router.post("/demo/reset")
def demo_reset():
    reset_database()
    return {"ok": True}


@router.get("/messages")
def messages(limit: int = 60, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Message).order_by(Message.created_at.desc()).limit(min(limit, 200))))
    return [message_out(m) for m in rows]


def _404():
    raise HTTPException(404, "غير موجود")
