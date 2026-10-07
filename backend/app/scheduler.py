"""المجدول: نبضة كل دقيقة تشغّل اللي حان وقته.

الأوقات (ملخص الثامنة، تقرير الصباح، مهام اليوم) تنقرأ من إعدادات الصالون في كل نبضة،
فلو صاحبة الصالون غيرتها من اللوحة يتغير التشغيل بدون إعادة تشغيل السيرفر.
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from . import cleaning, orders, reports
from .config import get_settings
from .db import now, session_scope
from .models import JobLog

log = logging.getLogger("salon.scheduler")
settings = get_settings()
_scheduler: BackgroundScheduler | None = None

DAILY_WINDOW = timedelta(minutes=30)

JOBS = {
    "tasks": ("tasks_time", cleaning.send_daily_tasks),
    "morning": ("morning_time", reports.morning_report),
    "summary": ("summary_time", orders.nightly_summary),
}


def run_job(name: str, manual: bool = False, **kwargs) -> dict:
    """تشغيل مهمة باسمها (من المجدول أو من زر العرض في اللوحة)."""
    with session_scope() as db:
        if name in JOBS:
            result = JOBS[name][1](db)
            today = now().date()
            row = db.get(JobLog, (name, today))
            if not row:
                db.add(JobLog(job=name, run_date=today, ran_at=now(), manual=manual))
            return result
        if name == "cleaning_check":
            return cleaning.check_overdue(db, force=kwargs.get("force", False))
        if name == "supplier_followup":
            return orders.supplier_followups(db, force=kwargs.get("force", False))
    raise KeyError(name)


def tick() -> None:
    t = now()
    try:
        with session_scope() as db:
            salon = orders.salon(db)
            if not salon:
                return
            cleaning.close_previous_days(db)
            cleaning.ensure_runs(db, t.date())
            due = []
            for name, (attr, _) in JOBS.items():
                at = datetime.combine(t.date(), getattr(salon, attr), tzinfo=settings.tz)
                if at <= t < at + DAILY_WINDOW and not db.get(JobLog, (name, t.date())):
                    due.append(name)
        for name in due:
            log.info("تشغيل المهمة اليومية: %s", name)
            run_job(name)
        run_job("cleaning_check")
        run_job("supplier_followup")
    except Exception:  # المجدول ما يطيح بسبب خطأ واحد
        log.exception("خطأ في نبضة المجدول")


def start() -> None:
    global _scheduler
    if _scheduler or not settings.enable_scheduler:
        return
    _scheduler = BackgroundScheduler(timezone=settings.tz)
    _scheduler.add_job(tick, "cron", second=5, id="tick", max_instances=1, coalesce=True)
    _scheduler.start()
    log.info("المجدول شغال")


def stop() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
