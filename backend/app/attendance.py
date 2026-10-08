"""تحضير العاملات: المديرة (أو صاحبة الصالون) ترسل للمساعد مين وصلت ومين طلعت.

أمثلة يفهمها:
  «نورة وصلت»  «وصلت ريم وهيا»  «الكل وصل»  «سارة وصلت 9:30»
  «طلعت مريم»  «نورة راحت الساعة 10 الليل»  «ريم غايبة اليوم»
  «مين حاضر؟»  «الحضور»
"""
import re
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import textnorm as tn
from .config import get_settings
from .db import now
from .models import Attendance, Staff

settings = get_settings()

IN_WORDS = ["وصلت", "وصل", "وصلو", "وصلوا", "جت", "جات", "جاو", "جو", "حضرت", "حضر", "حضروا", "داومت", "دخلت", "حاضره", "حاضرين", "موجوده", "موجودين"]
OUT_WORDS = ["طلعت", "طلع", "طلعو", "طلعوا", "راحت", "راح", "راحو", "راحوا", "خرجت", "خرج", "مشت", "روحت", "انصرفت", "انصرفوا", "قفلت دوامها", "خلصت دوامها"]
ABSENT_WORDS = ["غايبه", "غائبه", "غياب", "غايبين", "ما جت", "ماجت", "ما حضرت", "ماحضرت", "ما داومت", "اجازه", "إجازه", "مريضه", "معتذره", "ما بتجي", "مابتجي"]
ALL_WORDS = ["الكل", "كلهم", "الجميع", "كل البنات", "الموظفات كلهم"]
QUERY_WORDS = ["مين حاضر", "مين موجود", "مين وصل", "الحضور", "التحضير", "مين طلع", "مين غايب"]

PM_HINTS = ["م", "مساء", "مساءا", "العصر", "عصر", "المغرب", "مغرب", "الليل", "بالليل", "العشا", "الظهر", "ظهر"]
AM_HINTS = ["ص", "صباحا", "الصبح", "صبح", "الصباح"]


def workers(db: Session) -> list[Staff]:
    return list(db.scalars(select(Staff).where(Staff.role == "worker", Staff.active.is_(True)).order_by(Staff.id)))


def _names_in(text: str, staff: list[Staff]) -> list[Staff]:
    words = tn.normalize(text).split()
    cands = set(words)
    for w in words:  # «وريم» ← «ريم»
        if w.startswith("و") and len(w) > 3:
            cands.add(w[1:])
    found = []
    for s in staff:
        if tn.normalize(s.name) in cands:
            found.append(s)
    return found


def _parse_time(text: str, day: date) -> datetime | None:
    """«9:30» «الساعة 10 الليل» «4م» ← وقت. بدون ص/م: الأرقام الصغيرة (1–6) تعتبر مساءً."""
    n = tn.normalize(text)
    m = re.search(r"(?<!\d)(\d{1,2})(?:[:\.](\d{2}))?(?!\d)", n)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h > 23 or mi > 59:
        return None
    suffix = re.match(r"\s?(م|ص)(?:\s|$)", n[m.end():])
    words = set(n.split()) | {tn.strip_al(w) for w in n.split()}
    pm = (suffix and suffix.group(1) == "م") or any(tn.strip_al(tn.normalize(x)) in words for x in PM_HINTS[1:])
    am = (suffix and suffix.group(1) == "ص") or any(tn.strip_al(tn.normalize(x)) in words for x in AM_HINTS[1:])
    if h < 12 and (pm or (not am and h < 7)):
        h += 12
    return datetime.combine(day, time(h, mi), tzinfo=settings.tz)


def _record(db: Session, staff: Staff, day: date) -> Attendance:
    a = db.scalar(select(Attendance).where(Attendance.staff_id == staff.id, Attendance.work_date == day))
    if not a:
        a = Attendance(staff_id=staff.id, work_date=day)
        db.add(a)
    return a


def fmt(dt: datetime | None) -> str:
    if not dt:
        return ""
    h = dt.astimezone(settings.tz)
    return f"{((h.hour + 11) % 12) + 1}:{h.minute:02d} {'ص' if h.hour < 12 else 'م'}"


