"""جداول قاعدة البيانات.

قاعدة التصميم: كل شي خاص بالصالون (الأقسام، الأصناف، المهام، الأدوار) بيانات مو كود،
عشان نفس النواة تشتغل لكوفي أو مغسلة أو أي متجر.
"""
import secrets
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, now


class Salon(Base):
    __tablename__ = "salon"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    business_type: Mapped[str] = mapped_column(String(40), default="salon")
    # owner = الموافقات تروح لصاحبة الصالون، manager = تروح للمديرة
    approver: Mapped[str] = mapped_column(String(20), default="owner")
    summary_time: Mapped[time] = mapped_column(Time, default=time(20, 0))
    morning_time: Mapped[time] = mapped_column(Time, default=time(8, 0))
    tasks_time: Mapped[time] = mapped_column(Time, default=time(9, 0))
    supplier_reminder_minutes: Mapped[int] = mapped_column(Integer, default=120)
    # مهام النظافة قائمة بدون أوقات: وقت واحد يراجع فيه المساعد اللي ما خلص، ثم مهلة قبل تبليغ الإدارة
    tasks_check_time: Mapped[time] = mapped_column(Time, default=time(18, 0))
    cleaning_grace_minutes: Mapped[int] = mapped_column(Integer, default=60)
    currency: Mapped[str] = mapped_column(String(10), default="ريال")
    # القناة الحية: simulator / telegram / whatsapp
    channel: Mapped[str] = mapped_column(String(20), default="simulator")


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salon.id"))
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    # owner / manager / worker
    role: Mapped[str] = mapped_column(String(20), default="worker")
    title: Mapped[str] = mapped_column(String(80), default="")
    color: Mapped[str] = mapped_column(String(20), default="rose")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # ربط تيليجرام: كود دعوة يُفتح برابط t.me/<bot>?start=<code>، وبعدها نحفظ رقم المحادثة
    invite_code: Mapped[str] = mapped_column(String(40), unique=True, default=lambda: secrets.token_urlsafe(6))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)

    sections: Mapped[list["Section"]] = relationship(back_populates="staff")


class Section(Base):
    __tablename__ = "section"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salon.id"))
    name: Mapped[str] = mapped_column(String(80))
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    icon: Mapped[str] = mapped_column(String(30), default="sparkles")
    sort: Mapped[int] = mapped_column(Integer, default=0)

    staff: Mapped["Staff | None"] = relationship(back_populates="sections")
    items: Mapped[list["Item"]] = relationship(back_populates="section", order_by="Item.id")


class Supplier(Base):
    __tablename__ = "supplier"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salon.id"))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(120), default="")
    rep_name: Mapped[str] = mapped_column(String(80))
    rep_phone: Mapped[str] = mapped_column(String(20), unique=True)
    aliases: Mapped[str] = mapped_column(Text, default="")
    # ربط تيليجرام: كود دعوة يُفتح برابط t.me/<bot>?start=<code>، وبعدها نحفظ رقم المحادثة
    invite_code: Mapped[str] = mapped_column(String(40), unique=True, default=lambda: secrets.token_urlsafe(6))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)


class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("section.id"))
    name: Mapped[str] = mapped_column(String(120))
    # أسماء ثانية تستخدمها العاملات (مفصولة بفاصلة)
    aliases: Mapped[str] = mapped_column(Text, default="")
    # consumable = مستهلك (كمية وحد أدنى) / device = جهاز (حالة وأعطال)
    kind: Mapped[str] = mapped_column(String(20), default="consumable")
    unit: Mapped[str] = mapped_column(String(30), default="حبة")
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    min_qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    target_qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("supplier.id"), nullable=True)
    # للأجهزة: ok / broken
    status: Mapped[str] = mapped_column(String(20), default="ok")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    section: Mapped["Section"] = relationship(back_populates="items")
    supplier: Mapped["Supplier | None"] = relationship()

    @property
    def is_low(self) -> bool:
        return self.kind == "consumable" and self.quantity < self.min_qty


