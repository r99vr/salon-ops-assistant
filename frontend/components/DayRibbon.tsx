"use client";

import { mediaUrl } from "@/lib/api";
import { minutesOfDay, time } from "@/lib/format";
import type { Run, Salon } from "@/lib/types";

const START = 8 * 60;
const END = 23 * 60;
const pos = (m: number) => ((Math.min(Math.max(m, START), END) - START) / (END - START)) * 100;
const hm = (s: string) => {
  const [h, m] = s.split(":").map(Number);
  return h * 60 + m;
};

/** «يوم الصالون»: خط زمني من الصباح لآخر الليل — مهام النظافة كحبات، ومحطات المساعد تحت الخط، وإبرة «الآن». */
export default function DayRibbon({ runs, salon, now, onOpen }: { runs: Run[]; salon: Salon; now: string; onOpen: (src: string) => void }) {
  const nowM = minutesOfDay(now);
  const events = [
    { at: hm(salon.morning_time), label: "تقرير الصباح" },
    { at: hm(salon.tasks_time), label: "مهام النظافة" },
    { at: hm(salon.summary_time), label: "ملخص الطلبية" },
  ]
    .sort((a, b) => a.at - b.at)
    .map((e, i, arr) => ({ ...e, row: i > 0 && e.at - arr[i - 1].at < 150 && !(arr[i - 1] as { row?: number }).row ? 1 : 0 }));
  const hours = Array.from({ length: (END - START) / 60 + 1 }, (_, i) => START + i * 60);

  return (
    <div className="overflow-x-auto scroll-thin -mx-5 sm:-mx-7">
      <div className="relative mx-10 min-w-[720px] h-[214px]" aria-label="الخط الزمني لليوم">
        {/* ساعات */}
        {hours.map((m) => (
          <div key={m} className="absolute top-[118px] h-3 w-px bg-line-strong" style={{ right: `${pos(m)}%` }}>
            {m % 120 === 0 && (
              <span className="absolute top-4 translate-x-1/2 text-[11.5px] text-ink-mute whitespace-nowrap">
                {((m / 60 + 11) % 12) + 1}
                {m / 60 < 12 ? "ص" : "م"}
              </span>
            )}
          </div>
        ))}
        {/* الخط: الجزء اللي مضى أغمق */}
        <div className="absolute top-[117px] inset-x-0 h-[3px] rounded-full bg-line" />
        <div className="absolute top-[117px] right-0 h-[3px] rounded-full bg-plum/35" style={{ width: `${pos(nowM)}%` }} />

        {/* مهام النظافة */}
        {runs.map((r, i) => {
          const m = minutesOfDay(r.due_at);
          const row = i % 2;
          const ring =
            r.status === "done"
              ? "ring-sage"
              : r.status === "overdue" || r.status === "missed"
                ? "ring-alarm"
                : "ring-line-strong";
          return (
            <div key={r.id} className="absolute" style={{ right: `${pos(m)}%`, top: row ? 46 : 2, transform: "translateX(50%)" }}>
              <div className="flex flex-col items-center">
                <span className={`max-w-[118px] truncate text-[12.5px] leading-5 ${r.status === "overdue" ? "text-alarm" : "text-ink-soft"}`} title={r.title}>
                  {r.title}
                </span>
                <span className="text-[11px] text-ink-mute">{time(r.due_at)}</span>
              </div>
              <div className="absolute left-1/2 -translate-x-1/2 w-px bg-line-strong" style={{ top: 40, height: row ? 18 : 62 }} />
              <button
                type="button"
                disabled={!r.proof_url}
                onClick={() => r.proof_url && onOpen(r.proof_url)}
                aria-label={`${r.title}: ${r.status === "done" ? "تمت" : r.status === "overdue" ? "متأخرة" : "لم يحن وقتها"}`}
                className={`absolute left-1/2 -translate-x-1/2 size-9 overflow-hidden rounded-full bg-surface ring-[3px] ${ring}`}
                style={{ top: row ? 54 : 98 }}
              >
                {r.proof_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={mediaUrl(r.proof_url)} alt="" className="size-full object-cover" />
                ) : r.status === "overdue" ? (
                  <span className="text-alarm text-lg leading-9">!</span>
                ) : null}
              </button>
            </div>
          );
        })}

        {/* محطات المساعد */}
        {events.map((e) => (
          <div key={e.label} className="absolute top-[152px]" style={{ right: `${pos(e.at)}%`, transform: "translateX(50%)" }}>
            <div className="mx-auto size-2.5 rotate-45 bg-plum" />
            {e.row === 1 && <div className="mx-auto h-7 w-px bg-plum/30" />}
            <div className={`${e.row === 1 ? "mt-0.5" : "mt-2"} whitespace-nowrap text-center text-[12px] text-plum`}>{e.label}</div>
            <div className="text-center text-[11px] text-ink-mute">{e.at >= 720 ? `${((e.at / 60 + 11) % 12) + 1}:${String(e.at % 60).padStart(2, "0")}م` : `${e.at / 60 | 0}:${String(e.at % 60).padStart(2, "0")}ص`}</div>
          </div>
        ))}

        {/* الآن */}
        <div className="absolute top-[92px] h-[52px] w-0.5 bg-plum" style={{ right: `${pos(nowM)}%` }}>
          <span className="needle-dot absolute -top-1 left-1/2 -translate-x-1/2 size-2.5 rounded-full bg-plum" />
          <span
            className={`absolute top-[54px] whitespace-nowrap rounded-md bg-plum px-1.5 py-0.5 text-[11px] text-white ${pos(nowM) > 85 ? "left-1" : "right-1"}`}
          >
            الآن {time(now)}
          </span>
        </div>
      </div>
    </div>
  );
}
