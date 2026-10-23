import { useEffect, useRef, useState } from "react";
import { Info, Mic, PhoneOff, Store } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Conversation } from "@/components/conversation";
import { CallClient } from "@/lib/call-client";
import { fa, money, stockLabel } from "@/lib/api";
import type { Api, Config, Product, CallResult, Segment } from "@/lib/api";

const extractionLabels: Record<string, string> = {
  complete: "نتیجه و شواهد تأیید شد",
  not_requested: "انجام نشده",
  unconfigured: "فعلاً در دسترس نیست",
  error: "دریافت نتیجه انجام نشد",
  invalid: "نتیجه قابل تأیید نیست",
  skipped_incomplete: "انجام نشد؛ متن ناقص",
  skipped_abnormal: "انجام نشد؛ پایان غیرعادی",
  pending: "در حال آماده‌سازی نتیجه",
};

export function InlineInquiry({
  product,
  config,
  api,
  locked,
  onBusyChange,
}: {
  product: Product;
  config: Config;
  api: Api;
  locked: boolean;
  onBusyChange: (busy: boolean) => void;
}) {
  const client = useRef<CallClient | null>(null);
  const [running, setRunning] = useState(false);
  const [started, setStarted] = useState(false);
  const [status, setStatus] = useState("");
  const [segments, setSegments] = useState<Segment[]>([]);
  const [result, setResult] = useState<CallResult | null>(null);
  useEffect(() => () => client.current?.dispose(), []);
  async function start() {
    if (started || locked) return;
    setStarted(true);
    onBusyChange(true);
    setStatus("در حال آماده‌سازی میکروفون…");
    client.current = new CallClient(api, {
      status: setStatus,
      active: (active) => {
        setRunning(active);
        if (!active) onBusyChange(false);
      },
      transcript: (segment) => setSegments((old) => [...old, segment]),
      result: (value) => {
        setResult(value);
        setSegments(value.transcript);
        onBusyChange(false);
        setStatus(
          value.reason === "timeout"
            ? "مهلت دمو تمام شد. متن کامل مکالمه تأیید نشده است."
            : value.reason === "disconnected"
            ? "اتصال صوتی قطع شد؛ مکالمه کامل نشده است."
            : value.diagnostics.includes("playback_failed")
            ? "پخش صدا در مرورگر متوقف شد؛ مکالمه کامل نشده است."
            : value.diagnostics.includes("provider_error")
            ? "سرویس صوتی هنگام مکالمه خطا داد؛ مکالمه کامل نشده است."
            : value.reason === "error" && value.transcript.length === 0
            ? "اتصال برقرار نشد و مکالمه شروع نشد. لطفاً دوباره تلاش کنید."
            : value.transcript_complete
            ? "دمو پایان یافت؛ متن دوطرفه تأیید شد."
            : "دمو پایان یافت؛ متن مکالمه ناقص است.",
        );
      },
    });
    try {
      await client.current.start(product);
    } catch (error) {
      setStatus((error as Error).message);
      setStarted(false);
      onBusyChange(false);
    }
  }
  return (
    <Card
      className="inline-inquiry"
      data-testid="inline-inquiry"
      data-offer-id={product.id}
    >
      <CardHeader>
        <CardTitle>پیش از رفتن، استعلام بگیر</CardTitle>
        <CardDescription>
          <span className="inline-flex items-center gap-1.5">
            <Store className="size-3.5" />
            {product.store?.name}
          </span>{" "}
          · {product.name}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Alert>
          <Info />
          <AlertDescription>
            این گفت‌وگوی آزمایشی است؛ شما نقش فروشنده را دارید. تماس تلفنی
            واقعی با فروشگاه برقرار نمی‌شود.
          </AlertDescription>
        </Alert>
        {!config.call_configured && (
          <Alert>
            <AlertDescription>
              گفت‌وگوی صوتی فعلاً در دسترس نیست. لطفاً کمی بعد دوباره تلاش کنید.
            </AlertDescription>
          </Alert>
        )}
        <p className="field-note">
          صدا ذخیره نمی‌شود. نتیجه از متن کامل مکالمه تهیه می‌شود؛ متن و نتیجه
          تا حدود یک ساعت نگهداری می‌شوند.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={
              !config.call_configured ||
              !product.call_eligible ||
              started ||
              locked
            }
            onClick={() => void start()}
          >
            <Mic data-icon="inline-start" />
            شروع دمو با میکروفون
          </Button>
          <Button
            variant="outline"
            disabled={!running}
            onClick={() =>
              void client.current
                ?.end()
                .catch((error: Error) => setStatus(error.message))
            }
          >
            <PhoneOff data-icon="inline-start" />
            پایان دمو
          </Button>
        </div>
        <p role="status" className="field-note">
          {status}
        </p>
        <Conversation
          id={`transcript-${product.id}`}
          messages={segments.map((segment, index) => ({
            id: `${segment.item_id}-${index}`,
            speaker: segment.speaker === "seller" ? "user" : "agent",
            text: segment.text || "[متن دقیق صدای پخش‌شده نامشخص]",
          }))}
          userLabel="فروشنده"
          agentLabel="دستیار صوتی ترب"
        />
        {result && (
          <div className="flex flex-col gap-3" data-testid="call-result">
            <Badge variant="secondary">
              متن {result.transcript_complete ? "کامل" : "ناقص"}
            </Badge>
            <div className="call-facts">
              <div>
                <span>موجودی</span>
                <strong>{stockLabel[result.availability]}</strong>
              </div>
              <div>
                <span>قیمت</span>
                <strong>{money(result.price_amount, result.currency)}</strong>
              </div>
            </div>
            <p className="field-note">
              وضعیت نتیجه:{" "}
              {extractionLabels[result.extraction_status] || "نامشخص"}
            </p>
            <p className="field-note">
              پرسش تکمیلی: {fa(result.clarification_count)} از ۲ · پرسش‌های
              بی‌پاسخ:{" "}
              {result.unanswered_questions
                .map((item) => (item === "price" ? "قیمت" : "موجودی"))
                .join("، ") || "ندارد"}
            </p>
            {result.diagnostics.includes(
              "qwen_context_truncation_unsupported",
            ) && (
              <Alert>
                <AlertDescription>
                  به دلیل قطع پاسخ صوتی، متن کامل تأیید نشد و نتیجهٔ قطعی
                  استخراج نمی‌شود.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}
      </CardContent>
      <CardFooter>
        <p className="field-note">
          استعلام فقط برای همین محصول و همین فروشگاه است.
        </p>
      </CardFooter>
    </Card>
  );
}