def duration(a: Attendance) -> str:
    if not (a.check_in and a.check_out):
        return ""
    mins = max(0, int((a.check_out - a.check_in).total_seconds() // 60))
    return f"{mins // 60}س {mins % 60}د" if mins >= 60 else f"{mins}د"


def today_summary(db: Session, day: date | None = None) -> str:
    day = day or now().date()
    rows = {a.staff_id: a for a in db.scalars(select(Attendance).where(Attendance.work_date == day))}
    lines = []
    for s in workers(db):
        a = rows.get(s.id)
        if not a:
            lines.append(f"  ⏳ {s.name}: ما وصلت")
        elif a.status == "absent":
            lines.append(f"  ❌ {s.name}: غايبة")
        elif a.check_out:
            lines.append(f"  🚪 {s.name}: من {fmt(a.check_in)} إلى {fmt(a.check_out)} ({duration(a)})")
        else:
            lines.append(f"  ✅ {s.name}: وصلت {fmt(a.check_in)}")
    present = sum(1 for a in rows.values() if a.status == "present" and a.check_in and not a.check_out)
    return f"الحضور اليوم ({present} موجودة الحين):\n" + "\n".join(lines)


def handle(db: Session, text: str, sender: Staff, message_id: int | None) -> str | None:
    """يرجع الرد إذا كانت الرسالة تحضير، وإلا None."""
    if not text:
        return None
    staff = workers(db)
    t = now()
    day = t.date()
    names = _names_in(text, staff)
    everyone = tn.contains_any(text, ALL_WORDS)

    if not names and not everyone:
        if tn.contains_any(text, QUERY_WORDS):
            return today_summary(db, day)
        return None

    kind = None
    if tn.contains_any(text, ABSENT_WORDS):
        kind = "absent"
    elif tn.contains_any(text, OUT_WORDS):
        kind = "out"
    elif tn.contains_any(text, IN_WORDS):
        kind = "in"
    if not kind:
        if tn.contains_any(text, QUERY_WORDS):
            return today_summary(db, day)
        return None

    targets = staff if everyone and not names else names
    at = _parse_time(text, day) or t
    if at > t + timedelta(minutes=5):
        at = t  # وقت بالمستقبل غالباً غلط في الفهم
    done, notes = [], []
    for s in targets:
        a = _record(db, s, day)
        a.recorded_by, a.message_id, a.updated_at = sender.id, message_id, t
        if kind == "in":
            if a.check_in and a.status == "present" and everyone and not names:
                continue  # «الكل وصل» ما يغيّر وقت اللي سجلناها قبل
            a.status, a.check_in, a.check_out = "present", at, None
            done.append(f"{s.name} {fmt(at)}")
        elif kind == "out":
            if not a.check_in or a.status == "absent":
                a.status = "present"
                notes.append(f"{s.name} ما كان مسجل لها حضور، سجلت الخروج بس")
            if a.check_in and at < a.check_in:
                at = t
            a.check_out = at
            done.append(f"{s.name} {fmt(at)}" + (f" ({duration(a)})" if a.check_in else ""))
        else:
            a.status, a.check_in, a.check_out = "absent", None, None
            done.append(s.name)
    db.flush()

    if not done:
        return "الكل مسجلات من قبل ✅\n\n" + today_summary(db, day)
    head = {"in": "تم ✅ سجلت حضور:", "out": "تم ✅ سجلت خروج:", "absent": "تم ✅ سجلت غياب:"}[kind]
    body = head + "\n" + "\n".join(f"  • {d}" for d in done)
    if notes:
        body += "\n\n" + "\n".join(f"ملاحظة: {n}" for n in notes)
    missing = [s.name for s in staff if not db.scalar(select(Attendance).where(Attendance.staff_id == s.id, Attendance.work_date == day))]
    if kind == "in" and missing:
        body += "\n\nباقي ما وصلن: " + "، ".join(missing)
    return body


def report_line(db: Session, day: date) -> str | None:
    rows = list(db.scalars(select(Attendance).where(Attendance.work_date == day)))
    if not rows:
        return None
    present = [a for a in rows if a.status == "present"]
    absent = [a.staff.name for a in rows if a.status == "absent"]
    no_out = [a.staff.name for a in present if a.check_in and not a.check_out]
    line = f"👥 حضور أمس: {len(present)} من {len(workers(db))}"
    if absent:
        line += f" (غياب: {'، '.join(absent)})"
    if no_out:
        line += f"\n  ما سُجل خروج: {'، '.join(no_out)}"
    return line
