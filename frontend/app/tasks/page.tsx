"use client";

import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api, refreshAll, useApi } from "@/lib/api";
import { shortDate, time } from "@/lib/format";
import type { Run, Staff } from "@/lib/types";
import { Button, Empty, PageHeader, Pill, SectionTitle, Thumb, useLightbox, useToast } from "@/components/ui";

type Template = { id: number; title: string; due_time: string; days: string; staff_id: number | null; staff: string | null; aliases: string };
type TasksData = { date: string; runs: Run[]; templates: Template[]; history: { date: string; done: number; missed: number; total: number }[] };

// ترتيب الأسبوع السعودي (الأحد أولاً) بأرقام weekday() في بايثون
const WEEK = [
  { d: "6", l: "أحد" },
  { d: "0", l: "اثنين" },
  { d: "1", l: "ثلاثاء" },
  { d: "2", l: "أربعاء" },
  { d: "3", l: "خميس" },
  { d: "4", l: "جمعة" },
  { d: "5", l: "سبت" },
];

const STATUS: Record<Run["status"], { t: string; tone: "sage" | "alarm" | "mute" | "amber" }> = {
  done: { t: "تمت", tone: "sage" },
  overdue: { t: "متأخرة", tone: "alarm" },
  missed: { t: "فاتت", tone: "alarm" },
  pending: { t: "لم يحن وقتها", tone: "mute" },
};

