"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCheck, ImagePlus, RotateCcw, SendHorizontal, Upload } from "lucide-react";
import { api, apiForm, mediaUrl, refreshAll, useApi } from "@/lib/api";
import { KIND_LABEL, time } from "@/lib/format";
import type { Contact, Msg, Section } from "@/lib/types";
import { Avatar, Button, useLightbox, useToast } from "@/components/ui";

type Sample = { file: string; url: string; label: string };

const GROUPS: { role: Contact["role"][]; label: string }[] = [
  { role: ["owner", "manager"], label: "الإدارة" },
  { role: ["staff"], label: "العاملات" },
  { role: ["supplier"], label: "مناديب الموردين" },
];

const DEMO_JOBS = [
  { job: "tasks", label: "إرسال قائمة النظافة", hint: "مهام اليوم لعاملة النظافة" },
  { job: "cleaning_check", label: "مراجعة مهام النظافة", hint: "الضغطة الأولى تذكير للعاملة باللي باقي، الثانية تنبيه لصاحبة الصالون" },
  { job: "summary", label: "ملخص الثامنة الآن", hint: "طلبية اليوم تروح لصاحبة الصالون للموافقة" },
  { job: "supplier_followup", label: "المندوب ما رد", hint: "تذكير للمندوب، وبعدها تنبيه للإدارة" },
  { job: "morning", label: "تقرير الصباح الآن", hint: "النواقص والمهام والأعطال والمصاريف" },
];

export default function Simulator() {
  const { data: contacts } = useApi<Contact[]>("/api/sim/contacts", 4000);
  const { data: inv } = useApi<{ sections: Section[] }>("/api/inventory");
  const { data: samples } = useApi<Sample[]>("/api/sim/samples");
  const [phone, setPhone] = useState<string | null>(null);
  const current = contacts?.find((c) => c.phone === phone) ?? null;
  const toast = useToast();
  const [jobBusy, setJobBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!phone && contacts?.length) setPhone(contacts.find((c) => c.role === "staff")?.phone ?? contacts[0].phone);
  }, [contacts, phone]);

  const runJob = async (job: string) => {
    setJobBusy(job);
    try {
      const r = await api<{ result: Record<string, number> }>(`/api/demo/run/${job}`);
      const res = r.result || {};
      const nothing = Object.values(res).every((v) => !v);
      toast.ok(nothing && job !== "morning" && job !== "summary" ? "ما فيه شي يحتاج إرسال الحين" : "تم، شوف المحادثات");
      refreshAll();
    } catch (e) {
      toast.err((e as Error).message);
    } finally {
      setJobBusy(null);
    }
  };

  const reset = async () => {
    if (!confirm("ترجع كل بيانات العرض لبدايتها؟ (المحادثات والطلبيات والمخزون)")) return;
    setJobBusy("reset");
    await api("/api/demo/reset");
    setJobBusy(null);
    toast.ok("رجعت بيانات العرض لبدايتها");
    refreshAll();
  };

  return (
    <div className="-mx-4 sm:mx-0">
      <div className="px-4 sm:px-0 mb-5">
        <h1 className="text-[34px] leading-[1.15]">المحاكي</h1>
        <p className="mt-1.5 text-[15px] text-ink-soft">اختر أي شخص من الفريق واكتب كأنك هو. المساعد يرد بنفس الطريقة اللي يرد فيها على الجوال.</p>
      </div>

      <div className="grid gap-5 xl:grid-cols-[260px_1fr_250px]">
        {/* الأشخاص */}
        <aside className="px-4 sm:px-0 xl:max-h-[calc(100dvh-180px)] xl:overflow-y-auto scroll-thin">
          <div className="flex gap-2 overflow-x-auto pb-2 xl:block xl:space-y-5 xl:overflow-visible scroll-thin">
            {GROUPS.map((g) => (
              <div key={g.label} className="contents xl:block">
                <div className="hidden xl:block mb-1.5 text-[13px] text-ink-mute">{g.label}</div>
                {contacts
                  ?.filter((c) => g.role.includes(c.role))
                  .map((c) => (
                    <button
                      key={c.phone}
                      onClick={() => setPhone(c.phone)}
                      aria-pressed={c.phone === phone}
                      className={`flex shrink-0 items-center gap-3 rounded-xl px-2.5 py-2 text-right xl:w-full ${
                        c.phone === phone ? "bg-surface ring-1 ring-plum/40 shadow-sm" : "hover:bg-surface"
                      }`}
                    >
                      <Avatar name={c.name} color={c.color} size={38} />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-baseline justify-between gap-2">
                          <span className="text-[14.5px] font-medium">{c.name}</span>
                          {c.last && <span className="hidden xl:inline text-[11px] text-ink-mute">{time(c.last.created_at)}</span>}
                        </span>
                        <span className="block truncate text-[12.5px] text-ink-mute xl:max-w-[170px]">{c.subtitle}</span>
                      </span>
                    </button>
                  ))}
              </div>
            ))}
          </div>
        </aside>

        {/* المحادثة */}
        {current ? (
          <Chat key={current.phone} contact={current} sections={inv?.sections ?? []} samples={samples ?? []} onError={toast.err} />
        ) : (
          <div className="h-[560px] rounded-2xl bg-surface" />
        )}

        {/* تحكم العرض */}
        <aside className="px-4 sm:px-0">
          <h2 className="text-[19px]">تحكم العرض</h2>
          <p className="mt-1 mb-3 text-[13px] text-ink-mute">يشغّل اللي يصير تلقائياً في وقته، بدون ما تنتظر الساعة.</p>
          <div className="space-y-2">
            {DEMO_JOBS.map((j) => (
              <button
                key={j.job}
                onClick={() => runJob(j.job)}
                disabled={!!jobBusy}
                className="block w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-right transition-colors hover:border-plum disabled:opacity-60"
              >
                <span className="flex items-center justify-between text-[14.5px] font-medium text-plum">
                  {j.label}
                  {jobBusy === j.job && <span className="size-3.5 animate-spin rounded-full border-2 border-plum border-t-transparent" />}
                </span>
                <span className="mt-0.5 block text-[12.5px] leading-5 text-ink-mute">{j.hint}</span>
              </button>
            ))}
          </div>
          <Button variant="danger" className="mt-4 w-full" onClick={reset} busy={jobBusy === "reset"}>
            <RotateCcw size={16} /> إعادة بيانات العرض
          </Button>
        </aside>
      </div>
      {toast.node}
    </div>
  );
}

