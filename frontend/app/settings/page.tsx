"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Copy, QrCode, X } from "lucide-react";
import { api, refreshAll, useApi } from "@/lib/api";
import type { Salon, Staff, Supplier } from "@/lib/types";
import { Avatar, Button, PageHeader, Pill, SectionTitle, useToast } from "@/components/ui";

type SettingsData = {
  salon: Salon;
  staff: Staff[];
  sections: { id: number; name: string; staff_id: number | null; items: number }[];
  suppliers: Supplier[];
  channels: { ai: boolean; ai_model: string | null; telegram: boolean; telegram_bot: string | null; whatsapp: boolean };
};

const ROLE: Record<Staff["role"], string> = { owner: "صاحبة الصالون", manager: "مديرة", worker: "عاملة" };

export default function Settings() {
  const { data } = useApi<SettingsData>("/api/settings");
  const toast = useToast();
  const [invite, setInvite] = useState<{ name: string; link: string } | null>(null);
  if (!data) return <div className="py-24 text-center text-ink-mute">جاري التحميل…</div>;
  const { salon, channels } = data;

  const patch = async (body: Partial<Salon>, msg = "انحفظ") => {
    try {
      await api("/api/settings", "PATCH", body);
      toast.ok(msg);
      refreshAll();
    } catch (e) {
      toast.err((e as Error).message);
    }
  };

  const channelOpts = [
    { k: "simulator", t: "المحاكي فقط", d: "كل الرسائل داخل اللوحة. مناسب للعرض والفيديو.", ready: true },
    {
      k: "telegram",
      t: "تيليجرام",
      d: channels.telegram ? `البوت @${channels.telegram_bot ?? "…"} جاهز. كل شخص يربط حسابه برابط دعوته.` : "أضف TELEGRAM_BOT_TOKEN في ملف .env للخلفية.",
      ready: channels.telegram,
    },
    {
      k: "whatsapp",
      t: "واتساب",
      d: channels.whatsapp ? "WhatsApp Cloud API جاهز." : "جاهز في الكود، ويتفعّل مع عميل حقيقي ببيانات WhatsApp Cloud API.",
      ready: channels.whatsapp,
    },
  ] as const;

  return (
    <>
      <PageHeader title="الإعدادات" sub="كل شي هنا بيانات مو كود: نفس النظام يشتغل لكوفي أو مغسلة بتغيير الأقسام والأصناف والمهام." />

      <NameField value={salon.name} onSave={(v) => patch({ name: v }, "تغيّر اسم الصالون")} />

      <div className="grid gap-12 lg:grid-cols-2">
        <section>
          <SectionTitle>قناة الرسائل</SectionTitle>
          <div className="space-y-2" role="radiogroup" aria-label="قناة الرسائل">
            {channelOpts.map((c) => (
              <button
                key={c.k}
                role="radio"
                aria-checked={salon.channel === c.k}
                disabled={!c.ready}
                onClick={() => patch({ channel: c.k }, `القناة الحين: ${c.t}`)}
                className={`flex w-full items-start gap-3 rounded-2xl px-4 py-3 text-right ring-1 transition-colors disabled:cursor-not-allowed ${
                  salon.channel === c.k ? "bg-plum-wash ring-plum/50" : "bg-surface ring-line hover:ring-plum/40"
                } ${c.ready ? "" : "opacity-60"}`}
              >
                <span className={`mt-1 grid size-4 shrink-0 place-items-center rounded-full ring-2 ${salon.channel === c.k ? "ring-plum" : "ring-line-strong"}`}>
                  {salon.channel === c.k && <span className="size-2 rounded-full bg-plum" />}
                </span>
                <span>
                  <span className="flex items-center gap-2 text-[15px] font-medium">
                    {c.t}
                    {!c.ready && <Pill>غير مفعّل</Pill>}
                  </span>
                  <span className="mt-0.5 block text-[13px] text-ink-soft">{c.d}</span>
                </span>
              </button>
            ))}
          </div>
          <p className="mt-3 text-[12.5px] text-ink-mute">
            الرد على أي رسالة يرجع لنفس القناة اللي جت منها. الرسائل اللي يبدأها المساعد (الملخص، التقرير، رسالة المندوب) تروح للقناة المختارة، وتظهر في المحاكي دائماً.
          </p>

          <div className="mt-6 rounded-2xl bg-surface px-4 py-3 ring-1 ring-line text-[14px]">
            <div className="font-medium">فهم الرسائل والصور</div>
            <div className="mt-0.5 text-[13px] text-ink-soft">
              {channels.ai ? (
                <>
                  نموذج <span dir="ltr">{channels.ai_model}</span> عبر OpenRouter يقرأ النصوص والصور والفواتير.
                </>
              ) : (
                "قواعد نصية بسيطة بدون ذكاء اصطناعي. أضف OPENROUTER_API_KEY عشان يقرأ الصور والفواتير."
              )}
            </div>
          </div>
        </section>

        <section>
          <SectionTitle>الموافقات والأوقات</SectionTitle>
          <div className="mb-5 flex gap-2" role="radiogroup" aria-label="من يوافق على الطلبيات">
            {(["owner", "manager"] as const).map((r) => (
              <button
                key={r}
                role="radio"
                aria-checked={salon.approver === r}
                onClick={() => patch({ approver: r }, r === "owner" ? "الموافقات تروح لصاحبة الصالون" : "الموافقات تروح للمديرة")}
                className={`flex-1 rounded-xl px-4 py-2.5 text-[14px] ring-1 ${salon.approver === r ? "bg-ink text-white ring-ink" : "bg-surface ring-line"}`}
              >
                {r === "owner" ? "صاحبة الصالون توافق" : "المديرة توافق"}
              </button>
            ))}
          </div>
          <div className="divide-y divide-line rounded-2xl bg-surface ring-1 ring-line">
            <TimeRow label="تقرير الصباح" hint="رسالة وحدة فيها النواقص والمهام والأعطال والمصاريف" value={salon.morning_time} onSave={(v) => patch({ morning_time: v })} />
            <TimeRow label="قائمة النظافة اليومية" hint="تنرسل لعاملة النظافة" value={salon.tasks_time} onSave={(v) => patch({ tasks_time: v })} />
            <TimeRow label="مراجعة مهام النظافة" hint="يذكّر العاملة باللي باقي من القائمة" value={salon.tasks_check_time} onSave={(v) => patch({ tasks_check_time: v })} />
            <TimeRow label="ملخص الطلبية" hint="للموافقة قبل ما تروح للمندوب" value={salon.summary_time} onSave={(v) => patch({ summary_time: v })} />
            <NumRow label="تذكير المندوب بعد" unit="دقيقة" value={salon.supplier_reminder_minutes} onSave={(v) => patch({ supplier_reminder_minutes: v })} />
            <NumRow label="مهلة بعد المراجعة قبل تبليغك" unit="دقيقة" value={salon.cleaning_grace_minutes} onSave={(v) => patch({ cleaning_grace_minutes: v })} />
          </div>
        </section>
      </div>

      <section className="mt-12">
        <SectionTitle aside={channels.telegram ? "كل شخص يفتح رابطه مرة وحدة من جواله" : undefined}>الفريق</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.staff.map((s) => (
            <div key={s.id} className="flex items-start gap-3 rounded-2xl bg-surface p-4 ring-1 ring-line">
              <Avatar name={s.name} color={s.color} size={42} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[15.5px] font-medium">{s.name}</span>
                  <span className="text-[12.5px] text-ink-mute">{ROLE[s.role]}</span>
                </div>
                <div className="text-[13px] text-ink-soft">{s.title}</div>
                {s.sections.length > 0 && <div className="mt-0.5 text-[12.5px] text-ink-mute">قسم {s.sections.join("، ")}</div>}
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[12px] text-ink-mute" dir="ltr">
                    +{s.phone}
                  </span>
                  {channels.telegram &&
                    (s.telegram_linked ? (
                      <Pill tone="sage">مربوطة بتيليجرام</Pill>
                    ) : (
                      s.invite_link && (
                        <button onClick={() => setInvite({ name: s.name, link: s.invite_link! })} className="inline-flex items-center gap-1 text-[12.5px] text-plum hover:underline">
                          <QrCode size={14} /> رابط الدعوة
                        </button>
                      )
                    ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12">
        <SectionTitle>الموردين</SectionTitle>
        <ul className="divide-y divide-line rounded-2xl bg-surface ring-1 ring-line">
          {data.suppliers.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-3.5">
              <div className="min-w-[220px] flex-1">
                <div className="text-[15px] font-medium">{s.name}</div>
                <div className="text-[12.5px] text-ink-mute">{s.category}</div>
              </div>
              <div className="text-[13.5px] text-ink-soft">
                المندوب: {s.rep_name} <span dir="ltr" className="text-ink-mute">+{s.rep_phone}</span>
              </div>
              {channels.telegram &&
                (s.telegram_linked ? (
                  <Pill tone="sage">مربوط بتيليجرام</Pill>
                ) : (
                  s.invite_link && (
                    <button onClick={() => setInvite({ name: s.rep_name, link: s.invite_link! })} className="inline-flex items-center gap-1 text-[13px] text-plum hover:underline">
                      <QrCode size={14} /> رابط الدعوة
                    </button>
                  )
                ))}
            </li>
          ))}
        </ul>
      </section>

      {invite && <InviteModal {...invite} onClose={() => setInvite(null)} onCopied={() => toast.ok("نُسخ الرابط")} />}
      {toast.node}
    </>
  );
}

function NameField({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  const save = () => v.trim() && v.trim() !== value && onSave(v.trim());
  return (
    <section className="mb-10 max-w-xl">
      <label htmlFor="salon-name" className="mb-1.5 block text-[14.5px] font-medium">
        اسم الصالون
      </label>
      <input
        id="salon-name"
        value={v}
        onChange={(e) => setV(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => e.key === "Enter" && (e.currentTarget as HTMLInputElement).blur()}
        className="w-full rounded-xl bg-surface px-4 py-2.5 font-display text-[20px] text-plum ring-1 ring-line outline-none focus:ring-plum"
      />
      <p className="mt-1.5 text-[12.5px] text-ink-mute">يظهر في اللوحة وفي رسائل المساعد للمناديب. غيّره لاسم صالون العميل قبل العرض.</p>
    </section>
  );
}

function TimeRow({ label, hint, value, onSave }: { label: string; hint: string; value: string; onSave: (v: string) => void }) {
  const [v, setV] = useState(value);
  return (
    <label className="flex items-center justify-between gap-4 px-4 py-3">
      <span>
        <span className="block text-[14.5px]">{label}</span>
        <span className="block text-[12.5px] text-ink-mute">{hint}</span>
      </span>
      <input type="time" value={v} onChange={(e) => setV(e.target.value)} onBlur={() => v !== value && onSave(v)} className="rounded-lg bg-paper px-2 py-1.5 text-[14px] ring-1 ring-line" />
    </label>
  );
}

function NumRow({ label, unit, value, onSave }: { label: string; unit: string; value: number; onSave: (v: number) => void }) {
  const [v, setV] = useState(String(value));
  return (
    <label className="flex items-center justify-between gap-4 px-4 py-3">
      <span className="text-[14.5px]">{label}</span>
      <span className="flex items-center gap-2 text-[13px] text-ink-mute">
        <input
          type="number"
          min={5}
          step={5}
          value={v}
          onChange={(e) => setV(e.target.value)}
          onBlur={() => Number(v) !== value && onSave(Number(v))}
          className="w-20 rounded-lg bg-paper px-2 py-1.5 text-center text-[14px] text-ink ring-1 ring-line"
        />
        {unit}
      </span>
    </label>
  );
}

function InviteModal({ name, link, onClose, onCopied }: { name: string; link: string; onClose: () => void; onCopied: () => void }) {
  const [qr, setQr] = useState("");
  useEffect(() => {
    QRCode.toDataURL(link, { width: 260, margin: 1, color: { dark: "#2b1d2e", light: "#ffffff" } }).then(setQr);
  }, [link]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/60 p-4" role="dialog" aria-modal aria-label={`رابط دعوة ${name}`} onClick={onClose}>
      <div className="w-full max-w-sm rounded-3xl bg-surface p-6 text-center shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-[22px]">دعوة {name}</h2>
          <button onClick={onClose} aria-label="إغلاق" className="rounded-full p-1.5 text-ink-mute hover:bg-paper">
            <X size={20} />
          </button>
        </div>
        <p className="mt-1 text-[13.5px] text-ink-soft">تمسح الكود بكاميرا الجوال وتضغط Start في تيليجرام.</p>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {qr && <img src={qr} alt={`كود QR لدعوة ${name}`} className="mx-auto my-4 size-[220px]" />}
        <div className="flex items-center gap-2 rounded-xl bg-paper px-3 py-2 text-[12.5px]" dir="ltr">
          <span className="flex-1 truncate">{link}</span>
          <button
            onClick={() => {
              navigator.clipboard.writeText(link);
              onCopied();
            }}
            aria-label="نسخ الرابط"
            className="text-plum"
          >
            <Copy size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
