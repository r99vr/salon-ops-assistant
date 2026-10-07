"use client";

import { Check } from "lucide-react";
import { mediaUrl } from "@/lib/api";
import { minutesOfDay, time } from "@/lib/format";
import type { Run, Salon } from "@/lib/types";

const START = 7 * 60;
const END = 23 * 60;
const pos = (m: number) => ((Math.min(Math.max(m, START), END) - START) / (END - START)) * 100;
const hm = (s: string) => {
  const [h, m] = s.split(":").map(Number);
  return h * 60 + m;
};
const clock = (m: number) => {
  const h = Math.floor(m / 60);
  const mm = String(m % 60).padStart(2, "0");
  return `${((h + 11) % 12) + 1}:${mm} ${h < 12 ? "ص" : "م"}`;
};

/**
 * «يوم الصالون»: فوق، جدول المساعد (متى يرسل وش) مع إبرة «الآن».
 * تحت، قائمة مهام النظافة لليوم: كل مهمة تنقفل بصورة في أي وقت، بدون مواعيد.
 */
export default function DayRibbon({ runs, salon, now, onOpen }: { runs: Run[]; salon: Salon; now: string; onOpen: (src: string) => void }) {
  const nowM = minutesOfDay(now);
  const open = nowM >= START && nowM <= END;
  const stations = [
    { at: hm(salon.morning_time), label: "تقرير الصباح" },
    { at: hm(salon.tasks_time), label: "قائمة النظافة" },
    { at: hm(salon.tasks_check_time), label: "مراجعة المهام" },
    { at: hm(salon.summary_time), label: "ملخص الطلبية" },
  ]
    .sort((a, b) => a.at - b.at)
    // المحطات المتقاربة (أقل من ساعتين) تنزل أسماؤها سطر عشان ما تتداخل
    .reduce<{ at: number; label: string; row: number }[]>((acc, s) => {
      const prev = acc[acc.length - 1];
      acc.push({ ...s, row: prev && s.at - prev.at < 120 && prev.row === 0 ? 1 : 0 });
      return acc;
    }, []);
  const done = runs.filter((r) => r.status === "done").length;

  return (
    <div>
      {/* جدول المساعد */}
      <div className="overflow-x-auto overflow-y-hidden scroll-thin -mx-5 sm:-mx-7">
        <div className="relative mx-12 min-w-[640px] h-[128px]" aria-label="جدول المساعد اليوم">
          <div className="absolute top-[30px] inset-x-0 h-[3px] rounded-full bg-line" />
          <div
            className="absolute top-[30px] right-0 h-[3px] rounded-full bg-plum/35"
            style={{ width: `${open ? pos(nowM) : nowM > END ? 100 : 0}%` }}
          />
          {stations.map((s) => {
            const passed = nowM >= s.at;
            return (
              <div key={s.label} className="absolute top-[24px] text-center" style={{ right: `${pos(s.at)}%`, transform: "translateX(50%)" }}>
                <div className={`mx-auto size-3.5 rotate-45 ${passed ? "bg-plum" : "bg-surface ring-2 ring-plum/50"}`} />
                {s.row === 1 && <div className="mx-auto mt-1 h-11 w-px bg-plum/25" />}
                <div className={`${s.row === 1 ? "mt-0.5" : "mt-2.5"} whitespace-nowrap text-[12.5px] ${passed ? "text-plum" : "text-ink-soft"}`}>{s.label}</div>
                <div className="text-[11px] text-ink-mute">{clock(s.at)}</div>
              </div>
            );
          })}
          {open ? (
            <div className="absolute top-0 h-[36px] w-0.5 bg-plum" style={{ right: `${pos(nowM)}%` }}>
              <span
                className={`absolute -top-0.5 whitespace-nowrap rounded-md bg-plum px-1.5 py-0.5 text-[11px] text-white ${pos(nowM) > 85 ? "left-1.5" : "right-1.5"}`}
              >
                الآن {time(now)}
              </span>
            </div>
          ) : (
            <div className="absolute -top-0.5 left-0 rounded-md bg-paper px-2 py-0.5 text-[11.5px] text-ink-mute">
              الحين {time(now)}، خارج ساعات الدوام
            </div>
          )}
        </div>
      </div>

      {/* قائمة النظافة */}
      <div className="mt-4 border-t border-line pt-4">
        <div className="mb-3 flex items-center gap-3">
          <h3 className="text-[16px]">قائمة النظافة</h3>
          <div className="h-1.5 flex-1 max-w-48 rounded-full bg-line" role="progressbar" aria-valuenow={done} aria-valuemax={runs.length}>
            <div className="h-full rounded-full bg-sage" style={{ width: `${runs.length ? (done / runs.length) * 100 : 0}%` }} />
          </div>
          <span className="text-[13px] text-ink-soft">
            {done} من {runs.length}
          </span>
        </div>
        <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
          {runs.map((r) => {
            const isDone = r.status === "done";
            const late = r.status === "overdue" || r.status === "missed";
            return (
              <li key={r.id}>
                <button
                  type="button"
                  disabled={!r.proof_url}
                  onClick={() => r.proof_url && onOpen(r.proof_url)}
                  className={`group block w-full overflow-hidden rounded-xl text-right ring-1 ${
                    isDone ? "ring-sage/40" : late ? "ring-alarm/40" : "ring-line"
                  }`}
                  aria-label={`${r.title}: ${isDone ? "تمت" : late ? "متأخرة" : "باقية"}`}
                >
                  <div className={`relative aspect-[4/3] ${isDone ? "" : late ? "bg-alarm-wash/60" : "bg-paper"}`}>
                    {r.proof_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={mediaUrl(r.proof_url)} alt="" className="size-full object-cover" />
                    ) : (
                      <span className={`absolute inset-0 grid place-items-center text-[12px] ${late ? "text-alarm" : "text-ink-mute"}`}>
                        {late ? "ما وصلت الصورة" : "بانتظار الصورة"}
                      </span>
                    )}
                    {isDone && (
                      <span className="absolute top-1.5 right-1.5 grid size-5 place-items-center rounded-full bg-sage text-white">
                        <Check size={13} strokeWidth={3} />
                      </span>
                    )}
                  </div>
                  <div className="bg-surface px-2.5 py-2">
                    <div className="truncate text-[13px] leading-5" title={r.title}>
                      {r.title}
                    </div>
                    <div className="text-[11.5px] text-ink-mute">{isDone ? `قُفلت ${time(r.done_at)}` : late ? "ذكّرها المساعد" : " "}</div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
