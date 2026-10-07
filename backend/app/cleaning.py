"""جدول النظافة: توليد مهام اليوم، إرسالها، التذكير، والتصعيد."""
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import now
from .messaging import send
from .models import CleaningTask, TaskRun
from .orders import approver, salon

settings = get_settings()


def ensure_runs(db: Session, day: date) -> int:
    """ينشئ تنفيذات اليوم لكل مهمة نشطة (مرة وحدة)."""
    existing = {r.task_id for r in db.scalars(select(TaskRun).where(TaskRun.run_date == day))}
    created = 0
    for t in db.scalars(select(CleaningTask).where(CleaningTask.active.is_(True))):
        if t.id in existing or str(day.weekday()) not in (t.days or "0123456"):
            continue
        due = datetime.combine(day, t.due_time, tzinfo=settings.tz)
        db.add(TaskRun(task_id=t.id, run_date=day, due_at=due, status="pending"))
        created += 1
    db.flush()
    return created


def today_runs(db: Session, day: date | None = None) -> list[TaskRun]:
    day = day or now().date()
    return list(db.scalars(select(TaskRun).where(TaskRun.run_date == day).order_by(TaskRun.due_at)))


def send_daily_tasks(db: Session) -> dict:
    day = now().date()
    ensure_runs(db, day)
    per_staff: dict[int, list[TaskRun]] = defaultdict(list)
    for r in today_runs(db, day):
        if r.task.staff_id and r.status == "pending":
            per_staff[r.task.staff_id].append(r)
    for runs in per_staff.values():
        staff = runs[0].task.staff
        lines = "\n".join(f"  {i}. {r.task.title} — {r.due_at:%H:%M}" for i, r in enumerate(runs, 1))
        send(
            db,
            staff.phone,
            f"صباح الخير {staff.name} ☀️\nمهامك اليوم:\n{lines}\n\nبعد كل مهمة أرسلي صورة، وأنا أقفلها لك ✅",
            kind="tasks",
        )
    return {"staff": len(per_staff)}


def check_overdue(db: Session, force: bool = False) -> dict:
    """بعد موعد المهمة بدون صورة: تذكير للعاملة. بعد المهلة: تنبيه لصاحبة الصالون.

    force=True (زر العرض) يعامل أقرب مهمة معلقة كأنها فات وقتها، عشان العرض ما ينتظر الساعة.
    """
    s = salon(db)
    grace = timedelta(minutes=s.cleaning_grace_minutes)
    t = now()
    ensure_runs(db, t.date())
    reminded = escalated = 0
    pending = [r for r in today_runs(db, t.date()) if r.status == "pending"]
    if force and not pending:
        # وضع العرض بالليل: كل مهام اليوم خلصت، نعيد فتح آخر مهمة كأن وقتها فات للتو
        runs = today_runs(db, t.date())
        if runs:
            r = runs[-1]
            r.status, r.done_at, r.proof_url, r.reminded_at, r.escalated_at = "pending", None, None, None, None
            r.due_at = t - timedelta(minutes=1)
            db.flush()
            pending = [r]
    if force and pending:
        # في وضع العرض نحرك أول مهمة معلقة خطوة وحدة (تذكير ثم تصعيد)
        pending = [next((r for r in pending if not r.escalated_at), pending[0])]
    for r in pending:
        staff = r.task.staff
        if not staff:
            continue
        if not r.reminded_at and (force or t >= r.due_at):
            send(
                db,
                staff.phone,
                f"تذكير 🔔 {staff.name}، مهمة «{r.task.title}» موعدها {r.due_at:%H:%M}.\nأرسلي صورة بعد ما تخلصينها 🙏",
                kind="reminder",
                meta={"task_run_id": r.id},
            )
            r.reminded_at = t
            reminded += 1
        elif r.reminded_at and not r.escalated_at and (force or t >= r.due_at + grace):
            send(
                db,
                approver(db).phone,
                f"⚠️ مهمة «{r.task.title}» (موعدها {r.due_at:%H:%M}) ما تقفلت.\n"
                f"المسؤولة: {staff.name}. ذكّرتها ولا وصلت صورة الإثبات.",
                kind="alert",
                meta={"task_run_id": r.id},
            )
            r.escalated_at = t
            escalated += 1
    return {"reminded": reminded, "escalated": escalated}


def close_previous_days(db: Session) -> int:
    """أي مهمة من أيام سابقة ما تقفلت تصير «فاتت»."""
    n = 0
    for r in db.scalars(select(TaskRun).where(TaskRun.run_date < now().date(), TaskRun.status == "pending")):
        r.status = "missed"
        n += 1
    return n
