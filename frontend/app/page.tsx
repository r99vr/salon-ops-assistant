"use client";

import Link from "next/link";
import { useState } from "react";
import { api, refreshAll, useApi } from "@/lib/api";
import { ORDER_STATUS, clock12, dayLabel, money, num, relative, shortDate } from "@/lib/format";
import type { Overview } from "@/lib/types";
import DayRibbon from "@/components/DayRibbon";
import { AttendanceToday, attendanceCounts } from "@/components/Attendance";
import { Button, Empty, LevelBar, Pill, SectionTitle, count, useLightbox, useToast } from "@/components/ui";

export default function Home() {
  const { data, error } = useApi<Overview>("/api/overview", 8000);
  const lb = useLightbox();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  if (error) return <BackendDown message={error.message} />;
  if (!data) return <div className="py-24 text-center text-ink-mute">جاري التحميل…</div>;

  const { stats, salon } = data;
  const overdue = data.today_tasks.filter((r) => r.status === "overdue").length;
  const awaiting = data.open_orders.filter((o) => o.status === "awaiting_approval");
  const drafts = data.open_orders.filter((o) => o.status === "draft");
  const tonight = [...awaiting, ...drafts];
  const inTransit = data.open_orders.filter((o) => o.status === "sent" || o.status === "confirmed");

  const approve = async () => {
    setBusy(true);
    try {
      await api("/api/orders/approve", "POST", {});
      toast.ok("أُرسلت الطلبية للمندوب");
      refreshAll();
    } catch (e) {
      toast.err((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const headline = [
    stats.low_count ? `${count(stats.low_count, "صنف واحد", "صنفين", "أصناف", "صنف")} تحت الحد الأدنى` : "كل الأصناف فوق الحد الأدنى",
    stats.broken_count ? `${count(stats.broken_count, "جهاز معطل", "جهازين معطلين", "أجهزة معطلة", "جهاز معطل")}` : null,
    overdue ? `${count(overdue, "مهمة متأخرة", "مهمتين متأخرتين", "مهام متأخرة", "مهمة متأخرة")}` : null,
  ].filter(Boolean);

  return (
    <>
      <div className="mb-6">
        <h1 className="text-[34px] leading-[1.15]">{dayLabel(data.now)}</h1>
        <p className="mt-1.5 text-[15.5px] text-ink-soft">{headline.join("، ")}.</p>
      </div>

      <section className="rounded-3xl bg-surface px-5 sm:px-7 pt-5 pb-5 ring-1 ring-line" aria-labelledby="day-title">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="day-title" className="text-[21px]">يوم الصالون</h2>
          <div className="text-[13px] text-ink-mute">كل مهمة نظافة تنقفل بصورة، اضغط عليها تشوف الإثبات</div>
        </div>
        <DayRibbon runs={data.today_tasks} salon={salon} now={data.now} onOpen={lb.open} />
      </section>

      <div className="mt-10 grid gap-10 lg:grid-cols-[1.35fr_1fr]">
        <section>
          <SectionTitle aside={<Link href="/inventory" className="text-plum hover:underline">كل المخزون</Link>}>تحت الحد الأدنى</SectionTitle>
          {data.low_items.length === 0 ? (
            <Empty title="ما فيه نواقص">أول ما ترسل عاملة «خلص كذا» يظهر هنا.</Empty>
          ) : (
            <ul className="divide-y divide-line">
              {data.low_items.map((i) => (
                <li key={i.id} className="grid grid-cols-[1fr_120px] sm:grid-cols-[1fr_170px_88px] items-center gap-x-5 gap-y-1.5 py-3">
                  <div className="min-w-0">
                    <div className="truncate text-[15.5px]">{i.name}</div>
                    <div className="text-[12.5px] text-ink-mute">
                      قسم {i.section}، من {i.supplier ?? "بدون مورد"}
                    </div>
                  </div>
                  <LevelBar qty={i.quantity} min={i.min_qty} target={i.target_qty} />
                  <div className="col-span-2 sm:col-span-1 text-[13.5px] sm:text-left">
                    <b className="font-semibold text-amber">{num(i.quantity)}</b>
                    <span className="text-ink-mute"> / {num(i.min_qty)} {i.unit}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-10">
            <SectionTitle
              aside={
                <Link href="/attendance" className="text-plum hover:underline">
                  سجل الحضور
                </Link>
              }
            >
              الحضور اليوم
            </SectionTitle>
            <p className="-mt-1.5 mb-2 text-[13px] text-ink-mute">
              {(() => {
                const c = attendanceCounts(data.attendance);
                return c.arrived === 0 && c.absent === 0
                  ? "ما سجلت المديرة أحد للحين."
                  : `وصلت ${c.arrived} من ${c.total}${c.absent ? `، وغياب ${c.absent}` : ""}. تسجلها المديرة برسالة للمساعد.`;
              })()}
            </p>
            <AttendanceToday rows={data.attendance} />
          </div>
        </section>

        <section>
          <SectionTitle aside={`الملخص يوصل الساعة ${clock12(salon.summary_time)}`}>طلبية الليلة</SectionTitle>
          {tonight.length === 0 ? (
            <Empty title="ما فيه شي للطلب الليلة">الأصناف اللي تنزل تحت الحد تنضاف هنا تلقائياً.</Empty>
          ) : (
            <div className="rounded-2xl bg-plum-wash/60 p-5">
              {tonight.map((o) => (
                <div key={o.id} className="mb-4 last:mb-0">
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <div className="text-[15px] font-medium">{o.supplier.name}</div>
                    <Pill tone={o.status === "awaiting_approval" ? "plum" : "mute"}>{ORDER_STATUS[o.status]}</Pill>
                  </div>
                  <ul className="space-y-1 text-[14px] text-ink-soft">
                    {o.lines.map((l) => (
                      <li key={l.id} className="flex justify-between">
                        <span>{l.name}</span>
                        <span>
                          {num(l.qty)} {l.unit}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-plum/15 pt-4">
                <div className="text-[14px]">
                  التقدير: <b className="font-semibold">{money(tonight.reduce((s, o) => s + o.estimated_total, 0))}</b> {salon.currency}
                </div>
                {awaiting.length > 0 ? (
                  <Button onClick={approve} busy={busy}>
                    موافقة وإرسال للمندوب
                  </Button>
                ) : (
                  <span className="text-[13px] text-ink-mute">توافقين عليها من الواتساب أو من هنا بعد الملخص</span>
                )}
              </div>
            </div>
          )}

          {inTransit.length > 0 && (
            <div className="mt-6">
              <h3 className="mb-2 text-[17px]">بالطريق</h3>
              <ul className="space-y-2 text-[14px]">
                {inTransit.map((o) => (
                  <li key={o.id} className="flex items-center justify-between gap-3">
                    <span>{o.supplier.name}</span>
                    <Pill tone={o.status === "confirmed" ? "sage" : "amber"}>{ORDER_STATUS[o.status]}</Pill>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-8">
            <SectionTitle>الأجهزة</SectionTitle>
            {data.broken_devices.length === 0 ? (
              <p className="text-[14.5px] text-ink-soft">
                كل الأجهزة شغالة ({stats.devices_count} جهاز).
              </p>
            ) : (
              <ul className="space-y-3">
                {data.broken_devices.map((d) => (
                  <li key={d.id} className="rounded-xl border border-alarm/25 bg-alarm-wash/50 px-4 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <b className="font-medium">{d.name}</b>
                      <Pill tone="alarm">معطل</Pill>
                    </div>
                    {d.issue && (
                      <div className="mt-1 text-[13.5px] text-ink-soft">
                        «{d.issue.description}» — {d.issue.reported_by}، {relative(d.issue.created_at)}
                      </div>
                    )}
                    <ResolveButton id={d.id} onDone={() => toast.ok("رجع الجهاز شغال")} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>

      <div className="mt-12 grid gap-10 lg:grid-cols-2">
        <section>
          <SectionTitle aside={`هذا الشهر: ${money(stats.month_spend)} ${salon.currency}`}>المصاريف</SectionTitle>
          <SpendChart series={data.spend_series} currency={salon.currency} />
        </section>
        <section>
          <TaskWeek week={data.task_week} />
        </section>
      </div>
      {lb.node}
      {toast.node}
    </>
  );
}

function ResolveButton({ id, onDone }: { id: number; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="ghost"
      className="mt-2 -mr-3 px-3 py-1 text-[13.5px]"
      busy={busy}
      onClick={async () => {
        setBusy(true);
        await api(`/api/devices/${id}/resolve`);
        setBusy(false);
        onDone();
        refreshAll();
      }}
    >
      تم الإصلاح
    </Button>
  );
}

function SpendChart({ series, currency }: { series: { date: string; total: number }[]; currency: string }) {
  const max = Math.max(...series.map((s) => s.total), 1);
  return (
    <div>
      <div className="flex h-32 items-end gap-1.5" role="img" aria-label="مصاريف آخر 14 يوم">
        {series.map((s, i) => (
          <div key={s.date} className="group relative flex-1">
            <div
              className={`w-full rounded-t-md ${s.total ? (i === series.length - 1 ? "bg-plum" : "bg-plum/30 group-hover:bg-plum/55") : "bg-line"}`}
              style={{ height: `${s.total ? Math.max((s.total / max) * 128, 6) : 3}px` }}
            />
            {s.total > 0 && (
              <div className="pointer-events-none absolute bottom-full left-1/2 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-[11.5px] text-white opacity-0 group-hover:opacity-100">
                {shortDate(s.date)}: {money(s.total)} {currency}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex justify-between text-[11.5px] text-ink-mute">
        <span>{shortDate(series[0].date)}</span>
        <span>اليوم</span>
      </div>
    </div>
  );
}

function TaskWeek({ week }: { week: { date: string; done: number; total: number }[] }) {
  return (
    <div>
      <SectionTitle>التزام النظافة هذا الأسبوع</SectionTitle>
      <div className="flex gap-2">
        {week.map((d) => {
          const pct = d.total ? d.done / d.total : 0;
          return (
            <div key={d.date} className="flex-1 text-center">
              <div
                className="mx-auto grid size-10 place-items-center rounded-full text-[12px] font-medium"
                style={{ background: `conic-gradient(var(--color-sage) ${pct * 360}deg, var(--color-line) 0)` }}
                title={`${d.done} من ${d.total}`}
              >
                <span className="grid size-7 place-items-center rounded-full bg-paper">{d.total ? Math.round(pct * 100) : "–"}</span>
              </div>
              <div className="mt-1 text-[11px] text-ink-mute">
                {new Date(d.date).toLocaleDateString("ar-SA-u-nu-latn-ca-gregory", { weekday: "short" })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BackendDown({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-lg py-24 text-center">
      <h1 className="text-[28px]">اللوحة ما وصلت للخلفية</h1>
      <p className="mt-3 text-ink-soft">
        تأكد إن الخلفية شغالة على <code dir="ltr">{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}</code> ثم حدّث الصفحة.
      </p>
      <p className="mt-2 text-[13px] text-ink-mute" dir="ltr">
        {message}
      </p>
    </div>
  );
}