function suggestions(contact: Contact, sections: Section[]): string[] {
  if (contact.role === "manager") return ["وصلت نورة وريم", "الكل وصل", "هيا غايبة اليوم", "طلعت سارة", "مين حاضر؟"];
  if (contact.role === "owner") return ["موافقة", "شيل مطهر الأدوات", "الصبغة البنية 8", "انصلح استشوار 2"];
  if (contact.role === "supplier") return ["تم، يوصلكم بكرة العصر", "الصنف الثاني بيتأخر يومين"];
  const own = sections.filter((s) => s.staff?.name === contact.name);
  const items = own.flatMap((s) => s.items);
  const cons = items.filter((i) => i.kind === "consumable");
  const devs = items.filter((i) => i.kind === "device");
  const out: string[] = [];
  if (cons[0]) out.push(`خلصت ${cons[0].name}`);
  if (cons[2]) out.push(`${cons[2].name} باقي ثنتين بس`);
  if (devs[1]) out.push(`${devs[1].aliases.split(",")[0] || devs[1].name} ما يشتغل`);
  else if (devs[0]) out.push(`${devs[0].name} خربان`);
  return out;
}

function Chat({ contact, sections, samples, onError }: { contact: Contact; sections: Section[]; samples: Sample[]; onError: (t: string) => void }) {
  const { data: thread, mutate } = useApi<Msg[]>(`/api/sim/thread/${contact.phone}`, 2000);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState<{ text: string; image?: string } | null>(null);
  const [showSamples, setShowSamples] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lb = useLightbox();
  const chips = useMemo(() => suggestions(contact, sections), [contact, sections]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [thread?.length, pending]);

  const send = async (opts: { text?: string; sample?: Sample; file?: File }) => {
    const body = (opts.text ?? text).trim();
    if (!body && !opts.sample && !opts.file) return;
    const form = new FormData();
    form.append("phone", contact.phone);
    form.append("text", body);
    if (opts.sample) form.append("sample", opts.sample.file);
    if (opts.file) form.append("image", opts.file);
    setPending({ text: body, image: opts.sample?.url ?? (opts.file ? URL.createObjectURL(opts.file) : undefined) });
    setText("");
    setShowSamples(false);
    setSending(true);
    try {
      await apiForm("/api/sim/send", form);
      await mutate();
      refreshAll();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setPending(null);
      setSending(false);
    }
  };

  const isAgentSide = (m: Msg) => m.direction === "out";

  return (
    <section className="flex h-[min(720px,calc(100dvh-170px))] min-h-[520px] flex-col overflow-hidden sm:rounded-2xl bg-surface ring-1 ring-line">
      <header className="flex items-center gap-3 border-b border-line px-4 py-3">
        <Avatar name={contact.name} color={contact.color} size={40} />
        <div className="min-w-0 flex-1">
          <div className="text-[15.5px] font-medium">تكتب الحين كأنك {contact.name}</div>
          <div className="truncate text-[12.5px] text-ink-mute">{contact.subtitle}، والطرف الثاني هو مساعد الصالون</div>
        </div>
      </header>

      <div ref={scrollRef} className="chat-wallpaper flex-1 overflow-y-auto scroll-thin px-3 sm:px-5 py-4 space-y-2" aria-live="polite">
        {thread?.length === 0 && !pending && (
          <div className="mx-auto mt-10 max-w-xs rounded-xl bg-white/80 px-4 py-3 text-center text-[13.5px] text-ink-soft">
            ما فيه محادثة بعد. جرّب وحدة من الاقتراحات تحت.
          </div>
        )}
        {thread?.map((m) => (
          <Bubble key={m.id} m={m} mine={!isAgentSide(m)} onOpen={lb.open} />
        ))}
        {pending && (
          <>
            <Bubble
              m={{ id: -1, body: pending.text, media_url: null, created_at: new Date().toISOString(), direction: "in" } as Msg}
              localImage={pending.image}
              mine
              onOpen={lb.open}
            />
            <div className="bubble-in w-fit rounded-2xl rounded-tr-sm bg-chat-in px-4 py-2.5 text-[13.5px] text-ink-mute shadow-sm">المساعد يكتب…</div>
          </>
        )}
      </div>

      <div className="border-t border-line bg-paper/70 px-3 pt-2.5 pb-3">
        {chips.length > 0 && (
          <div className="mb-2 flex gap-2 overflow-x-auto scroll-thin pb-1">
            {chips.map((c) => (
              <button
                key={c}
                onClick={() => send({ text: c })}
                disabled={sending}
                className="shrink-0 rounded-full border border-line-strong bg-surface px-3 py-1 text-[13px] text-ink-soft hover:border-plum hover:text-plum disabled:opacity-50"
              >
                {c}
              </button>
            ))}
          </div>
        )}

        {showSamples && (
          <div className="mb-2 rounded-xl bg-surface p-2.5 ring-1 ring-line">
            <div className="mb-2 flex items-center justify-between text-[13px] text-ink-soft">
              صور جاهزة للعرض
              <button onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-1 text-plum hover:underline">
                <Upload size={14} /> أو ارفع صورة من جهازك
              </button>
            </div>
            <div className="flex gap-2 overflow-x-auto scroll-thin pb-1">
              {samples.map((s) => (
                <button key={s.file} onClick={() => send({ sample: s })} className="w-20 shrink-0 text-center" title={`إرسال: ${s.label}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={mediaUrl(s.url)} alt="" className="h-20 w-20 rounded-lg object-cover ring-1 ring-line" />
                  <span className="mt-1 block truncate text-[11.5px] text-ink-soft">{s.label}</span>
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[11.5px] text-ink-mute">النص اللي في الخانة ينرسل مع الصورة كتعليق.</p>
          </div>
        )}

        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send({});
          }}
        >
          <button
            type="button"
            onClick={() => setShowSamples((v) => !v)}
            aria-expanded={showSamples}
            aria-label="إرفاق صورة"
            className={`grid size-11 shrink-0 place-items-center rounded-full ${showSamples ? "bg-plum text-white" : "bg-surface text-ink-soft ring-1 ring-line hover:text-plum"}`}
          >
            <ImagePlus size={20} />
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) send({ file: f });
              e.target.value = "";
            }}
          />
          <label className="sr-only" htmlFor="sim-input">
            الرسالة
          </label>
          <input
            id="sim-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={`اكتب كأنك ${contact.name}…`}
            autoComplete="off"
            className="min-w-0 flex-1 rounded-full bg-surface px-4 py-2.5 text-[15px] ring-1 ring-line outline-none focus:ring-plum"
          />
          <button
            type="submit"
            disabled={sending || !text.trim()}
            aria-label="إرسال"
            className="grid size-11 shrink-0 place-items-center rounded-full bg-sage text-white disabled:opacity-40"
          >
            <SendHorizontal size={19} className="-scale-x-100" />
          </button>
        </form>
      </div>
      {lb.node}
    </section>
  );
}

function Bubble({ m, mine, onOpen, localImage }: { m: Msg; mine: boolean; onOpen: (s: string) => void; localImage?: string }) {
  const img = localImage ?? (m.media_url ? mediaUrl(m.media_url) : null);
  const c = m.classification;
  const failed = m.transport === "failed";
  return (
    <div className={`bubble-in flex flex-col ${mine ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[85%] sm:max-w-[72%] rounded-2xl px-3 py-2 shadow-sm ${
          mine ? "rounded-tl-sm bg-chat-out" : "rounded-tr-sm bg-chat-in"
        }`}
      >
        {img && (
          <button type="button" onClick={() => onOpen(localImage ? (m.media_url ?? "") : m.media_url!)} className="mb-1.5 block overflow-hidden rounded-xl">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img} alt="صورة مرسلة" className="max-h-60 w-full object-cover" />
          </button>
        )}
        {m.body && <div className="whitespace-pre-line text-[14.5px] leading-7 text-ink">{m.body}</div>}
        <div className="mt-0.5 flex items-center justify-end gap-1 text-[11px] text-ink-mute">
          {!mine && m.channel && m.channel !== "simulator" && (
            <span className={failed ? "text-alarm" : ""}>
              {m.channel === "telegram" ? "تيليجرام" : "واتساب"}
              {m.transport === "not_linked" ? " (الشخص ما ربط حسابه)" : failed ? " (فشل الإرسال)" : ""}
            </span>
          )}
          <span>{time(m.created_at)}</span>
          {mine && <CheckCheck size={14} className="text-sky-600" />}
        </div>
      </div>
      {mine && c && c.type && (
        <div className="mt-1 px-1 text-[11.5px] text-ink-mute">
          فهمها المساعد: <span className="text-plum">{KIND_LABEL[c.type] ?? c.type}</span>
        </div>
      )}
    </div>
  );
}
