"""بيانات صالون تجريبي كامل — «صالون التجميل» (الاسم يتغير من الإعدادات).

كل شي هنا بيانات: لو بغينا كوفي أو مغسلة نكتب ملف seed ثاني بنفس الشكل بدون تغيير الكود.
التواريخ نسبية لوقت التشغيل عشان العرض يطلع «حي» في أي يوم.
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from .cleaning import ensure_runs
from .config import get_settings
from .db import Base, engine, now, session_scope
from .models import (
    Attendance,
    CleaningTask,
    DeviceIssue,
    Invoice,
    Item,
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

settings = get_settings()
TZ = settings.tz

STAFF = [
    # name, phone, role, title, color
    ("منيرة", "966500000001", "owner", "صاحبة الصالون", "plum"),
    ("دانة", "966500000002", "manager", "مديرة الصالون", "slate"),
    ("نورة", "966500000011", "worker", "خبيرة المكياج", "rose"),
    ("ريم", "966500000012", "worker", "البديكير والمنيكير", "coral"),
    ("هيا", "966500000013", "worker", "أخصائية المساج", "sage"),
    ("سارة", "966500000014", "worker", "مصففة الشعر", "amber"),
    ("مريم", "966500000015", "worker", "النظافة والتعقيم", "sky"),
]

SUPPLIERS = [
    ("lamsa", "مؤسسة لمسة للتجميل", "مستحضرات المكياج والصبغات والعناية بالشعر", "أبو فهد", "966500000021", "لمسه,لمسة للتجميل"),
    ("nokhba", "مستودع النخبة لأدوات الصالونات", "أدوات البديكير والمساج والشعر", "خالد", "966500000022", "النخبه,نخبة"),
    ("naqaa", "شركة نقاء للمنظفات", "مواد التنظيف والمناشف والتعطير", "سلمان", "966500000023", "نقاء,نقا"),
]

# section: (name, staff_phone, icon, items)
# consumable: (name, aliases, unit, qty, min, target, price, supplier)
# device: ("@device", name, aliases)
SECTIONS = [
    ("الميكب", "966500000011", "palette", [
        ("كريم أساس", "فاونديشن,الفاونديشن,كريم الاساس", "علبة", 8, 4, 10, 95, "lamsa"),
        ("بودرة تثبيت", "البودره,بودرة", "علبة", 6, 3, 8, 70, "lamsa"),
        ("أحمر شفاه", "روج,الروج,احمر الشفايف", "حبة", 14, 6, 18, 45, "lamsa"),
        ("ماسكرا", "مسكره,الماسكرا", "حبة", 5, 4, 10, 55, "lamsa"),
        ("رموش صناعية", "الرموش,رموش", "علبة", 9, 5, 15, 25, "lamsa"),
        ("مزيل مكياج", "مزيل المكياج,ميسلار", "قارورة", 3, 2, 6, 30, "lamsa"),
        ("إسفنج مكياج", "الاسفنج,بيوتي بلندر,اسفنجات", "كيس", 4, 3, 10, 18, "lamsa"),
        ("فرش مكياج", "الفرش,فرشات", "طقم", 3, 2, 4, 120, "nokhba"),
    ]),
    ("البديكير والمنيكير", "966500000012", "hand", [
        ("مبارد أظافر", "المبارد,مبرد", "حبة", 30, 20, 60, 2, "nokhba"),
        ("مزيل طلاء", "الاسيتون,مزيل المناكير,اسيتون", "قارورة", 4, 2, 6, 22, "nokhba"),
        ("طلاء أظافر", "مناكير,المناكير,الطلاء", "حبة", 26, 12, 30, 28, "lamsa"),
        ("ملح قدمين", "الملح,ملح البديكير", "علبة", 3, 2, 6, 35, "nokhba"),
        ("كريم ترطيب قدمين", "كريم القدمين,كريم الترطيب", "علبة", 3, 2, 5, 48, "lamsa"),
        ("أدوات بديكير", "ادوات البديكير,عدة البديكير", "طقم", 6, 4, 10, 40, "nokhba"),
    ]),
    ("المساج", "966500000013", "leaf", [
        ("زيت مساج", "زيت المساج,الزيت", "لتر", 5, 3, 8, 65, "nokhba"),
        ("زيت لافندر", "اللافندر,زيت اللافندر", "قارورة", 3, 2, 5, 85, "nokhba"),
        ("كريم مساج", "كريم المساج", "علبة", 4, 2, 6, 70, "nokhba"),
        ("شموع عطرية", "الشموع,شمع", "حبة", 10, 6, 20, 15, "naqaa"),
        ("مناديل سرير", "ورق السرير,رول السرير,غطا السرير", "رول", 6, 4, 12, 30, "naqaa"),
    ]),
    ("الشعر", "966500000014", "scissors", [
        ("صبغة بنية", "الصبغه البنيه,صبغة البني,البني", "علبة", 4, 3, 12, 38, "lamsa"),
        ("صبغة أشقر", "الصبغه الشقرا,الاشقر,اشقر", "علبة", 5, 3, 10, 38, "lamsa"),
        ("صبغة سوداء", "الصبغه السودا,الاسود,اسود", "علبة", 7, 3, 10, 38, "lamsa"),
        ("أوكسجين صبغة", "الاوكسجين,اوكسجين,مثبت الصبغه", "قارورة", 6, 4, 12, 25, "lamsa"),
        ("شامبو احترافي", "الشامبو,شامبو", "لتر", 4, 3, 8, 75, "lamsa"),
        ("بلسم احترافي", "البلسم,بلسم", "لتر", 3, 2, 6, 75, "lamsa"),
        ("سيروم شعر", "السيروم,سيروم", "قارورة", 2, 3, 6, 90, "lamsa"),
        ("ورق قصدير", "القصدير,ورق الالمنيوم", "رول", 3, 2, 6, 20, "nokhba"),
        ("@device", "استشوار 1", "الاستشوار الاول,استشوار رقم 1,سشوار 1"),
        ("@device", "استشوار 2", "الاستشوار الثاني,استشوار رقم 2,سشوار 2"),
        ("@device", "استشوار 3", "الاستشوار الثالث,استشوار رقم 3,سشوار 3"),
        ("@device", "مكواة فرد", "السشوار المسطح,المكواه,مكواة الشعر,الفير"),
    ]),
    ("النظافة والتعقيم", "966500000015", "sparkles", [
        ("مناشف بيضاء", "المناشف,فوط,الفوط,مناشف", "حبة", 40, 30, 60, 12, "naqaa"),
        ("مناديل ورقية", "المناديل,كلينكس", "كرتون", 3, 2, 6, 45, "naqaa"),
        ("معقم أسطح", "المعقم,معقم", "قارورة", 4, 3, 8, 28, "naqaa"),
        ("مطهر أدوات", "المطهر,ديتول الادوات,مطهر", "قارورة", 1, 2, 6, 55, "naqaa"),
        ("عبوات تعطير", "معطر الجهاز,عبوة المعطر,التعطير,معطر", "عبوة", 5, 3, 10, 30, "naqaa"),
        ("أكياس نفايات", "الاكياس,اكياس الزباله", "رول", 8, 5, 15, 12, "naqaa"),
        ("منظف أرضيات", "منظف الارضيات,الفلاش,منظف البلاط", "جالون", 2, 2, 5, 35, "naqaa"),
        ("@device", "جهاز تعقيم الأدوات", "جهاز التعقيم,المعقم الحراري,التعقيم,جهاز الأشعة"),
        ("@device", "جهاز تعطير الصالون", "جهاز التعطير,المعطر,الفواحه"),
        ("@device", "جهاز تنظيف الفرش", "منظف الفرش,جهاز الفرش"),
        ("@device", "مكنسة كهربائية", "المكنسه,الكنسه"),
    ]),
]

TASKS = [
    # title, aliases, days (weekday: 0=Mon..6=Sun) — الترتيب هنا هو ترتيب القائمة
    ("تعقيم أدوات البديكير", "تعقيم,الادوات,ادوات البديكير,عقمت", "0123456"),
    ("تنظيف فرش المكياج", "الفرش,فرش المكياج,غسلت الفرش", "0123456"),
    ("تعقيم الكراسي والأسطح", "الكراسي,الاسطح,مسحت الكراسي", "0123456"),
    ("تبديل المناشف وغسلها", "المناشف,الغسيل,بدلت المناشف", "0123456"),
    ("تنظيف الأرضيات", "الارضيات,البلاط,مسحت الارض", "0123456"),
    ("تعطير الصالون", "التعطير,عطرت,المعطر", "0123456"),
    ("تنظيف نهاية اليوم", "نهاية اليوم,التقفيل,قفلت", "0123456"),
]


def reset_database() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with session_scope() as db:
        seed(db)


def seed(db: Session) -> None:
    rnd = random.Random(7)
    t_now = now()
    today = t_now.date()

    salon = Salon(name="صالون التجميل", channel=settings.default_channel)
    db.add(salon)
    db.flush()

    staff = {}
    for name, phone, role, title, color in STAFF:
        s = Staff(salon_id=salon.id, name=name, phone=phone, role=role, title=title, color=color)
        db.add(s)
        staff[phone] = s
    suppliers = {}
    for key, name, cat, rep, phone, aliases in SUPPLIERS:
        sp = Supplier(salon_id=salon.id, name=name, category=cat, rep_name=rep, rep_phone=phone, aliases=aliases)
        db.add(sp)
        suppliers[key] = sp
    db.flush()

    items: dict[str, Item] = {}
    for idx, (sname, phone, icon, rows) in enumerate(SECTIONS):
        sec = Section(salon_id=salon.id, name=sname, staff_id=staff[phone].id, icon=icon, sort=idx)
        db.add(sec)
        db.flush()
        for row in rows:
            if row[0] == "@device":
                it = Item(section_id=sec.id, name=row[1], aliases=row[2], kind="device", unit="جهاز", status="ok")
            else:
                name, aliases, unit, q, mn, tg, price, sup = row
                it = Item(
                    section_id=sec.id, name=name, aliases=aliases, kind="consumable", unit=unit,
                    quantity=Decimal(q), min_qty=Decimal(mn), target_qty=Decimal(tg),
                    unit_price=Decimal(price), supplier_id=suppliers[sup].id,
                )
            db.add(it)
            items[it.name] = it
    db.flush()

    cleaner = staff["966500000015"]
    tasks = []
    for idx, (title, aliases, days) in enumerate(TASKS):
        t = CleaningTask(salon_id=salon.id, title=title, aliases=aliases, sort=idx, days=days, staff_id=cleaner.id)
        db.add(t)
        tasks.append(t)
    db.flush()

    _seed_task_history(db, tasks, rnd, t_now)
    _seed_orders_and_invoices(db, salon, suppliers, items, staff, t_now)
    _seed_device_history(db, items, staff, t_now)
    _seed_attendance(db, staff, rnd, t_now)
    _seed_today_conversations(db, items, staff, suppliers, t_now)
    db.flush()


def _at(day, hh, mm=0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=TZ)


def _proof_image(title: str) -> str | None:
    """صور إثبات جاهزة (تتولد بسكربت samples) — نختار حسب المهمة."""
    mapping = {
        "تعقيم أدوات البديكير": "proof-sterilize.jpg",
        "تنظيف فرش المكياج": "proof-brushes.jpg",
        "تعقيم الكراسي والأسطح": "proof-chairs.jpg",
        "تبديل المناشف وغسلها": "proof-towels.jpg",
        "تنظيف الأرضيات": "proof-floor.jpg",
        "تعطير الصالون": "proof-scent.jpg",
        "تنظيف نهاية اليوم": "proof-closing.jpg",
    }
    name = mapping.get(title)
    if name and (Path(settings.media_dir) / name).exists():
        return f"/media/{name}"
    return None


def _seed_task_history(db: Session, tasks, rnd, t_now) -> None:
    today = t_now.date()
    for back in range(13, 0, -1):
        day = today - timedelta(days=back)
        # المهام تنقفل على مدار اليوم بالترتيب من 10 الصباح لين 10 الليل تقريباً
        minute = 10 * 60
        for t in tasks:
            minute += rnd.randint(50, 120)
            done_at = _at(day, min(minute // 60, 23), minute % 60)
            r = TaskRun(task_id=t.id, run_date=day)
            roll = rnd.random()
            if roll < 0.9:
                r.status, r.done_at, r.proof_url = "done", done_at, _proof_image(t.title)
            else:
                r.status = "missed"
                r.reminded_at = _at(day, 18)
                r.escalated_at = _at(day, 19)
            db.add(r)
    db.flush()
    # اليوم: العاملة خلصت جزء من القائمة حسب الوقت الحالي
    ensure_runs(db, today)
    runs = (
        db.query(TaskRun).join(CleaningTask).filter(TaskRun.run_date == today)
        .order_by(CleaningTask.sort).all()
    )
    hours_in = max(0.0, (t_now.hour * 60 + t_now.minute - 10 * 60) / 60)
    done_count = min(len(runs) - 2, int(hours_in / 1.6)) if hours_in > 0 else 0
    minute = 10 * 60
    for r in runs[: max(done_count, 0)]:
        minute += rnd.randint(40, 90)
        r.status = "done"
        r.done_at = min(_at(today, minute // 60, minute % 60), t_now - timedelta(minutes=5))
        r.proof_url = _proof_image(r.task.title)


def _seed_orders_and_invoices(db, salon, suppliers, items, staff, t_now) -> None:
    today = t_now.date()
    owner = staff["966500000001"]
    history = [
        # days ago, supplier, [(item, qty)], invoice_no, uploader
        (12, "lamsa", [("صبغة بنية", 8), ("أوكسجين صبغة", 6), ("شامبو احترافي", 4)], "LM-2231", "966500000014"),
        (10, "nokhba", [("زيت مساج", 4), ("مبارد أظافر", 40), ("ورق قصدير", 4)], "NK-0912", "966500000013"),
        (8, "naqaa", [("مناشف بيضاء", 25), ("معقم أسطح", 5), ("أكياس نفايات", 10)], "NQ-5520", "966500000015"),
        (6, "lamsa", [("ماسكرا", 6), ("رموش صناعية", 8), ("طلاء أظافر", 12)], "LM-2287", "966500000011"),
        (4, "naqaa", [("مناديل ورقية", 4), ("عبوات تعطير", 6), ("شموع عطرية", 12)], "NQ-5561", "966500000015"),
        (2, "nokhba", [("زيت لافندر", 3), ("كريم مساج", 3), ("أدوات بديكير", 5)], "NK-0950", "966500000012"),
        (1, "lamsa", [("بلسم احترافي", 3), ("كريم أساس", 4)], "LM-2302", "966500000014"),
    ]
    for back, sup_key, lines, inv_no, uploader in history:
        day = today - timedelta(days=back)
        sp = suppliers[sup_key]
        o = Order(
            salon_id=salon.id, supplier_id=sp.id, order_date=day - timedelta(days=1), status="received",
            approved_by=owner.id, approved_at=_at(day - timedelta(days=1), 20, 6),
            sent_at=_at(day - timedelta(days=1), 20, 6), supplier_reply="تم، يوصلكم بكرة الظهر إن شاء الله",
            supplier_replied_at=_at(day - timedelta(days=1), 20, 41), received_at=_at(day, 13, 10),
            created_at=_at(day - timedelta(days=1), 12, 0),
        )
        db.add(o)
        db.flush()
        inv_lines, total = [], Decimal(0)
        for name, q in lines:
            it = items[name]
            db.add(OrderItem(order_id=o.id, item_id=it.id, qty=Decimal(q)))
            inv_lines.append({"item_id": it.id, "name": it.name, "qty": q, "unit_price": float(it.unit_price)})
            total += Decimal(q) * it.unit_price
            db.add(StockEvent(item_id=it.id, delta=Decimal(q), qty_after=it.quantity, source="invoice",
                              staff_id=staff[uploader].id, note=f"فاتورة {inv_no}", created_at=_at(day, 13, 12)))
        vat = (total * Decimal("0.15")).quantize(Decimal("1"))
        db.add(
            Invoice(
                salon_id=salon.id, supplier_id=sp.id, supplier_name=sp.name, invoice_no=inv_no,
                total=total + vat, invoice_date=day, lines=inv_lines, order_id=o.id,
                uploaded_by=staff[uploader].id, extraction="ai", created_at=_at(day, 13, 12),
            )
        )


def _seed_attendance(db, staff, rnd, t_now) -> None:
    """حضور أسبوعين تسجله دانة، واليوم حسب الوقت الحالي (الصالون يفتح 10 الصبح تقريباً)."""
    manager = staff["966500000002"]
    worker_list = [s for s in staff.values() if s.role == "worker"]
    today = t_now.date()
    for back in range(13, -1, -1):
        day = today - timedelta(days=back)
        for w in worker_list:
            arrive = _at(day, 9, 40) + timedelta(minutes=rnd.randint(-15, 45))
            leave = _at(day, 21, 30) + timedelta(minutes=rnd.randint(-40, 60))
            if back == 0:
                if t_now < arrive:
                    continue
                db.add(Attendance(staff_id=w.id, work_date=day, status="present", check_in=arrive,
                                  check_out=leave if t_now > leave else None, recorded_by=manager.id,
                                  updated_at=arrive))
                continue
            if rnd.random() < 0.06:
                db.add(Attendance(staff_id=w.id, work_date=day, status="absent", recorded_by=manager.id,
                                  updated_at=_at(day, 10, 30)))
            else:
                db.add(Attendance(staff_id=w.id, work_date=day, status="present", check_in=arrive,
                                  check_out=leave, recorded_by=manager.id, updated_at=leave))


def _seed_device_history(db, items, staff, t_now) -> None:
    dev = items["جهاز تعطير الصالون"]
    db.add(
        DeviceIssue(
            item_id=dev.id, reported_by=staff["966500000015"].id, description="الجهاز يطفي لحاله بعد دقايق",
            status="resolved", created_at=t_now - timedelta(days=5, hours=3),
            resolved_at=t_now - timedelta(days=4, hours=20),
        )
    )
    dev2 = items["استشوار 3"]
    db.add(
        DeviceIssue(
            item_id=dev2.id, reported_by=staff["966500000014"].id, description="يصدر صوت عالي وريحة حرارة",
            status="resolved", created_at=t_now - timedelta(days=9, hours=5),
            resolved_at=t_now - timedelta(days=8),
        )
    )


def _msg(db, phone, name, role, direction, body, kind, at, media=None, meta=None):
    db.add(
        Message(
            phone=phone, contact_name=name, contact_role=role, direction=direction, body=body, kind=kind,
            created_at=at, media_url=media, meta=meta or {}, channel="simulator",
            transport="received" if direction == "in" else "simulator",
        )
    )


def _seed_today_conversations(db, items, staff, suppliers, t_now) -> None:
    """نواقص اليوم اللي جت من رسائل (السيروم والمطهر) + مسودة طلبية الليلة + محادثات أمس."""
    today = t_now.date()
    yday = today - timedelta(days=1)
    owner = staff["966500000001"]
    sara = staff["966500000014"]
    mariam = staff["966500000015"]
    noura = staff["966500000011"]

    # أمس: محادثة ملخص الثامنة والموافقة وتأكيد المندوب
    _msg(db, owner.phone, owner.name, "owner", "out",
         "مساء الخير 🌙 طلبية اليوم جاهزة للموافقة:\n\n📦 مؤسسة لمسة للتجميل (المندوب: أبو فهد)\n  • بلسم احترافي × 3 لتر\n  • كريم أساس × 4 علبة\n\nالتكلفة التقديرية: 605 ريال\n\nللإرسال ردي بـ «موافقة»\nللتعديل مثلاً: «شيل زيت المساج» أو «الصبغة البنية 8»",
         "summary", _at(yday - timedelta(days=1), 20, 0))
    _msg(db, owner.phone, owner.name, "owner", "in", "موافقة", "owner_command", _at(yday - timedelta(days=1), 20, 6))
    _msg(db, owner.phone, owner.name, "owner", "out",
         "تم ✅ أرسلت الطلبية للمندوب: أبو فهد (مؤسسة لمسة للتجميل)\nأتابع ردهم وأبلغك.", "reply",
         _at(yday - timedelta(days=1), 20, 6))
    _msg(db, owner.phone, owner.name, "owner", "out",
         "🚚 المندوب أبو فهد (مؤسسة لمسة للتجميل) رد على الطلبية:\n«تم، يوصلكم بكرة الظهر إن شاء الله»", "alert",
         _at(yday - timedelta(days=1), 20, 41))

    sup = suppliers["lamsa"]
    _msg(db, sup.rep_phone, sup.rep_name, "supplier", "out",
         "السلام عليكم أبو فهد،\nطلبية جديدة من صالون التجميل:\n\n  • بلسم احترافي × 3 لتر\n  • كريم أساس × 4 علبة\n\nنرجو تأكيد الطلب وموعد التوصيل بالرد على هذي الرسالة. شكراً 🌷",
         "order", _at(yday - timedelta(days=1), 20, 6))
    _msg(db, sup.rep_phone, sup.rep_name, "supplier", "in", "تم، يوصلكم بكرة الظهر إن شاء الله", "supplier_reply",
         _at(yday - timedelta(days=1), 20, 41))
    _msg(db, sup.rep_phone, sup.rep_name, "supplier", "out", "شكراً أبو فهد 🙏 تم تسجيل ردك على الطلب.", "reply",
         _at(yday - timedelta(days=1), 20, 41))

    _msg(db, noura.phone, noura.name, "staff", "in", "الماسكرا قربت تخلص باقي ٥", "shortage", _at(yday, 16, 12))
    _msg(db, noura.phone, noura.name, "staff", "out", "تم ✅ سجلت:\n• ماسكرا: باقي 5 حبة", "reply", _at(yday, 16, 12))

    # اليوم: بلاغين نقص صاروا مسودة طلبية الليلة
    serum, disinf = items["سيروم شعر"], items["مطهر أدوات"]
    morning = min(t_now - timedelta(hours=2), _at(today, 12, 40))
    _msg(db, sara.phone, sara.name, "staff", "in", "السيروم باقي ثنتين بس", "shortage", morning)
    _msg(db, sara.phone, sara.name, "staff", "out",
         "تم ✅ سجلت:\n• سيروم شعر: باقي 2 قارورة ← انضاف لطلبية الليلة 🛒", "reply", morning + timedelta(seconds=4))
    later = morning + timedelta(minutes=50)
    _msg(db, mariam.phone, mariam.name, "staff", "in", "مطهر الادوات باقي قارورة وحده", "shortage", later)
    _msg(db, mariam.phone, mariam.name, "staff", "out",
         "تم ✅ سجلت:\n• مطهر أدوات: باقي 1 قارورة ← انضاف لطلبية الليلة 🛒", "reply", later + timedelta(seconds=4))
    for it, who, at in ((serum, sara, morning), (disinf, mariam, later)):
        db.add(StockEvent(item_id=it.id, delta=Decimal(-1), qty_after=it.quantity, source="message",
                          staff_id=who.id, note="بلاغ نقص", created_at=at))

    db.flush()
    from .orders import add_to_order

    add_to_order(db, serum)
    add_to_order(db, disinf)
