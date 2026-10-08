"""تصنيف الرسالة الواردة من عاملة لوحدة من أربع: نقص / إثبات مهمة / عطل / فاتورة.

المسار الأساسي: نموذج يقرأ النص والصورة (OpenRouter).
المسار البديل: قواعد نصية بسيطة لما ما فيه مفتاح أو فشل النموذج.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import textnorm as tn
from .ai import AIError, chat_json
from .config import get_settings
from .models import CleaningTask, Item, Section, Staff, Supplier, TaskRun

log = logging.getLogger("salon.classifier")
settings = get_settings()

TYPES = ("shortage", "task_proof", "issue", "invoice", "other")  # «attendance» يُعالج قبل التصنيف


@dataclass
class Classification:
    type: str = "other"
    items: list[dict] = field(default_factory=list)  # [{"item_id": 3, "remaining": 0}]
    device_id: int | None = None
    issue: str = ""
    task_run_id: int | None = None
    invoice: dict | None = None
    question: str | None = None
    source: str = "rules"
    confidence: float = 0.0

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Context:
    staff: Staff
    own_items: list[Item]
    all_items: list[Item]
    pending_runs: list[TaskRun]
    suppliers: list[Supplier]


def build_context(db: Session, staff: Staff, today: date) -> Context:
    all_items = list(db.scalars(select(Item).join(Section).order_by(Section.sort, Item.id)))
    own_section_ids = {s.id for s in staff.sections}
    own = [i for i in all_items if i.section_id in own_section_ids]
    runs = list(
        db.scalars(
            select(TaskRun)
            .join(CleaningTask)
            .where(TaskRun.run_date == today, TaskRun.status == "pending", CleaningTask.staff_id == staff.id)
            .order_by(CleaningTask.sort, CleaningTask.id)
        )
    )
    suppliers = list(db.scalars(select(Supplier)))
    return Context(staff, own, all_items, runs, suppliers)


def classify(db: Session, ctx: Context, text: str, image: Path | None) -> Classification:
    if settings.ai_enabled:
        try:
            c = _classify_ai(ctx, text, image)
            c.source = "ai"
            return c
        except AIError as e:
            log.warning("رجعنا للقواعد النصية: %s", e)
    return _classify_rules(ctx, text, image)


# ------------------------------------------------------------------ AI path
SYSTEM = """أنت مساعد تشغيل داخل صالون نسائي. العاملات يرسلن رسائل واتساب قصيرة بالعامية السعودية، أحياناً مع صورة.
مهمتك تصنيف الرسالة لنوع واحد واستخراج البيانات، وترجع JSON فقط بدون أي كلام.

الأنواع:
- "shortage": صنف ناقص أو خلص أو قرب يخلص (نص مثل "خلصت الصبغة البنية" أو صورة رف فاضي).
- "task_proof": صورة تثبت إنجاز مهمة نظافة أو تعقيم (أو نص يقول خلصت المهمة مع صورة).
- "issue": جهاز خربان أو فيه مشكلة.
- "invoice": صورة فاتورة أو سند استلام من مورد.
- "other": سلام، شكر، أو شي ما له علاقة.

قواعد:
- استخدم أرقام الأصناف والأجهزة والمهام من القوائم المعطاة فقط. لا تخترع رقم.
- "remaining" = الكمية الباقية بوحدة الصنف إذا ذُكرت ("باقي علبتين" = 2، "خلصت" = 0). إذا ما ذُكرت ضع null.
- في الصورة: عدّ الوحدات الظاهرة إذا كان واضحاً أن الرف شبه فاضي.
- إذا الرسالة غامضة ولا تقدر تحدد الصنف أو الجهاز بثقة، ضع "question" بسؤال واحد قصير جداً بالعامية موجّه للعاملة (بصيغة المؤنث)، واترك القوائم فاضية.
- الفاتورة: استخرج اسم المورد كما هو مكتوب، رقم الفاتورة، الإجمالي، التاريخ (YYYY-MM-DD)، والأسطر. اربط كل سطر بـ item_id إذا تطابق مع صنف معروف، وإلا null.