export default function Tasks() {
  const { data } = useApi<TasksData>("/api/tasks", 8000);
  const { data: settings } = useApi<{ staff: Staff[] }>("/api/settings");
  const lb = useLightbox();
  const toast = useToast();
  const [editing, setEditing] = useState<Template | "new" | null>(null);

  if (!data) return <div className="py-24 text-center text-ink-mute">جاري التحميل…</div>;
  const done = data.runs.filter((r) => r.status === "done").length;

  return (
    <>
      <PageHeader
        title="مهام النظافة"
        sub="المساعد يرسل لعاملة النظافة مهامها كل صباح، وكل مهمة تنقفل بصورة. إذا فات وقتها يذكّرها، وبعد المهلة يبلغك."
      />

      <div className="grid gap-10 lg:grid-cols-[1.3fr_1fr]">
        <section>
          <SectionTitle aside={`${done} من ${data.runs.length} تمت`}>اليوم</SectionTitle>
          {data.runs.length === 0 ? (
            <Empty title="ما فيه مهام اليوم">أضف مهمة من الجدول.</Empty>
          ) : (
            <ol className="relative border-r-2 border-line pr-6 space-y-5">
              {data.runs.map((r) => (
                <li key={r.id} className="relative">
                  <span
                    className={`absolute -right-[33px] top-1.5 size-4 rounded-full ring-4 ring-paper ${
                      r.status === "done" ? "bg-sage" : r.status === "pending" ? "bg-line-strong" : "bg-alarm"
                    }`}
                  />
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[13px] text-ink-mute w-16">{time(r.due_at)}</span>
                        <span className="text-[15.5px]">{r.title}</span>
                        <Pill tone={STATUS[r.status].tone}>{STATUS[r.status].t}</Pill>
                      </div>
                      <div className="mt-1 pr-[72px] text-[12.5px] text-ink-mute space-x-3 space-x-reverse">
                        {r.done_at && <span>قُفلت {time(r.done_at)}</span>}
                        {r.reminded_at && <span>تذكير {time(r.reminded_at)}</span>}
                        {r.escalated_at && <span className="text-alarm">بُلّغت الإدارة {time(r.escalated_at)}</span>}
                        {r.staff && !r.done_at && <span>المسؤولة: {r.staff}</span>}
                      </div>
                    </div>
                    {r.proof_url ? (
                      <Thumb src={r.proof_url} alt={`إثبات ${r.title}`} size={52} onOpen={lb.open} />
                    ) : r.status !== "done" ? (
                      <Button
                        variant="quiet"
                        className="px-3 py-1.5 text-[13px]"
                        onClick={async () => {
                          await api(`/api/task-runs/${r.id}/done`);
                          refreshAll();
                        }}
                      >
                        قفلها يدوياً
                      </Button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          )}

          <div className="mt-10">
            <SectionTitle>آخر أسبوعين</SectionTitle>
            <div className="flex items-end gap-1.5" role="img" aria-label="المهام المنجزة والفائتة لآخر 14 يوم">
              {data.history.map((h) => (
                <div key={h.date} className="flex-1" title={`${shortDate(h.date)}: ${h.done} تمت، ${h.missed} فاتت`}>
                  <div className="flex h-24 flex-col justify-end gap-0.5">
                    {h.missed > 0 && <div className="rounded-sm bg-alarm/70" style={{ height: `${(h.missed / Math.max(h.total, 1)) * 96}px` }} />}
                    <div className="rounded-sm bg-sage/70" style={{ height: `${(h.done / Math.max(h.total, 1)) * 96}px` }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 flex gap-4 text-[12px] text-ink-mute">
              <span className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-sm bg-sage/70" /> تمت
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-sm bg-alarm/70" /> فاتت
              </span>
            </div>
          </div>
        </section>

        <section>
          <SectionTitle
            aside={
              <Button variant="ghost" className="px-2 py-1 text-[13.5px]" onClick={() => setEditing("new")}>
                <Plus size={15} /> مهمة جديدة
              </Button>
            }
          >
            الجدول
          </SectionTitle>
          {editing === "new" && <TemplateForm staff={settings?.staff ?? []} onClose={() => setEditing(null)} onSaved={() => toast.ok("أُضيفت المهمة")} />}
          <ul className="divide-y divide-line rounded-2xl bg-surface ring-1 ring-line">
            {data.templates.map((t) =>
              editing !== "new" && editing?.id === t.id ? (
                <li key={t.id} className="p-3">
                  <TemplateForm initial={t} staff={settings?.staff ?? []} onClose={() => setEditing(null)} onSaved={() => toast.ok("حُفظ التعديل")} />
                </li>
              ) : (
                <li key={t.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="w-14 text-[13.5px] font-medium text-plum">{t.due_time}</span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[14.5px]">{t.title}</div>
                    <div className="text-[12px] text-ink-mute">
                      {t.days.length === 7 ? "كل يوم" : WEEK.filter((w) => t.days.includes(w.d)).map((w) => w.l).join("، ")}
                      {t.staff ? `، ${t.staff}` : ""}
                    </div>
                  </div>
                  <button onClick={() => setEditing(t)} aria-label={`تعديل ${t.title}`} className="grid size-8 place-items-center rounded-lg text-ink-mute hover:bg-paper hover:text-plum">
                    <Pencil size={15} />
                  </button>
                  <button
                    onClick={async () => {
                      if (!confirm(`حذف «${t.title}» من الجدول؟`)) return;
                      await api(`/api/tasks/${t.id}`, "DELETE");
                      refreshAll();
                    }}
                    aria-label={`حذف ${t.title}`}
                    className="grid size-8 place-items-center rounded-lg text-ink-mute hover:bg-alarm-wash hover:text-alarm"
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ),
            )}
          </ul>
        </section>
      </div>
      {lb.node}
      {toast.node}
    </>
  );
}

function TemplateForm({ initial, staff, onClose, onSaved }: { initial?: Template; staff: Staff[]; onClose: () => void; onSaved: () => void }) {
  const cleaner = staff.find((s) => s.sections.some((x) => x.includes("نظاف")));
  const [title, setTitle] = useState(initial?.title ?? "");
  const [due, setDue] = useState(initial?.due_time ?? "12:00");
  const [days, setDays] = useState(initial?.days ?? "0123456");
  const [staffId, setStaffId] = useState<number | null>(initial?.staff_id ?? cleaner?.id ?? null);
  const [busy, setBusy] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    const body = { title: title.trim(), due_time: due, days, staff_id: staffId, aliases: initial?.aliases ?? "" };
    if (initial) await api(`/api/tasks/${initial.id}`, "PATCH", body);
    else await api("/api/tasks", "POST", body);
    setBusy(false);
    onSaved();
    onClose();
    refreshAll();
  };

  return (
    <form onSubmit={save} className="mb-3 space-y-3 rounded-2xl bg-plum-wash/50 p-4">
      <div className="grid grid-cols-[1fr_110px] gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="اسم المهمة، مثل: تعقيم أحواض الغسيل"
          className="rounded-lg bg-surface px-3 py-2 text-[14.5px] ring-1 ring-line outline-none focus:ring-plum"
          aria-label="اسم المهمة"
          autoFocus
        />
        <input type="time" value={due} onChange={(e) => setDue(e.target.value)} className="rounded-lg bg-surface px-2 py-2 text-[14px] ring-1 ring-line" aria-label="الوقت" />
      </div>
      <div className="flex flex-wrap gap-1.5">
        {WEEK.map((w) => {
          const on = days.includes(w.d);
          return (
            <button
              type="button"
              key={w.d}
              aria-pressed={on}
              onClick={() => setDays(on ? days.replace(w.d, "") : [...days, w.d].sort().join(""))}
              className={`rounded-full px-3 py-1 text-[12.5px] ${on ? "bg-plum text-white" : "bg-surface text-ink-soft ring-1 ring-line"}`}
            >
              {w.l}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <select
          value={staffId ?? ""}
          onChange={(e) => setStaffId(e.target.value ? Number(e.target.value) : null)}
          className="rounded-lg bg-surface px-3 py-2 text-[14px] ring-1 ring-line"
          aria-label="المسؤولة"
        >
          {staff
            .filter((s) => s.role === "worker")
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.title})
              </option>
            ))}
        </select>
        <div className="flex gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            إلغاء
          </Button>
          <Button type="submit" busy={busy}>
            {initial ? "حفظ التعديل" : "إضافة المهمة"}
          </Button>
        </div>
      </div>
    </form>
  );
}
