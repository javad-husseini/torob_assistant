export type Stock = "in_stock" | "out_of_stock" | "unknown";
export interface Product {
  id: string;
  product_id?: string | null;
  name: string;
  category: string;
  attributes: Record<string, string>;
  price: string | number | null;
  currency: "TOMAN" | "IRR" | null;
  stock: Stock;
  installments: "yes" | "no" | "unknown";
  store: { id: string; name: string } | null;
  call_eligible: boolean;
  recorded_price?: string | null;
  updated_at: string | null;
  why: string;
  demo: boolean;
}
export interface Config {
  csrf_token: string;
  call_configured: boolean;
  call_missing: string[];
  coverage: {
    products: number;
    offers?: number;
    stores: number;
    categories: string[];
    attributes: Record<string, string[]>;
    currencies: string[];
    issues: string[];
  };
}
export interface SearchResult {
  state: string;
  message: string;
  items: Product[];
}
export interface Segment {
  item_id: string;
  speaker: "seller" | "agent";
  text: string | null;
  interrupted: boolean;
}
export interface CallResult {
  reason: string;
  availability: Stock;
  price_amount: number | null;
  currency: Product["currency"];
  clarification_count: number;
  unanswered_questions: string[];
  transcript: Segment[];
  transcript_complete: boolean;
  diagnostics: string[];
  extraction_status: string;
  extraction_usage: {
    total_tokens?: number | null;
    reported_cost?: string | number | null;
    reported_cost_currency?: string | null;
  };
}
export type Api = <T>(
  path: string,
  body?: unknown,
  method?: string,
) => Promise<T>;
export function makeApi(config: () => Config | null): Api {
  return async <T>(
    path: string,
    body?: unknown,
    method?: string,
  ): Promise<T> => {
    const response = await fetch(path, {
      method: method ?? (body !== undefined ? "POST" : "GET"),
      headers: {
        "Content-Type": "application/json",
        ...(config() ? { "X-App-Token": config()!.csrf_token } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : response.status === 503
            ? "دموی تماس هنوز آماده نیست. تنظیمات سرویس باید تکمیل شود."
            : response.status === 422
              ? "ورودی نامعتبر است؛ مبلغ، واحد و محدودیت‌ها را بررسی کنید."
              : `درخواست انجام نشد (${response.status})`,
      );
    return data as T;
  };
}
export const fa = (n: number) => n.toLocaleString("fa-IR");
export const money = (
  n: string | number | null | undefined,
  currency: string | null,
) =>
  n != null && currency
    ? `${Number(n).toLocaleString("fa-IR")} ${currency === "TOMAN" ? "تومان" : "ریال"}`
    : "نامشخص";
export const stockLabel: Record<Stock, string> = {
  in_stock: "موجود (ثبت‌شده)",
  out_of_stock: "ناموجود (ثبت‌شده)",
  unknown: "نامشخص",
};
export const installmentsLabel = { yes: "بله", no: "خیر", unknown: "نامشخص" };
export const normalizeFa = (s: string) =>
  s
    .replace(/[يى]/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/\u200c/g, " ")
    .toLocaleLowerCase()
    .trim();
