"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, ClipboardCheck, House, MessagesSquare, Settings2, Truck } from "lucide-react";
import { useApi } from "@/lib/api";
import type { Overview } from "@/lib/types";
import { setTimezone } from "@/lib/format";

const NAV = [
  { href: "/", label: "الرئيسية", icon: House },
  { href: "/inventory", label: "المخزون", icon: Boxes },
  { href: "/tasks", label: "مهام النظافة", icon: ClipboardCheck },
  { href: "/orders", label: "الطلبيات", icon: Truck },
  { href: "/simulator", label: "المحاكي", icon: MessagesSquare },
  { href: "/settings", label: "الإعدادات", icon: Settings2 },
];

const CHANNEL: Record<string, string> = { simulator: "المحاكي فقط", telegram: "تيليجرام", whatsapp: "واتساب" };

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { data, error } = useApi<Overview>("/api/overview", 15000);
  setTimezone(data?.salon.timezone);
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  const lowCount = data?.stats.low_count ?? 0;
  const awaiting = data?.open_orders.filter((o) => o.status === "awaiting_approval").length ?? 0;

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="hidden lg:flex flex-col border-l border-line bg-surface sticky top-0 h-dvh">
        <div className="px-6 pt-7 pb-6">
          <div className="font-display text-[26px] leading-tight text-plum">{data?.salon.name ?? "…"}</div>
          <div className="text-[13px] text-ink-mute mt-1">مساعد التشغيل</div>
        </div>
        <nav className="flex-1 px-3 space-y-0.5" aria-label="الأقسام">
          {NAV.map(({ href, label, icon: Icon }) => {
            const badge = href === "/inventory" ? lowCount : href === "/orders" ? awaiting : 0;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active(href) ? "page" : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] transition-colors ${
                  active(href) ? "bg-plum-wash text-plum-deep font-medium" : "text-ink-soft hover:bg-paper"
                }`}
              >
                <Icon size={19} strokeWidth={1.8} aria-hidden />
                <span className="flex-1">{label}</span>
                {badge > 0 && (
                  <span
                    className={`min-w-6 rounded-full px-1.5 text-center text-xs leading-6 ${
                      href === "/orders" ? "bg-plum text-white" : "bg-amber-wash text-amber"
                    }`}
                  >
                    {badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        {data && (
          <div className="m-4 rounded-xl bg-paper px-4 py-3 text-[13px] text-ink-soft">
            <div className="flex items-center gap-2">
              <span className={`size-2 rounded-full ${data.salon.channel === "simulator" ? "bg-ink-mute" : "bg-sage"}`} />
              القناة: {CHANNEL[data.salon.channel]}
            </div>
          </div>
        )}
      </aside>

      <div className="min-w-0 pb-24 lg:pb-0">
        <header className="lg:hidden sticky top-0 z-20 flex items-center justify-between bg-paper/90 backdrop-blur px-4 py-3 border-b border-line">
          <div className="font-display text-xl text-plum">{data?.salon.name ?? "…"}</div>
          <div className="text-xs text-ink-mute">مساعد التشغيل</div>
        </header>
        <main className="mx-auto max-w-[1180px] px-4 sm:px-6 lg:px-10 py-6 lg:py-9">
          {/* ننتظر إعدادات الصالون (التوقيت) قبل عرض أي صفحة */}
          {data || error ? children : <div className="py-24 text-center text-ink-mute">جاري التحميل…</div>}
        </main>
      </div>

      <nav
        className="lg:hidden fixed bottom-0 inset-x-0 z-30 grid grid-cols-6 border-t border-line bg-surface/95 backdrop-blur pb-[env(safe-area-inset-bottom)]"
        aria-label="الأقسام"
      >
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            aria-current={active(href) ? "page" : undefined}
            className={`flex flex-col items-center gap-1 py-2 text-[10.5px] ${active(href) ? "text-plum" : "text-ink-mute"}`}
          >
            <Icon size={20} strokeWidth={1.8} aria-hidden />
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