الشكل المطلوب بالضبط:
{"type": "...", "confidence": 0.0-1.0,
 "items": [{"item_id": 0, "remaining": null}],
 "device_id": null, "issue": "",
 "task_run_id": null,
 "invoice": null | {"supplier": "", "invoice_no": "", "total": 0, "date": "", "lines": [{"item_id": null, "name": "", "qty": 0, "unit_price": null}]},
 "question": null}"""


def _catalog(ctx: Context) -> str:
    own_ids = {i.id for i in ctx.own_items}
    lines = []
    for i in ctx.all_items:
        tag = " ⟵ قسمها" if i.id in own_ids else ""
        kind = "جهاز" if i.kind == "device" else f"مستهلك/{i.unit}"
        alias = f" (يسمونه: {i.aliases})" if i.aliases else ""
        lines.append(f"{i.id}: {i.name}{alias} — {i.section.name} — {kind}{tag}")
    return "\n".join(lines)


def _classify_ai(ctx: Context, text: str, image: Path | None) -> Classification:
    runs = "\n".join(f"{r.id}: {r.task.title}" for r in ctx.pending_runs) or "لا يوجد"
    sections = "، ".join(s.name for s in ctx.staff.sections) or "بدون قسم"
    suppliers = "، ".join(s.name for s in ctx.suppliers)
    user = (
        f"المرسلة: {ctx.staff.name} — {ctx.staff.title} — أقسامها: {sections}\n\n"
        f"الأصناف والأجهزة:\n{_catalog(ctx)}\n\n"
        f"مهام النظافة المعلقة لها اليوم:\n{runs}\n\n"
        f"الموردين: {suppliers}\n\n"
        f"نص الرسالة: {text or '(بدون نص)'}\n"
        f"فيها صورة: {'نعم' if image else 'لا'}"
    )
    data = chat_json(SYSTEM, user, image)
    log.info("AI classification: %s", json.dumps(data, ensure_ascii=False)[:500])
    return _validate(ctx, data, text, image)


def _validate(ctx: Context, data: dict, text: str, image: Path | None) -> Classification:
    valid_items = {i.id: i for i in ctx.all_items}
    valid_runs = {r.id for r in ctx.pending_runs}
    t = data.get("type") if data.get("type") in TYPES else "other"
    c = Classification(type=t, confidence=float(data.get("confidence") or 0), question=data.get("question") or None)

    for it in data.get("items") or []:
        try:
            iid = int(it.get("item_id"))
        except (TypeError, ValueError):
            continue
        if iid in valid_items and valid_items[iid].kind == "consumable":
            rem = it.get("remaining")
            c.items.append({"item_id": iid, "remaining": float(rem) if isinstance(rem, (int, float)) else None})

    dev = data.get("device_id")
    if isinstance(dev, int) and dev in valid_items and valid_items[dev].kind == "device":
        c.device_id = dev
    c.issue = (data.get("issue") or "").strip() or (text or "").strip()

    run = data.get("task_run_id")
    if isinstance(run, int) and run in valid_runs:
        c.task_run_id = run

    if t == "invoice" and isinstance(data.get("invoice"), dict):
        inv = data["invoice"]
        lines = []
        for ln in inv.get("lines") or []:
            iid = ln.get("item_id")
            lines.append(
                {
                    "item_id": iid if isinstance(iid, int) and iid in valid_items else None,
                    "name": str(ln.get("name") or ""),
                    "qty": _num(ln.get("qty")),
                    "unit_price": _num(ln.get("unit_price"), None),
                }
            )
        c.invoice = {
            "supplier": str(inv.get("supplier") or ""),
            "invoice_no": str(inv.get("invoice_no") or ""),
            "total": _num(inv.get("total")),
            "date": str(inv.get("date") or ""),
            "lines": lines,
        }

    # تحقق منطقي: نوع بدون بيانات كافية = سؤال توضيحي بدل التخمين
    if t == "shortage" and not c.items and not c.question:
        c.question = "أي صنف بالضبط اللي ناقص؟"
    if t == "issue" and not c.device_id and not c.question:
        c.question = "أي جهاز بالضبط؟"
    if t == "task_proof" and not c.task_run_id:
        if len(ctx.pending_runs) == 1:
            c.task_run_id = ctx.pending_runs[0].id
        elif ctx.pending_runs and not c.question:
            c.question = "هذي الصورة لأي مهمة؟ " + " / ".join(r.task.title for r in ctx.pending_runs[:3])
    return c


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------- rules path
def _best_items(query: str, items: list[Item], threshold: float = 0.6) -> list[tuple[float, Item]]:
    scored = sorted(((tn.score(query, i.name, i.aliases), i) for i in items), key=lambda x: -x[0])
    return [(s, i) for s, i in scored if s >= threshold]


def _classify_rules(ctx: Context, text: str, image: Path | None) -> Classification:
    text = text or ""
    is_cleaner = bool(ctx.pending_runs) or any("نظاف" in s.name for s in ctx.staff.sections)

    # 1) فاتورة
    if tn.contains_any(text, tn.INVOICE_WORDS) and (image or "فاتور" in tn.normalize(text)):
        return Classification(type="invoice", invoice=None, confidence=0.7)

    # 2) عطل جهاز
    devices = [i for i in ctx.all_items if i.kind == "device"]
    if tn.contains_any(text, tn.ISSUE_WORDS):
        own_devices = [i for i in ctx.own_items if i.kind == "device"]
        best = _best_items(text, own_devices, 0.4) or _best_items(text, devices, 0.4)
        if best:
            top_score = best[0][0]
            tied = [i for s, i in best if s >= top_score - 0.01]
            if len(tied) == 1:
                return Classification(type="issue", device_id=tied[0].id, issue=text.strip(), confidence=top_score)
            names = " / ".join(i.name for i in tied[:4])
            return Classification(type="issue", issue=text.strip(), question=f"أي واحد بالضبط؟ {names}")
        return Classification(type="issue", issue=text.strip(), question="أي جهاز بالضبط اللي فيه المشكلة؟")

    # 3) إثبات مهمة: صورة من عاملة النظافة وعندها مهام معلقة
    if image and ctx.pending_runs and (is_cleaner or tn.contains_any(text, tn.PROOF_WORDS)):
        run = None
        if text:
            scored = sorted(
                ((tn.score(text, r.task.title, r.task.aliases), r) for r in ctx.pending_runs), key=lambda x: -x[0]
            )
            if scored and scored[0][0] >= 0.6:
                run = scored[0][1]
        if not run:
            # بدون نص: أول مهمة معلقة في القائمة
            run = ctx.pending_runs[0]
        return Classification(type="task_proof", task_run_id=run.id, confidence=0.6)

    # 4) نقص
    consumables_own = [i for i in ctx.own_items if i.kind == "consumable"]
    consumables_all = [i for i in ctx.all_items if i.kind == "consumable"]
    if tn.contains_any(text, tn.SHORTAGE_WORDS) or (image and not ctx.pending_runs):
        if not text.strip():
            return Classification(
                type="shortage", question="وش هذي الصورة؟ إذا فاتورة استلام اكتبي «فاتورة»، وإذا صنف ناقص اكتبي اسمه"
            )
        best = _best_items(text, consumables_own) or _best_items(text, consumables_all)
        if best:
            top = best[0][0]
            tied = [i for s, i in best if s >= top - 0.01]
            if len(tied) > 1:
                names = " / ".join(i.name for i in tied[:4])
                return Classification(type="shortage", question=f"أي واحد تقصدين؟ {names}")
            remaining = tn.extract_remaining(text)
            return Classification(
                type="shortage", items=[{"item_id": tied[0].id, "remaining": remaining}], confidence=top
            )
        hint = " / ".join(i.name for i in consumables_own[:4])
        q = "ما عرفت الصنف، وش اسمه بالضبط؟" + (f" مثلاً: {hint}" if hint else "")
        return Classification(type="shortage", question=q)

    return Classification(type="other")
