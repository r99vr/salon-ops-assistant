"""قائمة مهام النظافة اليومية (بدون أوقات): توليد مهام اليوم، إرسالها، المراجعة، والتصعيد.

كل مهمة تنقفل بصورة في أي وقت خلال اليوم. في «وقت المراجعة» المساعد يذكّر عاملة النظافة
باللي باقي، وإذا ما خلصت بعد المهلة يبلّغ الإدارة بقائمة المهام المفتوحة.
"""
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
    """ينشئ مهام اليوم لكل مهمة نشطة (مرة وحدة)."""
    existing = {r.task_id for r in db.scalars(select(TaskRun).where(TaskRun.run_date == day))}
    created = 0
    for t in db.scalars(select(CleaningTask).where(CleaningTask.active.is_(True))):
        if t.id in existing or str(day.weekday()) not in (t.days or "0123456"):
            continue
        db.add(TaskRun(task_id=t.id, run_date=day, status="pending"))
        created += 1
    db.flush()
    return created


def today_runs(db: Session, day: date | None = None) -> list[TaskRun]:
    day = day or now().date()
    return list(
        db.scalars(
            select(TaskRun)
            .join(CleaningTask)
            .where(TaskRun.run_date == day)
            .order_by(CleaningTask.sort, CleaningTask.id)
        )
    )


def check_at(db: Session, day: date) -> datetime:
    return datetime.combine(day, salon(db).tasks_check_time, tzinfo=settings.tz)


def _by_staff(runs: list[TaskRun]) -> dict[int, list[TaskRun]]:
    out: dict[int, list[TaskRun]] = defaultdict(list)
    for r in runs:
        if r.task.staff_id:
            out[r.task.staff_id].append(r)
    return out


def _bullets(runs: list[TaskRun]) -> str:
    return "\n".join(f"  ☐ {r.task.title}" for r in runs)


def send_daily_tasks(db: Session) -> dict:
    day = now().date()
    ensure_runs(db, day)
    groups = _by_staff([r for r in today_runs(db, day) if r.status == "pending"])
    for runs in groups.values():
        staff = runs[0].task.staff
        send(
            db,
            staff.phone,
            f"صباح الخير {staff.name} ☀️\nمهام النظافة اليوم:\n{_bullets(runs)}\n\n"
            "بعد كل مهمة أرسلي صورة، وأنا أقفلها لك ✅",
            kind="tasks",
        )
    return {"staff": len(groups)}


def check_overdue(db: Session, force: bool = False) -> dict:
    """في وقت المراجعة: تذكير للعاملة باللي باقي. بعد المهلة: تنبيه للإدارة.

    force=True (زر العرض) يتقدّم خطوة وحدة في كل ضغطة: تذكير، ثم تنبيه.
    """
    t = now()
    day = t.date()
    ensure_runs(db, day)
    s = salon(db)
    deadline = check_at(db, day)
    grace = timedelta(minutes=s.cleaning_grace_minutes)
    pending = [r for r in today_runs(db, day) if r.status == "pending"]

    if force and not pending:
        # وضع العرض: كل مهام اليوم خلصت، نعيد فتح آخر مهمة عشان نقدر نعرض التذكير
        runs = today_runs(db, day)
        if runs:
            r = runs[-1]
            r.status, r.done_at, r.proof_url, r.reminded_at, r.escalated_at = "pending", None, None, None, None
            db.flush()
            pending = [r]

    reminded = escalated = 0
    for staff_id, runs in _by_staff(pending).items():
        staff = runs[0].task.staff
        not_reminded = [r for r in runs if not r.reminded_at]
        if not_reminded and (force or t >= deadline):
            send(
                db,
                staff.phone,
                f"تذكير 🔔 {staff.name}، باقي من مهام النظافة اليوم:\n{_bullets(runs)}\n\nأرسلي صورة بعد كل وحدة 🙏",
                kind="reminder",
                meta={"task_run_ids": [r.id for r in runs]},
            )
            for r in runs:
                r.reminded_at = r.reminded_at or t
            reminded += 1
            if force:
                continue
        to_escalate = [r for r in runs if r.reminded_at and not r.escalated_at]
        if to_escalate and (force or t >= deadline + grace):
            send(
                db,
                approver(db).phone,
                f"⚠️ مهام النظافة ما تقفلت كلها اليوم.\nالمسؤولة: {staff.name}. ذكّرتها ولا وصلت صور الإثبات لـ:\n"
                f"{_bullets(runs)}",
                kind="alert",
                meta={"task_run_ids": [r.id for r in runs]},
            )
            for r in to_escalate:
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
