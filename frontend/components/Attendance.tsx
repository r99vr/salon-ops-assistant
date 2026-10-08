"use client";

import { time } from "@/lib/format";
import type { AttendanceRow } from "@/lib/types";
import { Avatar, Pill } from "@/components/ui";

export function hours(min: number | null) {
  if (min == null) return "";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h}س ${m}د` : `${m}د`;
}

const STATUS: Record<AttendanceRow["status"], { t: string; tone: "sage" | "alarm" | "mute" | "plum" }> = {
  present: { t: "موجودة", tone: "sage" },
  left: { t: "طلعت", tone: "plum" },
  absent: { t: "غايبة", tone: "alarm" },
  none: { t: "ما وصلت", tone: "mute" },
};

/** قائمة حضور اليوم: كل عاملة مع وقت الحضور والخروج كما سجلتها المديرة */
export function AttendanceToday({ rows }: { rows: AttendanceRow[] }) {
  return (
    <ul className="divide-y divide-line">
      {rows.map((r) => (
        <li key={r.staff_id} className="flex items-center gap-3 py-2.5">
          <Avatar name={r.name} color={r.color} size={34} />
          <div className="min-w-0 flex-1">
            <div className="text-[15px]">{r.name}</div>
            <div className="truncate text-[12.5px] text-ink-mute">{r.title}</div>
          </div>
          <div className="text-left text-[13px] leading-5">
            {r.status === "present" && <span className="text-ink-soft">وصلت {time(r.check_in)}</span>}
            {r.status === "left" && (
              <span className="text-ink-soft">
                {time(r.check_in)} ← {time(r.check_out)}
                <span className="block text-[12px] text-ink-mute">{hours(r.minutes)}</span>
              </span>
            )}
          </div>
          <Pill tone={STATUS[r.status].tone}>{STATUS[r.status].t}</Pill>
        </li>
      ))}
    </ul>
  );
}

export function attendanceCounts(rows: AttendanceRow[]) {
  return {
    present: rows.filter((r) => r.status === "present").length,
    arrived: rows.filter((r) => r.status === "present" || r.status === "left").length,
    absent: rows.filter((r) => r.status === "absent").length,
    total: rows.length,
  };
}
