"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { mediaUrl } from "@/lib/api";
import { num } from "@/lib/format";

/** العدد بالعربي: صنف واحد، صنفين، 3 أصناف، 11 صنف */
export function count(n: number, one: string, two: string, few: string, many = one) {
  if (n === 1) return one;
  if (n === 2) return two;
  if (n >= 3 && n <= 10) return `${n} ${few}`;
  return `${n} ${many}`;
}

export function PageHeader({ title, sub, action }: { title: string; sub?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[34px] leading-[1.15] text-ink">{title}</h1>
        {sub && <p className="mt-1.5 text-[15px] text-ink-soft">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

export function SectionTitle({ children, aside }: { children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="text-[21px] text-ink">{children}</h2>
      {aside && <div className="text-[13px] text-ink-mute">{aside}</div>}
    </div>
  );
}

/** مستوى المخزون: الشريط يمتلي حتى الكمية المستهدفة، والخط الرأسي = الحد الأدنى */
export function LevelBar({ qty, min, target, compact = false }: { qty: number; min: number; target: number; compact?: boolean }) {
  const max = Math.max(target, min * 1.5, qty, 1);
  const pct = Math.min(100, (qty / max) * 100);
  const minPct = Math.min(100, (min / max) * 100);
  const low = qty < min;
  return (
    <div
      className={`relative w-full rounded-full bg-line ${compact ? "h-1.5" : "h-2"}`}
      role="meter"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={qty}
      aria-label={`الكمية ${num(qty)} والحد الأدنى ${num(min)}`}
    >
      <div className={`absolute inset-y-0 right-0 rounded-full ${low ? "bg-amber" : "bg-sage"}`} style={{ width: `${Math.max(pct, qty > 0 ? 3 : 0)}%` }} />
      <div className="absolute -inset-y-1 w-0.5 rounded bg-ink/45" style={{ right: `${minPct}%` }} />
    </div>
  );
}

const PILL: Record<string, string> = {
  sage: "bg-sage-wash text-sage",
  amber: "bg-amber-wash text-amber",
  alarm: "bg-alarm-wash text-alarm",
  plum: "bg-plum-wash text-plum",
  mute: "bg-paper text-ink-mute",
};

export function Pill({ tone = "mute", children }: { tone?: keyof typeof PILL; children: React.ReactNode }) {
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[12.5px] ${PILL[tone]}`}>{children}</span>;
}

const AVATAR: Record<string, string> = {
  plum: "#6b2d5c",
  slate: "#4b5b70",
  rose: "#b8476b",
  coral: "#c8644a",
  sage: "#3e7c6b",
  amber: "#b7791f",
  sky: "#3b78a8",
  teal: "#25737a",
};

export function Avatar({ name, color = "plum", size = 40 }: { name: string; color?: string; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-grid shrink-0 place-items-center rounded-full font-display text-white"
      style={{ width: size, height: size, background: AVATAR[color] ?? AVATAR.plum, fontSize: size * 0.42 }}
    >
      {name.trim().charAt(0)}
    </span>
  );
}

export function Button({
  children,
  variant = "primary",
  busy,
  className = "",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "ghost" | "danger"; busy?: boolean }) {
  const styles = {
    primary: "bg-plum text-white hover:bg-plum-deep",
    quiet: "bg-surface text-ink border border-line-strong hover:border-plum hover:text-plum",
    ghost: "text-plum hover:bg-plum-wash",
    danger: "text-alarm hover:bg-alarm-wash",
  }[variant];
  return (
    <button
      {...rest}
      disabled={busy || rest.disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-[14.5px] font-medium transition-colors disabled:opacity-50 ${styles} ${className}`}
    >
      {busy ? <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" /> : null}
      {children}
    </button>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-line-strong px-6 py-8 text-center">
      <div className="text-[15px] text-ink">{title}</div>
      {children && <div className="mt-1 text-[13.5px] text-ink-mute">{children}</div>}
    </div>
  );
}

export function Thumb({ src, alt, size = 44, onOpen }: { src: string; alt: string; size?: number; onOpen?: (src: string) => void }) {
  return (
    <button type="button" onClick={() => onOpen?.(src)} className="shrink-0 overflow-hidden rounded-lg ring-1 ring-line" style={{ width: size, height: size }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={mediaUrl(src)} alt={alt} className="size-full object-cover" />
    </button>
  );
}

export function useLightbox() {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSrc(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const node = src ? (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/80 p-4" role="dialog" aria-modal onClick={() => setSrc(null)}>
      <button className="absolute top-4 left-4 rounded-full bg-white/15 p-2 text-white" aria-label="إغلاق">
        <X size={22} />
      </button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={mediaUrl(src)} alt="" className="max-h-[88dvh] max-w-full rounded-xl shadow-2xl" />
    </div>
  ) : null;
  return { open: setSrc, node };
}

export function useToast() {
  const [msg, setMsg] = useState<{ text: string; tone: "ok" | "err" } | null>(null);
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 3500);
    return () => clearTimeout(t);
  }, [msg]);
  const node = msg ? (
    <div
      role="status"
      className={`fixed bottom-24 lg:bottom-8 left-1/2 z-50 -translate-x-1/2 rounded-xl px-4 py-2.5 text-[14px] shadow-lg ${
        msg.tone === "ok" ? "bg-ink text-white" : "bg-alarm text-white"
      }`}
    >
      {msg.text}
    </div>
  ) : null;
  return { ok: (t: string) => setMsg({ text: t, tone: "ok" }), err: (t: string) => setMsg({ text: t, tone: "err" }), node };
}