class StockEvent(Base):
    __tablename__ = "stock_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    delta: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    qty_after: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # message / invoice / manual / seed
    source: Mapped[str] = mapped_column(String(20))
    message_id: Mapped[int | None] = mapped_column(ForeignKey("message.id"), nullable=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    item: Mapped["Item"] = relationship()
    staff: Mapped["Staff | None"] = relationship()


class DeviceIssue(Base):
    __tablename__ = "device_issue"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # open / resolved
    status: Mapped[str] = mapped_column(String(20), default="open")
    message_id: Mapped[int | None] = mapped_column(ForeignKey("message.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    item: Mapped["Item"] = relationship()
    reporter: Mapped["Staff | None"] = relationship()


class CleaningTask(Base):
    __tablename__ = "cleaning_task"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salon.id"))
    title: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[str] = mapped_column(Text, default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    # أيام التنفيذ بصيغة أرقام weekday() في بايثون (0=الاثنين ... 6=الأحد)
    days: Mapped[str] = mapped_column(String(20), default="0123456")
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    requires_photo: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    staff: Mapped["Staff | None"] = relationship()


class TaskRun(Base):
    __tablename__ = "task_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("cleaning_task.id"))
    run_date: Mapped[date] = mapped_column(Date, index=True)
    # pending / done / missed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    proof_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("message.id"), nullable=True)

    task: Mapped["CleaningTask"] = relationship()


class Order(Base):
    __tablename__ = "purchase_order"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salon.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"))
    order_date: Mapped[date] = mapped_column(Date)
    # draft → awaiting_approval → sent → confirmed → received  (أو cancelled)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supplier_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    supplier: Mapped["Supplier"] = relationship()
    lines: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )

    @property
    def estimated_total(self) -> Decimal:
        return sum((l.qty * (l.item.unit_price or 0) for l in self.lines), Decimal(0))


class OrderItem(Base):
    __tablename__ = "order_item"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_order.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped["Order"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()


class Invoice(Base):
    __tablename__ = "invoice"
    id: Mapped[int] = mapped_column(primary_key=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey("salon.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("supplier.id"), nullable=True)
    supplier_name: Mapped[str] = mapped_column(String(120), default="")
    invoice_no: Mapped[str] = mapped_column(String(60), default="")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    invoice_date: Mapped[date] = mapped_column(Date)
    image_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_order.id"), nullable=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("message.id"), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    # ai = استخرجها النموذج، matched = طابقناها مع طلبية مفتوحة، manual
    extraction: Mapped[str] = mapped_column(String(20), default="ai")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    supplier: Mapped["Supplier | None"] = relationship()
    uploader: Mapped["Staff | None"] = relationship()


class Message(Base):
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    # staff / owner / manager / supplier / unknown
    contact_role: Mapped[str] = mapped_column(String(20), default="unknown")
    direction: Mapped[str] = mapped_column(String(5))  # in / out
    body: Mapped[str] = mapped_column(Text, default="")
    media_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # للوارد: shortage / task_proof / issue / invoice / owner_command / supplier_reply / other
    # للصادر: reply / question / summary / order / reminder / alert / report / tasks
    kind: Mapped[str] = mapped_column(String(30), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    # القناة اللي جت منها أو راحت لها: simulator / telegram / whatsapp
    channel: Mapped[str] = mapped_column(String(20), default="simulator")
    # simulator / sent / failed / received
    transport: Mapped[str] = mapped_column(String(20), default="simulator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class ConversationState(Base):
    """حالة المحادثة لكل رقم — مثلاً لما المساعد يسأل سؤال توضيحي وينتظر الرد."""

    __tablename__ = "conversation_state"
    phone: Mapped[str] = mapped_column(String(20), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class JobLog(Base):
    """سجل المهام المجدولة اليومية عشان ما تتكرر في نفس اليوم."""

    __tablename__ = "job_log"
    job: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)


class Attendance(Base):
    """تحضير العاملات: المديرة ترسل للمساعد مين وصلت ومين طلعت."""

    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("staff_id", "work_date", name="uq_attendance_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    work_date: Mapped[date] = mapped_column(Date, index=True)
    # present / absent
    status: Mapped[str] = mapped_column(String(20), default="present")
    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("message.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    staff: Mapped["Staff"] = relationship(foreign_keys=[staff_id])
    recorder: Mapped["Staff | None"] = relationship(foreign_keys=[recorded_by])
