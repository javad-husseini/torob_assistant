import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Info,
  MessageSquare,
  Mic,
  Phone,
  PhoneOff,
  ShieldCheck,
  Store,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
  DialogFooter,
} from "@/components/ui/dialog";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  FieldGroup,
  Field,
  FieldLabel,
  FieldDescription,
} from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import { Conversation } from "./conversation";
import { CallClient } from "@/lib/call-client";
import type { Api, Product, Config, CallResult, Segment } from "@/lib/api";
import { fa, money, stockLabel, installmentsLabel } from "@/lib/api";

function CloseButton({ id }: { id?: string }) {
  return (
    <DialogClose asChild>
      <Button
        id={id}
        variant="ghost"
        size="icon-sm"
        className="absolute top-4 end-4"
        aria-label="بستن"
      >
        <X />
      </Button>
    </DialogClose>
  );
}

export function CompareDialog({
  items,
  note,
  comparable,
  onClose,
}: {
  items: Product[];
  note: string;
  comparable: boolean;
  onClose: () => void;
}) {
  const attributes = [
    ...new Set(items.flatMap((p) => Object.keys(p.attributes))),
  ];
  const rows: [string, (p: Product) => string][] = [
    ["قیمت ثبت‌شده", (p) => money(p.price, p.currency)],
    ["موجودی", (p) => stockLabel[p.stock]],
    ["اقساط", (p) => installmentsLabel[p.installments]],
    ...attributes.map(
      (key) =>
        [key, (p: Product) => p.attributes[key] || "نامشخص"] as [
          string,
          (p: Product) => string,
        ],
    ),
  ];
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        id="comparison"
        className="max-h-[85dvh] overflow-y-auto sm:max-w-4xl"
        showCloseButton={false}
        dir="rtl"
      >
        <DialogHeader>
          <DialogTitle>کنار هم، انتخاب راحت‌تر</DialogTitle>
          <DialogDescription>
            مقایسهٔ {fa(items.length)} پیشنهاد بر اساس اطلاعات ثبت‌شده؛ بدون
            تبدیل ضمنی واحدها.
          </DialogDescription>
        </DialogHeader>
        <CloseButton />
        <div id="compare-content">
          <Alert>
            <Info />
            <AlertDescription>
              {comparable
                ? "قیمت‌ها دارای واحد یکسان هستند؛ موجودی و قیمت فعلی تضمین نمی‌شوند."
                : "قیمت‌ها به‌دلیل واحد متفاوت یا اطلاعات نامشخص قابل رتبه‌بندی نیستند."}
            </AlertDescription>
          </Alert>
          <Table className="mt-5 min-w-120">
            <TableHeader>
              <TableRow>
                <TableHead>مشخصه</TableHead>
                {items.map((p) => (
                  <TableHead key={p.id}>
                    <span className="compare-product-title">{p.name}</span>
                    <span className="field-note">
                      {p.store?.name || "فروشگاه نامشخص"}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(([name, getValue]) => (
                <TableRow key={name}>
                  <TableCell className="whitespace-nowrap">{name}</TableCell>
                  {items.map((p) => (
                    <TableCell key={p.id}>{getValue(p)}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <p className="field-note">{note}</p>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">
              بازگشت به محصولات
              <ArrowLeft data-icon="inline-end" />
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function FeedbackDialog({
  product,
  api,
  onClose,
}: {
  product: Product;
  api: Api;
  onClose: () => void;
}) {
  const [kind, setKind] = useState("visit");
  const [purchased, setPurchased] = useState(false);
  const [consent, setConsent] = useState(false);
  const [text, setText] = useState("");
  const [status, setStatus] = useState("");
  const [id, setId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [invalid, setInvalid] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setInvalid(false);
    if (!consent || (kind === "purchase" && !purchased)) {
      setStatus(
        !consent
          ? "برای ثبت تجربه، رضایت شما لازم است."
          : "ابتدا خرید این محصول را تأیید کنید.",
      );
      setInvalid(true);
      return;
    }
    setBusy(true);
    try {
      const data = await api<{ id: string }>(`/api/feedback/${kind}`, {
        product_id: product.id,
        consent,
        purchased,
        text,
      });
      setId(data.id);
      setStatus(
        "تجربهٔ شما به‌صورت موقت ثبت شد. برای اصلاح، حذف و دوباره ثبت کنید.",
      );
    } catch (error) {
      setStatus((error as Error).message);
      setInvalid(true);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    try {
      await api(`/api/feedback/${id}`, undefined, "DELETE");
      setId(null);
      setStatus("بازخورد شما حذف شد.");
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        id="feedback"
        className="max-h-[90dvh] overflow-y-auto sm:max-w-lg"
        showCloseButton={false}
        dir="rtl"
      >
        <DialogHeader>
          <span className="dialog-emblem">
            <MessageSquare />
          </span>
          <DialogTitle>تجربهٔ شما ارزشمند است</DialogTitle>
          <DialogDescription>{product.name}</DialogDescription>
        </DialogHeader>
        <CloseButton />
        <form id="feedback-form" onSubmit={submit}>
          <FieldGroup>
            <Field>
              <FieldLabel id="feedback-kind-label">
                کدام تجربه را ثبت می‌کنید؟
              </FieldLabel>
              <ToggleGroup
                id="feedback-kind"
                type="single"
                value={kind}
                onValueChange={(value) => {
                  if (value) setKind(value);
                }}
                variant="outline"
                aria-labelledby="feedback-kind-label"
                className="w-full"
              >
                <ToggleGroupItem value="visit" className="flex-1">
                  پس از بازدید
                </ToggleGroupItem>
                <ToggleGroupItem value="purchase" className="flex-1">
                  پس از خرید
                </ToggleGroupItem>
              </ToggleGroup>
              <FieldDescription>
                برای ثبت تجربهٔ بازدید، نیازی به خرید نیست.
              </FieldDescription>
            </Field>
            {kind === "purchase" && (
              <Field
                orientation="horizontal"
                data-invalid={invalid && !purchased}
              >
                <Checkbox
                  id="purchased"
                  checked={purchased}
                  onCheckedChange={(value) => setPurchased(value === true)}
                  aria-invalid={invalid && !purchased}
                />
                <FieldLabel htmlFor="purchased">
                  تأیید می‌کنم این محصول را خریده‌ام
                </FieldLabel>
              </Field>
            )}
            <Field>
              <FieldLabel htmlFor="feedback-text">
                از تجربه‌تان بگویید
              </FieldLabel>
              <Textarea
                id="feedback-text"
                rows={4}
                maxLength={1000}
                required
                placeholder="چه چیزی در بازدید یا خرید برایتان مهم بود؟"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <FieldDescription>
                اطلاعات شخصی ننویسید. هدف، شناخت تجربهٔ خرید شماست.
              </FieldDescription>
            </Field>
            <Field orientation="horizontal" data-invalid={invalid && !consent}>
              <Checkbox
                id="consent"
                checked={consent}
                onCheckedChange={(value) => setConsent(value === true)}
                aria-invalid={invalid && !consent}
              />
              <FieldLabel htmlFor="consent">
                با ثبت موقت این بازخورد موافقم
              </FieldLabel>
            </Field>
            <Alert>
              <ShieldCheck />
              <AlertDescription>
                بازخورد شما تا حدود یک ساعت نگهداری می‌شود و هر زمان بخواهید
                می‌توانید آن را حذف کنید.
              </AlertDescription>
            </Alert>
            <div id="feedback-status" role="status">
              {status && (
                <Alert variant={invalid ? "destructive" : "default"}>
                  <AlertDescription>{status}</AlertDescription>
                </Alert>
              )}
            </div>
            <Button type="submit" disabled={busy || id !== null}>
              {busy ? (
                <Spinner data-icon="inline-start" />
              ) : (
                <CheckCircle2 data-icon="inline-start" />
              )}
              ثبت بازخورد
            </Button>
            {id && (
              <Button
                id="delete-feedback"
                type="button"
                variant="outline"
                onClick={() => void remove()}
                disabled={busy}
              >
                <Trash2 data-icon="inline-start" />
                حذف بازخورد ثبت‌شده
              </Button>
            )}
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const reasons: Record<string, string> = {
  manual_end: "پایان دستی",
  agent_finished: "پایان خودکار",
  timeout: "پایان مهلت",
  error: "خطا",
  disconnected: "قطع اتصال",
};
const extractionLabels: Record<string, string> = {
  complete: "نتیجه تأیید شد",
  not_requested: "انجام نشده",
  unconfigured: "فعلاً در دسترس نیست",
  error: "دریافت نتیجه انجام نشد",
  invalid: "نتیجه قابل تأیید نیست",
  skipped_incomplete: "انجام نشد؛ متن ناقص",
  skipped_abnormal: "انجام نشد؛ پایان غیرعادی",
  pending: "در حال آماده‌سازی نتیجه",
};

export function CallDialog({
  product,
  config,
  api,
  onClose,
}: {
  product: Product;
  config: Config;
  api: Api;
  onClose: () => void;
}) {
  const client = useRef<CallClient | null>(null);
  const [running, setRunning] = useState(false);
  const [started, setStarted] = useState(false);
  const [status, setStatus] = useState("");
  const [segments, setSegments] = useState<Segment[]>([]);
  const [result, setResult] = useState<CallResult | null>(null);
  useEffect(() => () => client.current?.dispose(), []);
  async function start() {
    if (started) return;
    setStarted(true);
    setStatus("در حال آماده‌سازی میکروفون…");
    client.current = new CallClient(api, {
      status: setStatus,
      active: setRunning,
      transcript: (segment) => setSegments((old) => [...old, segment]),
      result: (value) => {
        setResult(value);
        setSegments(value.transcript);
        setStatus(
          value.transcript_complete
            ? "جلسه پایان یافت؛ متن دوطرفه تأیید شد."
            : "جلسه پایان یافت؛ متن مکالمه ناقص است.",
        );
      },
    });
    try {
      await client.current.start(product);
    } catch (error) {
      setStatus((error as Error).message);
      setStarted(false);
    }
  }
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        id="call"
        className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl"
        showCloseButton={false}
        dir="rtl"
      >
        <DialogHeader>
          <span className="dialog-emblem">
            <Phone />
          </span>
          <DialogTitle>پیش از رفتن، استعلام کن</DialogTitle>
          <DialogDescription>
            دموی گفت‌وگو دربارهٔ محصول انتخاب‌شده
          </DialogDescription>
        </DialogHeader>
        <CloseButton id="close-call" />
        <Alert>
          <Info />
          <AlertDescription className="notice">
            دموی تماس مرورگری است؛ تماس تلفنی واقعی برقرار نمی‌شود و شما نقش
            فروشنده را دارید.
          </AlertDescription>
        </Alert>
        <Card size="sm">
          <CardHeader>
            <CardTitle>{product.name}</CardTitle>
            <CardDescription>
              <span className="inline-flex items-center gap-1">
                <Store className="size-3.5" />
                {product.store?.name}
              </span>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="field-note">
              {Object.entries(product.attributes)
                .slice(0, 5)
                .map(([key, value]) => `${key}: ${value}`)
                .join(" · ")}
            </p>
          </CardContent>
          <CardFooter>
            <Badge variant="secondary">همان محصول و همان فروشگاه</Badge>
          </CardFooter>
        </Card>
        {!config.call_configured && (
          <Alert>
            <AlertTitle>دموی صوتی هنوز آماده نیست</AlertTitle>
            <AlertDescription>
              گفت‌وگوی صوتی فعلاً در دسترس نیست. می‌توانید جست‌وجو و مقایسهٔ
              محصولات را ادامه دهید.
            </AlertDescription>
          </Alert>
        )}
        <p className="field-note">
          صدا ذخیره نمی‌شود. نتیجه از متن کامل مکالمه تهیه می‌شود؛ متن و نتیجه
          تا حدود یک ساعت نگهداری می‌شوند.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button
            id="start-call"
            disabled={!config.call_configured || started}
            onClick={() => void start()}
          >
            <Mic data-icon="inline-start" />
            شروع دمو با میکروفون
          </Button>
          <Button
            id="end-call"
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
        <p id="call-status" role="status" className="field-note">
          {status}
        </p>
        <Conversation
          id="transcript"
          messages={segments.map((s, index) => ({
            id: `${s.item_id}-${index}`,
            speaker: s.speaker === "seller" ? "user" : "agent",
            text: s.text || "[صدای پخش‌شده یا متن دقیق نامشخص]",
          }))}
          userLabel="فروشنده"
          agentLabel="دستیار هوش مصنوعی ترب"
        />
        {result && (
          <div id="call-result">
            <Card>
              <CardHeader>
                <CardTitle>نتیجهٔ نهایی دمو</CardTitle>
                <CardDescription>
                  {reasons[result.reason]} · متن{" "}
                  {result.transcript_complete ? "کامل" : "ناقص"}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="call-facts">
                  <div>
                    <span>موجودی</span>
                    <strong>{stockLabel[result.availability]}</strong>
                  </div>
                  <div>
                    <span>قیمت</span>
                    <strong>
                      {money(result.price_amount, result.currency)}
                    </strong>
                  </div>
                </div>
                <p>
                  وضعیت نتیجه:{" "}
                  {extractionLabels[result.extraction_status] || "نامشخص"}
                </p>
                <p className="field-note">
                  نوبت تکمیلی مصرف‌شده: {fa(result.clarification_count)} از ۲ ·
                  بی‌پاسخ:{" "}
                  {result.unanswered_questions
                    .map((q) => (q === "price" ? "قیمت" : "موجودی"))
                    .join("، ") || "ندارد"}
                </p>
                {result.diagnostics.includes(
                  "qwen_context_truncation_unsupported",
                ) && (
                  <Alert>
                    <Info />
                    <AlertDescription>
                      مکالمه قطع شد و متن کامل نیست؛ نتیجه قابل تأیید نیست.
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
              <CardFooter>
                <DialogClose asChild>
                  <Button variant="outline">بازگشت به خرید</Button>
                </DialogClose>
              </CardFooter>
            </Card>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
