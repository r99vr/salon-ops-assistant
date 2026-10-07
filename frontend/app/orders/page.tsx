"use client";

import { useState } from "react";
import { api, refreshAll, useApi } from "@/lib/api";
import { ORDER_STATUS, money, num, relative, shortDate, time } from "@/lib/format";
import type { Invoice, Order } from "@/lib/types";
import { Button, Empty, PageHeader, Pill, SectionTitle, Thumb, useLightbox, useToast } from "@/components/ui";

type Data = { drafts: Order[]; orders: Order[]; invoices: Invoice[]; summary_time: string };

const EXTRACTION: Record<string, string> = {
  ai: "قرأها المساعد من الصورة",
  matched: "طابقها المساعد مع الطلبية",
  pending: "تحتاج مراجعة",
  manual: "إدخال يدوي",
};

export default function Orders() {
  const { data } = useApi<Data>("/api/orders", 6000);
  const lb = useLightbox();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  if (!data) return <div className="py-24 text-center text-ink-mute">جاري التحميل…</div>;

  const awaiting = data.orders.filter((o) => o.status === "awaiting_approval");
  const tonight = [...awaiting, ...data.drafts];
  const moving = data.orders.filter((o) => o.status === "sent" || o.status === "confirmed");
  const done = data.orders.filter((o) => o.status === "received" || o.status === "cancelled");

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

  return (
    <>
      <PageHeader
        title="الطلبيات"
        sub={`النواقص تتجمع طول اليوم، والساعة ${data.summary_time} يوصلك ملخص واحد بالواتساب. ما ينرسل شي للمندوب إلا بعد موافقتك.`}
      />

      <section>
        <SectionTitle aside={awaiting.length ? "بانتظار موافقتك" : `الملخص الساعة ${data.summary_time}`}>طلبية الليلة</SectionTitle>
        {tonight.length === 0 ? (
          <Empty title="ما فيه أصناف للطلب">الأصناف اللي تنزل تحت الحد الأدنى تنضاف هنا تلقائياً.</Empty>
        ) : (
          <div className="rounded-3xl bg-surface p-5 sm:p-6 ring-1 ring-line">
            <div className="grid gap-6 md:grid-cols-2">
              {tonight.map((o) => (
                <div key={o.id}>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <div className="text-[16px] font-medium">{o.supplier.name}</div>
                      <div className="text-[12.5px] text-ink-mute">المندوب: {o.supplier.rep_name}</div>
                    </div>
                    <Pill tone={o.status === "awaiting_approval" ? "plum" : "mute"}>{ORDER_STATUS[o.status]}</Pill>
                  </div>
                  <ul className="divide-y divide-line">
                    {o.lines.map((l) => (
                      <LineEdit key={l.id} line={l} />
                    ))}
                  </ul>
                  <div className="mt-2 text-[13px] text-ink-mute">التقدير: {money(o.estimated_total)} ريال</div>
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
              <p className="max-w-xl text-[13.5px] text-ink-soft">
                تقدرين تعدلين الكميات هنا أو بالواتساب، مثلاً «الصبغة البنية 8» أو «شيل زيت المساج». الكمية صفر تشيل الصنف.
              </p>
              {awaiting.length > 0 ? (
                <Button onClick={approve} busy={busy}>
                  موافقة وإرسال للمندوب
                </Button>
              ) : (
                <Pill>تنتظر ملخص {data.summary_time}</Pill>
              )}
            </div>
          </div>
        )}
      </section>

      <section className="mt-12">
        <SectionTitle>عند المناديب</SectionTitle>
        {moving.length === 0 ? (
          <Empty title="ما فيه طلبيات بالطريق" />
        ) : (
          <div className="space-y-4">
            {moving.map((o) => (
              <div key={o.id} className="rounded-2xl bg-surface p-5 ring-1 ring-line">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-[16px] font-medium">
                      {o.supplier.name} <span className="text-[13px] font-normal text-ink-mute">#{o.id}</span>
                    </div>
                    <div className="text-[13px] text-ink-soft">{o.lines.map((l) => `${l.name} × ${num(l.qty)}`).join("، ")}</div>
                  </div>
                  <Steps o={o} />
                </div>
                {o.supplier_reply && (
                  <div className="mt-3 rounded-xl bg-sage-wash/70 px-4 py-2.5 text-[14px]">
                    رد {o.supplier.rep_name}: «{o.supplier_reply}» <span className="text-[12px] text-ink-mute">{relative(o.supplier_replied_at)}</span>
                  </div>
                )}
                {!o.supplier_reply && o.reminded_at && (
                  <div className="mt-3 text-[13px] text-amber">ذكّر المساعد المندوب الساعة {time(o.reminded_at)} وما رد للحين.</div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mt-12">
        <SectionTitle aside="صورة الفاتورة من العاملة تسجّل المصروف وتضيف الأصناف للمخزون">الفواتير</SectionTitle>
        {data.invoices.length === 0 ? (
          <Empty title="ما فيه فواتير بعد" />
        ) : (
          <div className="overflow-x-auto rounded-2xl bg-surface ring-1 ring-line">
            <table className="w-full min-w-[640px] text-[14px]">
              <thead>
                <tr className="border-b border-line text-right text-[12.5px] text-ink-mute">
                  <th className="px-5 py-2.5 font-normal">المورد</th>
                  <th className="px-3 py-2.5 font-normal">التاريخ</th>
                  <th className="px-3 py-2.5 font-normal">الأصناف</th>
                  <th className="px-3 py-2.5 font-normal">المبلغ</th>
                  <th className="px-3 py-2.5 font-normal">المصدر</th>
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.invoices.map((i) => (
                  <tr key={i.id}>
                    <td className="px-5 py-3">
                      <div>{i.supplier || "غير معروف"}</div>
                      <div className="text-[12px] text-ink-mute">
                        {i.invoice_no || `#${i.id}`}
                        {i.uploaded_by ? `، صورتها ${i.uploaded_by}` : ""}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-ink-soft">{shortDate(i.date)}</td>
                    <td className="px-3 py-3 text-[13px] text-ink-soft">{i.lines.length} أصناف</td>
                    <td className="px-3 py-3 font-semibold">{money(i.total)} ريال</td>
                    <td className="px-3 py-3">
                      <Pill tone={i.extraction === "pending" ? "amber" : "mute"}>{EXTRACTION[i.extraction] ?? i.extraction}</Pill>
                    </td>
                    <td className="px-5 py-3">{i.image_url ? <Thumb src={i.image_url} alt={`فاتورة ${i.supplier}`} size={40} onOpen={lb.open} /> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {done.length > 0 && (
        <section className="mt-12">
          <SectionTitle>السجل</SectionTitle>
          <ul className="divide-y divide-line text-[14px]">
            {done.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <span>
                  {o.supplier.name} <span className="text-ink-mute">#{o.id}</span>
                </span>
                <span className="text-ink-mute">{o.lines.length} أصناف، {money(o.estimated_total)} ريال تقديراً</span>
                <span className="flex items-center gap-2">
                  <Pill tone={o.status === "received" ? "sage" : "mute"}>{ORDER_STATUS[o.status]}</Pill>
                  <span className="text-[12.5px] text-ink-mute">{shortDate(o.received_at ?? o.created_at)}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {lb.node}
      {toast.node}
    </>
  );
}

function LineEdit({ line }: { line: Order["lines"][number] }) {
  const [qty, setQty] = useState(String(line.qty));
  const save = async () => {
    const n = Number(qty);
    if (Number.isNaN(n) || n === line.qty) return;
    await api(`/api/order-lines/${line.id}`, "PATCH", { qty: n });
    refreshAll();
  };
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <span className="text-[14.5px]">{line.name}</span>
      <span className="flex items-center gap-2 text-[13px] text-ink-mute">
        <input
          type="number"
          min={0}
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => e.key === "Enter" && (e.currentTarget as HTMLInputElement).blur()}
          className="w-16 rounded-lg bg-paper px-2 py-1 text-center text-[14.5px] text-ink ring-1 ring-line outline-none focus:ring-plum"
          aria-label={`كمية ${line.name}`}
        />
        {line.unit}
      </span>
    </li>
  );
}

function Steps({ o }: { o: Order }) {
  const steps = [
    { k: "sent", t: "أُرسلت", at: o.sent_at },
    { k: "confirmed", t: "أكدها المندوب", at: o.supplier_replied_at },
    { k: "received", t: "استُلمت", at: o.received_at },
  ];
  const reached = (k: string) =>
    ({ sent: ["sent", "confirmed", "received"], confirmed: ["confirmed", "received"], received: ["received"] })[k]!.includes(o.status);
  return (
    <ol className="flex items-center gap-2 text-[12.5px]" aria-label="مراحل الطلبية">
      {steps.map((s, i) => (
        <li key={s.k} className="flex items-center gap-2">
          {i > 0 && <span className={`h-px w-6 ${reached(s.k) ? "bg-sage" : "bg-line-strong"}`} />}
          <span className={`flex items-center gap-1.5 ${reached(s.k) ? "text-sage" : "text-ink-mute"}`}>
            <span className={`size-2.5 rounded-full ${reached(s.k) ? "bg-sage" : "bg-line-strong"}`} />
            {s.t}
            {s.at && reached(s.k) && <span className="text-ink-mute">{time(s.at)}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
