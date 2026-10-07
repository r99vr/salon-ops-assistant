let TZ = "Asia/Riyadh";

/** توقيت الصالون يجي من الخلفية (إعداد TIMEZONE) */
export function setTimezone(tz?: string) {
  if (tz) TZ = tz;
}

export function time(iso?: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("ar-SA-u-nu-latn", { hour: "numeric", minute: "2-digit", timeZone: TZ });
}

export function dayLabel(iso: string) {
  return new Date(iso).toLocaleDateString("ar-SA-u-nu-latn-ca-gregory", { weekday: "long", day: "numeric", month: "long", timeZone: TZ });
}

export function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString("ar-SA-u-nu-latn-ca-gregory", { day: "numeric", month: "short", timeZone: TZ });
}

export function relative(iso?: string | null) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 60000;
  if (diff < 1) return "الحين";
  if (diff < 60) return `قبل ${Math.round(diff)} د`;
  if (diff < 60 * 24) return `قبل ${Math.round(diff / 60)} س`;
  const d = Math.round(diff / 1440);
  return d === 1 ? "أمس" : `قبل ${d} أيام`;
}

export function num(n: number) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace(/\.0$/, "");
}

export function money(n: number) {
  return Math.round(n).toLocaleString("en-US");
}

/** دقائق منذ بداية اليوم بتوقيت الرياض */
export function minutesOfDay(iso: string) {
  const parts = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: TZ }).formatToParts(new Date(iso));
  const h = Number(parts.find((p) => p.type === "hour")?.value);
  const m = Number(parts.find((p) => p.type === "minute")?.value);
  return h * 60 + m;
}

export const KIND_LABEL: Record<string, string> = {
  shortage: "نقص",
  task_proof: "إثبات مهمة",
  issue: "عطل",
  invoice: "فاتورة",
  owner_command: "أمر",
  supplier_reply: "رد المندوب",
  other: "عام",
  summary: "ملخص الطلبية",
  report: "تقرير الصباح",
  alert: "تنبيه",
  order: "طلبية",
  reminder: "تذكير",
  tasks: "مهام اليوم",
  question: "سؤال توضيحي",
  reply: "رد",
};

export const ORDER_STATUS: Record<string, string> = {
  draft: "تتجمع لملخص الليلة",
  awaiting_approval: "بانتظار موافقتك",
  sent: "أُرسلت للمندوب",
  confirmed: "أكدها المندوب",
  received: "استُلمت",
  cancelled: "ملغاة",
};
