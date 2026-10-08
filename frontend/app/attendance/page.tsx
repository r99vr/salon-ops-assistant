"use client";

import { useApi } from "@/lib/api";
import { time } from "@/lib/format";
import type { AttendanceRow } from "@/lib/types";
import { AttendanceToday, attendanceCounts } from "@/components/Attendance";
import { Avatar, PageHeader, SectionTitle } from "@/components/ui";

type Data = { today: AttendanceRow[]; history: { date: string; rows: AttendanceRow[] }[]; recorder: string | null };

const weekday = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("ar-SA-u-nu-latn-ca-gregory", { weekday: "short" });
const dayNum = (iso: string) => new Date(iso + "T12:00:00").getDate();

export default function Attendance() {
  const { data } = useApi<Data>("/api/attendance?days=7", 8000);
  if (!data) return <div className="py-24 text-center text-ink-mute">جاري التحميل…</div>;
  const c = attendanceCounts(data.today);
  const staff = data.today;

  // مجموع الساعات لكل عاملة خلال الأسبوع
  const totals = new Map<number, number>();
  data.history.forEach((d) => d.rows.forEach((r) => r.minutes && totals.set(r.staff_id, (totals.get(r.staff_id) ?? 0) + r.minutes)));

  return (
    <>
      <PageHeader
        title="الحضور"
        sub={`${data.recorder ?? "المديرة"} ترسل للمساعد مين وصلت ومين طلعت، مثل «وصلت نورة وريم» أو «سارة طلعت». المساعد يسجّل الوقت ويطلع هنا.`}
      />

      <div className="space-y-10">
        <section className="max-w-xl">
          <SectionTitle aside={`وصلت ${c.arrived} من ${c.total}`}>اليوم</SectionTitle>
          <div className="rounded-2xl bg-surface px-4 py-1 ring-1 ring-line">
            <AttendanceToday rows={data.today} />
          </div>
        </section>

        <section className="min-w-0">
          <SectionTitle aside="الحضور والخروج كما سجلتها المديرة">آخر 7 أيام</SectionTitle>
          <div className="overflow-x-auto scroll-thin rounded-2xl bg-surface ring-1 ring-line">
            <table className="w-full min-w-[720px] text-[12.5px] [&_td]:whitespace-nowrap">
              <thead>
                <tr className="border-b border-line text-ink-mute">
                  <th className="px-4 py-2.5 text-right font-normal">العاملة</th>
                  {data.history.map((d, i) => (
                    <th key={d.date} className={`px-1.5 py-2.5 text-center font-normal ${i === data.history.length - 1 ? "text-plum" : ""}`}>
                      <div>{i === data.history.length - 1 ? "اليوم" : weekday(d.date)}</div>
                      <div className="text-[11px]">{dayNum(d.date)}</div>
                    </th>
                  ))}
                  <th className="px-3 py-2.5 text-center font-normal">المجموع</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {staff.map((s) => (
                  <tr key={s.staff_id}>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <Avatar name={s.name} color={s.color} size={26} />
                        <span className="text-[14px]">{s.name}</span>
                      </div>
                    </td>
                    {data.history.map((d, i) => {
                      const r = d.rows.find((x) => x.staff_id === s.staff_id);
                      return (
                        <td key={d.date} className="px-1 py-1.5 text-center">
                          <Cell r={r} today={i === data.history.length - 1} />
                        </td>
                      );
                    })}
                    <td className="px-3 py-2.5 text-center text-[13px] font-medium text-ink-soft">{totals.get(s.staff_id) ? `${Math.round((totals.get(s.staff_id) ?? 0) / 60)} ساعة` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-[12px] text-ink-mute">
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-sage-wash ring-1 ring-sage/40" /> حضور وخروج
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-amber-wash ring-1 ring-amber/40" /> ما سُجل خروج
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-alarm-wash ring-1 ring-alarm/40" /> غياب
            </span>
          </div>
        </section>
      </div>
    </>
  );
}

function Cell({ r, today }: { r?: AttendanceRow; today: boolean }) {
  if (!r || r.status === "none") return <span className="text-ink-mute">—</span>;
  if (r.status === "absent") return <span className="block rounded-lg bg-alarm-wash px-1 py-1.5 text-alarm">غياب</span>;
  const open = r.status === "present";
  return (
    <span className={`block rounded-lg px-2 py-1 leading-4 ${open ? "bg-amber-wash text-amber" : "bg-sage-wash text-ink"}`}>
      {time(r.check_in)}
      <span className="block text-[11px] text-ink-mute">{open ? (today ? "موجودة" : "بدون خروج") : time(r.check_out)}</span>
    </span>
  );
}
