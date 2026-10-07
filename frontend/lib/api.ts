import useSWR, { mutate as globalMutate } from "swr";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

function headers(extra?: HeadersInit): HeadersInit {
  return { ...(API_KEY ? { "X-API-Key": API_KEY } : {}), ...(extra || {}) };
}

export class ApiError extends Error {}

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = `خطأ ${r.status}`;
    try {
      const j = await r.json();
      detail = typeof j.detail === "string" ? j.detail : detail;
    } catch {}
    throw new ApiError(detail);
  }
  return r.json();
}

export const fetcher = <T,>(path: string) => fetch(`${API_URL}${path}`, { headers: headers() }).then((r) => handle<T>(r));

export async function api<T = unknown>(path: string, method = "POST", body?: unknown): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {
    method,
    headers: headers(body !== undefined ? { "Content-Type": "application/json" } : undefined),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(r);
}

export async function apiForm<T = unknown>(path: string, form: FormData): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { method: "POST", headers: headers(), body: form });
  return handle<T>(r);
}

export function useApi<T>(path: string | null, refreshInterval = 0) {
  return useSWR<T>(path, fetcher, { refreshInterval, revalidateOnFocus: true, keepPreviousData: true });
}

/** بعد أي إجراء يغير البيانات: نحدّث كل الشاشات */
export function refreshAll() {
  return globalMutate((key) => typeof key === "string" && key.startsWith("/api/"));
}

export function mediaUrl(u?: string | null) {
  if (!u) return "";
  return u.startsWith("http") ? u : `${API_URL}${u}`;
}
