"use client";

import { useState } from "react";
import { ChevronDown, Minus, Plus } from "lucide-react";
import { api, refreshAll, useApi } from "@/lib/api";
import { num, relative } from "@/lib/format";
import type { Item, Section } from "@/lib/types";
import { Avatar, Button, LevelBar, PageHeader, Pill, useToast } from "@/components/ui";

type Hist = { id: number; delta: number; qty_after: number; source: string; note: string; staff: string | null; created_at: string };

const SOURCE: Record<string, string> = { message: "رسالة", invoice: "فاتورة", manual: "تعديل يدوي", seed: "بداية" };

export default function Inventory() {
  const { data } = useApi<{ sections: Section[] }>("/api/inventory", 10000);
  const [filter, setFilter] = useState<number | "low" | "all">("all");
  const toast = useToast();
  const sections = data?.sections ?? [];
  const lowTotal = sections.reduce((n, s) => n + s.items.filter((i) => i.is_low).length, 0);
  const shown = typeof filter === "number" ? sections.filter((s) => s.id === filter) : sections;

  return (
    <>
      <PageHeader
        title="المخزون"
        sub="كل عاملة مسؤولة عن قسمها. الخط الصغير على الشريط هو الحد الأدنى اللي تحددينه، وأي صنف ينزل تحته ينضاف لطلبية الليلة."
      />
      <div className="mb-7 flex gap-2 overflow-x-auto scroll-thin pb-1" role="tablist">
        <Tab on={filter === "all"} onClick={() => setFilter("all")}>
          الكل
        </Tab>
        <Tab on={filter === "low"} onClick={() => setFilter("low")}>
          تحت الحد {lowTotal > 0 && <span className="text-amber">({lowTotal})</span>}
        </Tab>
        {sections.map((s) => (
          <Tab key={s.id} on={filter === s.id} onClick={() => setFilter(s.id)}>
            {s.name}
          </Tab>
        ))}
      </div>

      <div className="space-y-12">
        {shown.map((s) => {
          const items = filter === "low" ? s.items.filter((i) => i.is_low) : s.items;
          if (filter === "low" && items.length === 0) return null;
          const cons = items.filter((i) => i.kind === "consumable");
          const devs = filter === "low" ? [] : items.filter((i) => i.kind === "device");
          return (
            <section key={s.id}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-[23px]">{s.name}</h2>
                {s.staff && (
                  <div className="flex items-center gap-2 text-[13.5px] text-ink-soft">
                    <Avatar name={s.staff.name} color={s.staff.color} size={26} />
                    مسؤولة القسم: {s.staff.name}
                  </div>
                )}
              </div>
              {cons.length > 0 && (
                <div className="overflow-hidden rounded-2xl bg-surface ring-1 ring-line">
                  <div className="hidden md:grid grid-cols-[1.4fr_1.1fr_150px_120px_1fr_28px] gap-4 border-b border-line px-5 py-2.5 text-[12.5px] text-ink-mute">
                    <span>الصنف</span>
                    <span>المستوى</span>
                    <span>الكمية</span>
                    <span>الحد الأدنى</span>
                    <span>المورد</span>
                    <span />
                  </div>
                  <ul className="divide-y divide-line">
                    {cons.map((i) => (
                      <Row key={i.id} item={i} onError={toast.err} />
                    ))}
                  </ul>
                </div>
              )}
              {devs.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2.5">
                  {devs.map((d) => (
                    <Device key={d.id} d={d} onDone={() => toast.ok(`«${d.name}» رجع شغال`)} />
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>
      {toast.node}
    </>
  );
}

function Tab({ on, children, onClick }: { on: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      role="tab"
      aria-selected={on}
      onClick={onClick}
      className={`shrink-0 rounded-full px-4 py-1.5 text-[14px] ${on ? "bg-ink text-white" : "bg-surface text-ink-soft ring-1 ring-line hover:ring-plum"}`}
    >
      {children}
    </button>
  );
}

function Row({ item, onError }: { item: Item; onError: (t: string) => void }) {
  const [open, setOpen] = useState(false);
  const [min, setMin] = useState(String(item.min_qty));
  const { data: hist } = useApi<Hist[]>(open ? `/api/items/${item.id}/history` : null);

  const patch = async (body: Partial<Item>) => {
    try {
      await api(`/api/items/${item.id}`, "PATCH", body);
      refreshAll();
    } catch (e) {
      onError((e as Error).message);
    }
  };

  return (
    <li className={item.is_low ? "bg-amber-wash/35" : ""}>
      <div className="grid grid-cols-[1fr_auto] md:grid-cols-[1.4fr_1.1fr_150px_120px_1fr_28px] items-center gap-x-4 gap-y-2 px-5 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[15px]">
            {item.name}
            {item.is_low && <Pill tone="amber">ناقص</Pill>}
          </div>
          {item.aliases && <div className="truncate text-[12px] text-ink-mute">يسمونه: {item.aliases.split(",").slice(0, 3).join("، ")}</div>}
        </div>
        <div className="order-3 col-span-2 md:order-none md:col-span-1">
          <LevelBar qty={item.quantity} min={item.min_qty} target={item.target_qty} />
        </div>
        <div className="flex items-center gap-1.5">
          <Step label="نقص واحد" onClick={() => patch({ quantity: Math.max(0, item.quantity - 1) })}>
            <Minus size={14} />
          </Step>
          <span className={`min-w-10 text-center text-[15px] font-semibold ${item.is_low ? "text-amber" : ""}`}>{num(item.quantity)}</span>
          <Step label="زيادة واحد" onClick={() => patch({ quantity: item.quantity + 1 })}>
            <Plus size={14} />
          </Step>
          <span className="text-[12px] text-ink-mute">{item.unit}</span>
        </div>
        <label className="hidden md:flex items-center gap-1.5 text-[12.5px] text-ink-mute">
          <input
            type="number"
            min={0}
            step={1}
            value={min}
            onChange={(e) => setMin(e.target.value)}
            onBlur={() => Number(min) !== item.min_qty && patch({ min_qty: Number(min) })}
            className="w-16 rounded-lg bg-paper px-2 py-1 text-center text-[14px] text-ink ring-1 ring-line focus:ring-plum outline-none"
            aria-label={`الحد الأدنى لـ ${item.name}`}
          />
          {item.unit}
        </label>
        <div className="hidden md:block truncate text-[13.5px] text-ink-soft">{item.supplier ?? "—"}</div>
        <button onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label="سجل الحركة" className="hidden md:grid size-7 place-items-center rounded-lg text-ink-mute hover:bg-paper">
          <ChevronDown size={16} className={open ? "rotate-180" : ""} />
        </button>
      </div>
      {open && (
        <div className="border-t border-line bg-paper/60 px-5 py-3">
          <div className="mb-2 text-[13px] text-ink-mute">آخر الحركات</div>
          {!hist?.length ? (
            <div className="text-[13px] text-ink-mute">ما فيه حركات مسجلة.</div>
          ) : (
            <ul className="space-y-1.5 text-[13.5px]">
              {hist.slice(0, 6).map((h) => (
                <li key={h.id} className="flex flex-wrap gap-x-3">
                  <span className={h.delta >= 0 ? "text-sage" : "text-amber"} dir="ltr">
                    {h.delta >= 0 ? "+" : ""}
                    {num(h.delta)}
                  </span>
                  <span>{SOURCE[h.source] ?? h.source}</span>
                  {h.staff && <span className="text-ink-soft">من {h.staff}</span>}
                  {h.note && <span className="text-ink-mute">{h.note}</span>}
                  <span className="text-ink-mute">{relative(h.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

function Step({ children, onClick, label }: { children: React.ReactNode; onClick: () => void; label: string }) {
  return (
    <button onClick={onClick} aria-label={label} className="grid size-7 place-items-center rounded-lg bg-paper text-ink-soft ring-1 ring-line hover:text-plum hover:ring-plum">
      {children}
    </button>
  );
}

function Device({ d, onDone }: { d: Item; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const broken = d.status === "broken";
  return (
    <div className={`min-w-[190px] flex-1 rounded-xl px-4 py-3 ring-1 sm:flex-none ${broken ? "bg-alarm-wash/60 ring-alarm/30" : "bg-surface ring-line"}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-[14.5px]">{d.name}</span>
        <Pill tone={broken ? "alarm" : "sage"}>{broken ? "معطل" : "شغال"}</Pill>
      </div>
      {broken && d.issue && (
        <>
          <div className="mt-1 text-[12.5px] text-ink-soft">
            «{d.issue.description}» — {d.issue.reported_by}
          </div>
          <Button
            variant="ghost"
            className="mt-1 -mr-3 px-3 py-1 text-[13px]"
            busy={busy}
            onClick={async () => {
              setBusy(true);
              await api(`/api/devices/${d.id}/resolve`);
              setBusy(false);
              onDone();
              refreshAll();
            }}
          >
            تم الإصلاح
          </Button>
        </>
      )}
    </div>
  );
}
