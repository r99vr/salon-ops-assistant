"""تقرير الصباح: رسالة وحدة لصاحبة الصالون."""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import now
from .messaging import send
from .models import Invoice, Item, Order, TaskRun
from .orders import approver, fmt_qty, salon


def morning_report(db: Session) -> dict:
    s = salon(db)
    today = now().date()
    yday = today - timedelta(days=1)

    low = [i for i in db.scalars(select(Item).where(Item.kind == "consumable")) if i.is_low]
    broken = list(db.scalars(select(Item).where(Item.kind == "device", Item.status == "broken")))
    runs = list(db.scalars(select(TaskRun).where(TaskRun.run_date == yday)))
    done = [r for r in runs if r.status == "done"]
    missed = [r for r in runs if r.status != "done"]
    invoices = list(db.scalars(select(Invoice).where(Invoice.invoice_date == yday)))
    spent = sum((i.total for i in invoices), Decimal(0))
    waiting = list(db.scalars(select(Order).where(Order.status.in_(("sent", "confirmed")))))

    parts = [f"صباح الخير ☀️ تقرير {s.name} ليوم {today:%d/%m}\n"]
    if low:
        parts.append(f"🔻 النواقص ({len(low)}):")
        parts += [f"  • {i.name}: باقي {fmt_qty(i.quantity)} {i.unit} (الحد {fmt_qty(i.min_qty)})" for i in low[:8]]
        if len(low) > 8:
            parts.append(f"  … و{len(low) - 8} أصناف ثانية في اللوحة")
    else:
        parts.append("✅ ما فيه نواقص")
    if runs:
        parts.append(f"\n🧽 مهام أمس: {len(done)} من {len(runs)} تمت")
        parts += [f"  ✗ {r.task.title} ({r.task.staff.name if r.task.staff else '-'})" for r in missed[:5]]
    if broken:
        parts.append(f"\n🔧 أجهزة معطلة ({len(broken)}):")
        parts += [f"  • {d.name} — {d.section.name}" for d in broken]
    if waiting:
        parts.append(f"\n🚚 طلبيات بالطريق: {len(waiting)}")
        parts += [f"  • {o.supplier.name} — {'مؤكدة' if o.status == 'confirmed' else 'بانتظار رد المندوب'}" for o in waiting]
    parts.append(f"\n💰 مصاريف أمس: {fmt_qty(spent)} {s.currency}" + (f" ({len(invoices)} فاتورة)" if invoices else ""))
    parts.append("\nيومك سعيد 🌷")
    send(db, approver(db).phone, "\n".join(parts), kind="report")
    return {"low": len(low), "broken": len(broken), "runs": len(runs)}
